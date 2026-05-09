"""Gate B: action-controller tests with a fake store.

These tests run without ArcPy. They prove the action layer reads from / writes
to a Store-shaped seam in the right places, validates input atomically, and
respects the schema boundary (ensure_schema vs assert_schema).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from toolbox import arcpy_game_actions as actions
from toolbox import arcpy_game_rules as rules


@dataclass
class FakeStore:
    """In-memory Store impl that records every call for assertion."""

    cells: dict[str, rules.CellState] = field(default_factory=dict)
    adjacency: dict[str, list[rules.AdjacencyLink]] = field(default_factory=dict)
    state: rules.GameState | None = None
    log: list[dict[str, object]] = field(default_factory=list)
    selection: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def ensure_schema(self) -> None:
        self.calls.append("ensure_schema")

    def assert_schema(self) -> None:
        self.calls.append("assert_schema")

    def clear_all(self) -> None:
        self.calls.append("clear_all")
        self.cells = {}
        self.adjacency = {}
        self.state = None
        self.log = []
        self.selection = []

    def read_selection(self) -> list[str]:
        self.calls.append("read_selection")
        return list(self.selection)

    def read_game(self) -> rules.SurveySweeperGame:
        self.calls.append("read_game")
        if self.state is None:
            raise RuntimeError("FakeStore has no game; call new_game_action first")
        return rules.SurveySweeperGame(
            cells=self.cells,
            adjacency=self.adjacency,
            state=self.state,
        )

    def write_cells(self, changed_ids: list[str], game: rules.SurveySweeperGame) -> None:
        self.calls.append(f"write_cells:{','.join(changed_ids)}")
        for cid in changed_ids:
            self.cells[cid] = game.cells[cid]

    def write_state(self, state: rules.GameState) -> None:
        self.calls.append("write_state")
        self.state = state

    def write_full_game(self, game: rules.SurveySweeperGame) -> None:
        self.calls.append("write_full_game")
        self.cells = dict(game.cells)
        self.adjacency = dict(game.adjacency)
        self.state = game.state

    def append_log(self, payload: dict[str, object]) -> None:
        self.calls.append("append_log")
        self.log.append(dict(payload))


def test_new_game_writes_board_state_adjacency_and_log():
    store = FakeStore()

    result = actions.new_game_action(store, preset_name="Tiny Demo", seed=2026)

    assert result.ok is True
    assert result.action == "New Game"
    assert store.state is not None
    assert store.state.status == "playing"
    assert store.state.seed == 2026
    assert store.state.board_rows == 5
    assert store.state.board_cols == 5
    assert store.state.hazard_count == 4
    assert len(store.cells) == 25
    assert sum(len(links) for links in store.adjacency.values()) == 144
    assert len(store.log) == 1
    assert store.log[0]["action"] == "New Game"


def test_new_game_calls_ensure_schema_and_clears_before_writing():
    store = FakeStore()

    actions.new_game_action(store, preset_name="Tiny Demo", seed=2026)

    assert "ensure_schema" in store.calls
    assert "clear_all" in store.calls
    assert "write_full_game" in store.calls
    assert "append_log" in store.calls
    assert store.calls.index("ensure_schema") < store.calls.index("clear_all")
    assert store.calls.index("clear_all") < store.calls.index("write_full_game")
    assert "assert_schema" not in store.calls


def _store_with_seed_2026_game() -> FakeStore:
    store = FakeStore()
    actions.new_game_action(store, preset_name="Tiny Demo", seed=2026)
    store.calls.clear()
    return store


def test_reveal_happy_path_reads_selection_writes_changed_rows_and_logs_once():
    store = _store_with_seed_2026_game()
    store.selection = ["R00C00"]
    log_before = len(store.log)

    result = actions.reveal_action(store)

    assert result.ok is True
    assert result.action == "Reveal / Scout"
    assert result.changed_cell_ids == ["R00C00"]
    assert "assert_schema" in store.calls
    assert "ensure_schema" not in store.calls
    assert "read_selection" in store.calls
    assert "read_game" in store.calls
    assert "write_cells:R00C00" in store.calls
    assert "write_state" in store.calls
    assert "append_log" in store.calls
    assert len(store.log) == log_before + 1
    assert store.cells["R00C00"].revealed is True
    assert store.state is not None and store.state.action_count == 1
    for required in ("Reveal / Scout", "R00C00", "Adjacency lookup"):
        assert required in result.message


def test_reveal_with_no_selection_does_not_mutate_board():
    store = _store_with_seed_2026_game()
    store.selection = []
    cells_snapshot = {cid: cell.revealed for cid, cell in store.cells.items()}
    state_snapshot = (store.state.action_count, store.state.status)

    result = actions.reveal_action(store)

    assert result.ok is False
    assert "Select exactly one" in result.message
    assert "write_cells" not in " ".join(store.calls)
    assert "write_state" not in store.calls
    assert {cid: cell.revealed for cid, cell in store.cells.items()} == cells_snapshot
    assert (store.state.action_count, store.state.status) == state_snapshot


def test_reveal_with_unknown_cell_id_rejects_cleanly():
    store = _store_with_seed_2026_game()
    store.selection = ["R99C99"]

    result = actions.reveal_action(store)

    assert result.ok is False
    assert "Unknown cell" in result.message
    assert "write_cells" not in " ".join(store.calls)
    assert "write_state" not in store.calls


def test_ordinary_actions_use_assert_schema_not_ensure_schema():
    store = _store_with_seed_2026_game()
    store.selection = ["R00C00"]

    actions.reveal_action(store)

    assert "ensure_schema" not in store.calls, (
        "Reveal must not mutate schema mid-turn; call assert_schema only."
    )
    assert "assert_schema" in store.calls


def test_flag_happy_path_writes_toggled_cells_and_logs_once():
    store = _store_with_seed_2026_game()
    store.selection = ["R00C03", "R02C00"]
    log_before = len(store.log)

    result = actions.flag_action(store)

    assert result.ok is True
    assert result.action == "Flag / Mark"
    assert result.changed_cell_ids == ["R00C03", "R02C00"]
    assert "assert_schema" in store.calls
    assert "ensure_schema" not in store.calls
    assert "write_cells:R00C03,R02C00" in store.calls
    assert "write_state" in store.calls
    assert len(store.log) == log_before + 1
    assert store.cells["R00C03"].flagged is True
    assert store.cells["R02C00"].flagged is True
    assert store.state.flags_count == 2


def test_flag_with_revealed_cell_in_selection_is_atomic():
    store = _store_with_seed_2026_game()
    store.selection = ["R00C00"]
    actions.reveal_action(store)
    store.calls.clear()
    store.selection = ["R00C01", "R00C00"]
    flags_before = store.state.flags_count

    result = actions.flag_action(store)

    assert result.ok is False
    assert "revealed" in result.message
    assert "write_cells" not in " ".join(store.calls)
    assert store.state.flags_count == flags_before
    assert store.cells["R00C01"].flagged is False


def test_show_score_runs_without_selection_and_does_not_mutate_board():
    store = _store_with_seed_2026_game()
    store.selection = []
    cells_snapshot = {cid: (c.revealed, c.flagged) for cid, c in store.cells.items()}
    state_snapshot = (
        store.state.action_count,
        store.state.status,
        store.state.flags_count,
        store.state.safe_revealed_count,
    )
    log_before = len(store.log)

    result = actions.show_score_action(store)

    assert result.ok is True
    assert result.action == "Show Score"
    assert result.refresh_required is False
    assert "assert_schema" in store.calls
    assert "ensure_schema" not in store.calls
    assert "write_cells" not in " ".join(store.calls)
    assert "write_state" not in store.calls
    assert len(store.log) == log_before + 1
    assert {cid: (c.revealed, c.flagged) for cid, c in store.cells.items()} == cells_snapshot
    assert (
        store.state.action_count,
        store.state.status,
        store.state.flags_count,
        store.state.safe_revealed_count,
    ) == state_snapshot
    for fact in ("status=playing", "seed=2026", "flags=0/4", "safe revealed=0/21"):
        assert fact in result.message


def test_messages_include_required_gis_and_game_facts():
    store = _store_with_seed_2026_game()
    store.selection = ["R00C00"]
    reveal = actions.reveal_action(store)

    assert reveal.action in reveal.message
    assert "R00C00" in reveal.message
    gis_ops = ("Selection cursor", "Adjacency lookup", "Field update", "Display state")
    assert any(op in reveal.message for op in gis_ops), (
        f"Reveal message must name a GIS op; got: {reveal.message!r}"
    )

    store.selection = ["R00C03"]
    flag = actions.flag_action(store)
    assert flag.action in flag.message
    assert "R00C03" in flag.message
    assert any(op in flag.message for op in gis_ops)
