#!/usr/bin/env python3
"""Survey Sweeper smoke demo.

Drives the pure-Python rules engine through two deterministic arcs:

    1. "loss" arc on the seed-2026 Tiny Demo board (5x5, 4 hazards) that
       exercises hidden, revealed_empty, revealed_clue, flagged, hazard_hit,
       hazard_revealed, plus one rejected action.
    2. "win" arc on a hand-built 2x2 board (1 hazard) that exercises won_safe.

Together they cover every display_state branch.

Output convention:

    stdout = one JSON record per turn (JSONL; pipe into jq or a log collector)
    stderr = human-readable board + status banner

Each JSONL record carries an "arc" discriminator so a single capture file can
be split by arc downstream.

Run from anywhere:

    python scripts/play_demo.py
    python scripts/play_demo.py | jq -c '{arc, turn, action, status}'
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toolbox import arcpy_game_rules as rules

# Line-buffer stdout so JSONL records interleave with stderr board art in
# chronological order under redirection (Python block-buffers stdout otherwise).
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)


_DISPLAY_GLYPH = {
    "hidden": ".",
    "flagged": "F",
    "revealed_empty": "_",
    "revealed_clue": None,
    "hazard_hit": "X",
    "hazard_revealed": "*",
    "won_safe": "O",
}


def render_board(game: rules.SurveySweeperGame) -> str:
    rows, cols = game.state.board_rows, game.state.board_cols
    lines = ["    " + "  ".join(f"C{c:02d}" for c in range(cols))]
    for r in range(rows):
        glyphs = []
        for c in range(cols):
            cell = game.cells[rules.cell_id(r, c)]
            glyph = _DISPLAY_GLYPH[cell.display_state]
            if glyph is None:
                glyph = str(cell.neighbor_count)
            glyphs.append(f" {glyph} ")
        lines.append(f"R{r:02d} " + " ".join(glyphs))
    return "\n".join(lines)


def emit_log(arc: str, turn: int, result: rules.ActionResult) -> None:
    record: dict[str, object] = {
        "arc": arc,
        "turn": turn,
        "ok": result.ok,
        "action": result.action,
        "changed_cell_ids": result.changed_cell_ids,
        "message": result.message,
    }
    record.update(result.log_payload)
    print(json.dumps(record, sort_keys=True))


def banner(line: str) -> None:
    print(line, file=sys.stderr)


def build_manual_game(rows: int, cols: int, hazards: set[str]) -> rules.SurveySweeperGame:
    ids = rules.generate_cell_ids(rows, cols)
    adjacency = rules.build_adjacency(rows, cols)
    counts = rules.compute_neighbor_counts(ids, hazards, adjacency)
    cells = {
        cid: rules.CellState(
            cell_id=cid,
            row_idx=int(cid[1:3]),
            col_idx=int(cid[4:6]),
            is_hazard=cid in hazards,
            neighbor_count=counts[cid],
        )
        for cid in ids
    }
    state = rules.GameState(
        mode="survey",
        status="playing",
        seed=0,
        board_rows=rows,
        board_cols=cols,
        hazard_count=len(hazards),
    )
    game = rules.SurveySweeperGame(cells=cells, adjacency=adjacency, state=state)
    rules.refresh_display_states(game)
    return game


def play_arc(
    arc: str,
    game: rules.SurveySweeperGame,
    turns: list[tuple[str, list[str]]],
) -> None:
    banner(render_board(game))
    banner("")
    for turn_idx, (op, cells) in enumerate(turns, start=1):
        if op == "reveal":
            result = rules.reveal_cells(game, cells)
        elif op == "flag":
            result = rules.flag_cells(game, cells)
        else:
            raise ValueError(f"unknown op {op!r}")

        emit_log(arc, turn_idx, result)

        banner(f"# [{arc}] turn {turn_idx}: {op} {cells}  ok={result.ok}")
        banner(render_board(game))
        banner(
            f"# status={game.state.status}  "
            f"action_count={game.state.action_count}  "
            f"flags={game.state.flags_count}/{game.state.hazard_count}  "
            f"safe_revealed={game.state.safe_revealed_count}"
        )
        banner("")

        if game.state.status in {"won", "lost"}:
            banner(f"# [{arc}] terminal status reached: {game.state.status}")
            return


def main() -> int:
    banner("# Survey Sweeper Smoke Demo")
    banner("")

    banner("## Arc 1: loss  (preset=Tiny Demo, seed=2026, board=5x5, hazards=4)")
    loss_game = rules.new_game("Tiny Demo", seed=2026)
    loss_turns: list[tuple[str, list[str]]] = [
        ("reveal", ["R00C00"]),
        ("reveal", ["R00C02"]),
        ("flag",   ["R00C03"]),
        ("reveal", ["R00C03"]),
        ("flag",   ["R00C03"]),
        ("reveal", ["R00C03"]),
    ]
    play_arc("loss", loss_game, loss_turns)

    banner("")
    banner("## Arc 2: win  (manual board=2x2, hazard at R00C00)")
    win_game = build_manual_game(rows=2, cols=2, hazards={"R00C00"})
    win_turns: list[tuple[str, list[str]]] = [
        ("flag",   ["R00C00"]),
        ("reveal", ["R00C01"]),
        ("reveal", ["R01C00"]),
        ("reveal", ["R01C01"]),
    ]
    play_arc("win", win_game, win_turns)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
