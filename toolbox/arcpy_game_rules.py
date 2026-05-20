"""Pure Python Survey Sweeper rules.

This module intentionally does not import ArcPy. ArcGIS Pro integration code
should treat these functions as the gameplay source of truth and persist their
cell/state/action results into feature classes and tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Iterable


@dataclass(frozen=True)
class BoardPreset:
    name: str
    rows: int
    cols: int
    hazard_count: int


@dataclass(frozen=True)
class AdjacencyLink:
    neighbor_id: str
    touch_type: str
    weight: float = 1.0


@dataclass
class CellState:
    cell_id: str
    row_idx: int
    col_idx: int
    is_hazard: bool = False
    revealed: bool = False
    flagged: bool = False
    neighbor_count: int = 0
    turn_revealed: int = -1
    display_state: str = "hidden"
    notes: str = ""
    hazard_hit: bool = False


@dataclass
class GameState:
    mode: str = "survey"
    status: str = "playing"
    seed: int = 2026
    board_rows: int = 5
    board_cols: int = 5
    hazard_count: int = 4
    safe_revealed_count: int = 0
    flags_count: int = 0
    action_count: int = 0
    last_message: str = ""


@dataclass
class SurveySweeperGame:
    cells: dict[str, CellState]
    adjacency: dict[str, list[AdjacencyLink]]
    state: GameState


@dataclass
class ActionResult:
    ok: bool
    action: str
    changed_cell_ids: list[str] = field(default_factory=list)
    message: str = ""
    gp_operations: list[str] = field(default_factory=list)
    log_payload: dict[str, object] = field(default_factory=dict)
    refresh_required: bool = True


_PRESETS = {
    "Tiny Demo": BoardPreset("Tiny Demo", rows=5, cols=5, hazard_count=4),
    "Small": BoardPreset("Small", rows=7, cols=7, hazard_count=8),
}

_TERMINAL_STATUSES = {"won", "lost"}


def cell_id(row_idx: int, col_idx: int) -> str:
    """Return the stable zero-padded cell identifier for a board position."""

    return f"R{row_idx:02d}C{col_idx:02d}"


def generate_cell_ids(rows: int, cols: int) -> list[str]:
    """Return stable cell IDs in row-major board order."""

    if rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive")
    return [cell_id(r, c) for r in range(rows) for c in range(cols)]


def get_board_preset(name: str) -> BoardPreset:
    """Return a frozen MVP board preset by display name."""

    try:
        return _PRESETS[name]
    except KeyError as exc:
        allowed = ", ".join(sorted(_PRESETS))
        raise ValueError(f"Unknown board preset {name!r}. Expected one of: {allowed}") from exc


def build_adjacency(rows: int, cols: int) -> dict[str, list[AdjacencyLink]]:
    """Build directed 8-way adjacency for a rectangular Survey Sweeper board."""

    adjacency: dict[str, list[AdjacencyLink]] = {}
    for r in range(rows):
        for c in range(cols):
            cid = cell_id(r, c)
            links: list[AdjacencyLink] = []
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr = r + dr
                    nc = c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        touch_type = "edge" if dr == 0 or dc == 0 else "corner"
                        links.append(AdjacencyLink(cell_id(nr, nc), touch_type))
            adjacency[cid] = links
    return adjacency


def place_hazards(cell_ids: Iterable[str], hazard_count: int, seed: int) -> set[str]:
    """Place a deterministic set of hazards by seed."""

    ids = list(cell_ids)
    if hazard_count < 0 or hazard_count > len(ids):
        raise ValueError(f"Cannot place {hazard_count} hazards on {len(ids)} cells")
    return set(random.Random(seed).sample(ids, hazard_count))


def compute_neighbor_counts(
    cell_ids: Iterable[str],
    hazards: set[str],
    adjacency: dict[str, list[AdjacencyLink]],
) -> dict[str, int]:
    """Return adjacent hazard counts for each non-hazard cell; hazards store 0."""

    counts: dict[str, int] = {}
    for cid in cell_ids:
        if cid in hazards:
            counts[cid] = 0
        else:
            counts[cid] = sum(1 for link in adjacency[cid] if link.neighbor_id in hazards)
    return counts


def new_game(preset_name: str = "Tiny Demo", seed: int = 2026) -> SurveySweeperGame:
    """Create a fresh in-memory Survey Sweeper game."""

    preset = get_board_preset(preset_name)
    ids = generate_cell_ids(preset.rows, preset.cols)
    adjacency = build_adjacency(preset.rows, preset.cols)
    hazards = place_hazards(ids, preset.hazard_count, seed)
    counts = compute_neighbor_counts(ids, hazards, adjacency)

    cells: dict[str, CellState] = {}
    for cid in ids:
        row_idx = int(cid[1:3])
        col_idx = int(cid[4:6])
        cells[cid] = CellState(
            cell_id=cid,
            row_idx=row_idx,
            col_idx=col_idx,
            is_hazard=cid in hazards,
            neighbor_count=counts[cid],
        )

    state = GameState(
        mode="survey",
        status="playing",
        seed=seed,
        board_rows=preset.rows,
        board_cols=preset.cols,
        hazard_count=preset.hazard_count,
    )
    game = SurveySweeperGame(cells=cells, adjacency=adjacency, state=state)
    refresh_display_states(game)
    return game


def reveal_cells(game: SurveySweeperGame, selected_cell_ids: Iterable[str]) -> ActionResult:
    """Reveal exactly one selected cell for the MVP Survey Sweeper rules."""

    action = "Reveal / Scout"
    selected = list(selected_cell_ids)
    validation_error = _validate_can_mutate(game, action)
    if validation_error:
        return validation_error
    if len(selected) != 1:
        return _error(action, f"Select exactly one parcel for {action}; got {len(selected)}.")

    cid = selected[0]
    cell = game.cells.get(cid)
    if cell is None:
        return _error(action, f"Unknown cell {cid!r}; select a current Survey Sweeper parcel.")
    if cell.flagged:
        return _error(action, f"Cannot reveal flagged cell {cid}; unflag it first.")
    if cell.revealed:
        return _error(action, f"Cannot reveal already revealed cell {cid}.")

    changed = [cid]
    game.state.action_count += 1
    cell.revealed = True
    cell.turn_revealed = game.state.action_count

    if cell.is_hazard:
        cell.hazard_hit = True
        game.state.status = "lost"
        changed = sorted({cid, *[other.cell_id for other in game.cells.values() if other.is_hazard]})
        message = (
            f"{action}: Selection cursor read parcel {cid}. Field update revealed a hidden hazard. "
            "Status set to LOST; all hazard cells revealed for inspection."
        )
    else:
        game.state.safe_revealed_count = _count_safe_revealed(game)
        if _all_safe_cells_revealed(game):
            game.state.status = "won"
            message = (
                f"{action}: Selection cursor read parcel {cid}. Adjacency lookup found "
                f"{cell.neighbor_count} neighboring hazard indicators. Field update revealed the final safe parcel; "
                "status set to WON."
            )
        else:
            clue_text = "neighboring hazard indicators"
            message = (
                f"{action}: Selection cursor read parcel {cid}. Adjacency lookup found "
                f"{cell.neighbor_count} {clue_text}. Field update set revealed=1 and recomputed Display state."
            )

    refresh_display_states(game)
    game.state.last_message = message
    return _success(
        action,
        changed,
        message,
        ["Selection cursor", "Adjacency lookup", "Field update", "Display state"],
        game,
    )


def flag_cells(game: SurveySweeperGame, selected_cell_ids: Iterable[str]) -> ActionResult:
    """Toggle flags on one or more selected unrevealed cells, atomically."""

    action = "Flag / Mark"
    selected = list(selected_cell_ids)
    validation_error = _validate_can_mutate(game, action)
    if validation_error:
        return validation_error
    if not selected:
        return _error(action, f"Select at least one parcel for {action}.")

    seen = set()
    ordered: list[str] = []
    for cid in selected:
        if cid not in seen:
            seen.add(cid)
            ordered.append(cid)

    for cid in ordered:
        cell = game.cells.get(cid)
        if cell is None:
            return _error(action, f"Unknown cell {cid!r}; select current Survey Sweeper parcels.")
        if cell.revealed:
            return _error(action, f"Cannot flag revealed cell {cid}.")

    game.state.action_count += 1
    for cid in ordered:
        game.cells[cid].flagged = not game.cells[cid].flagged

    game.state.flags_count = sum(1 for cell in game.cells.values() if cell.flagged)
    refresh_display_states(game)
    message = (
        f"{action}: Selection cursor read {len(ordered)} parcel(s) ({','.join(ordered)}). "
        f"Field update toggled flagged state; flags={game.state.flags_count}/{game.state.hazard_count}. "
        "Display state recomputed."
    )
    game.state.last_message = message
    return _success(action, ordered, message, ["Selection cursor", "Field update", "Display state"], game)


def refresh_display_states(game: SurveySweeperGame) -> None:
    """Recompute display_state for every cell from domain state."""

    for cell in game.cells.values():
        cell.display_state = display_state_for_cell(cell, game.state.status)


def display_state_for_cell(cell: CellState, game_status: str) -> str:
    """Map domain fields to the symbology-facing display_state field."""

    if game_status == "won" and not cell.is_hazard and cell.revealed:
        return "won_safe"
    if cell.hazard_hit:
        return "hazard_hit"
    if game_status == "lost" and cell.is_hazard:
        return "hazard_revealed"
    if cell.flagged and not cell.revealed:
        return "flagged"
    if not cell.revealed:
        return "hidden"
    if cell.neighbor_count == 0:
        return "revealed_empty"
    return "revealed_clue"


def _validate_can_mutate(game: SurveySweeperGame, action: str) -> ActionResult | None:
    if game.state.status in _TERMINAL_STATUSES:
        return _error(action, f"Cannot run {action}; game status is {game.state.status}. Run Reset or New Game.")
    return None


def _error(action: str, message: str) -> ActionResult:
    return ActionResult(ok=False, action=action, message=message, refresh_required=False)


def _success(
    action: str,
    changed_cell_ids: list[str],
    message: str,
    gp_operations: list[str],
    game: SurveySweeperGame,
) -> ActionResult:
    return ActionResult(
        ok=True,
        action=action,
        changed_cell_ids=changed_cell_ids,
        message=message,
        gp_operations=gp_operations,
        log_payload={
            "action": action,
            "target_cell_ids": ",".join(changed_cell_ids),
            "result": message,
            "gp_operation": ";".join(gp_operations),
            "status": game.state.status,
            "action_count": game.state.action_count,
        },
        refresh_required=True,
    )


def _count_safe_revealed(game: SurveySweeperGame) -> int:
    return sum(1 for cell in game.cells.values() if not cell.is_hazard and cell.revealed)


def _all_safe_cells_revealed(game: SurveySweeperGame) -> bool:
    return all(cell.is_hazard or cell.revealed for cell in game.cells.values())
