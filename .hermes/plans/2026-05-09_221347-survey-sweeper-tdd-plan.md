# Survey Sweeper TDD Implementation Plan

> **For Hermes:** This is a planning artifact. Do not implement from this document unless Griffin explicitly says to proceed. When execution begins, use strict RED-GREEN-REFACTOR: write one failing test, run it and confirm the expected failure, implement the minimum code, run the specific test green, then run the relevant suite. Commit at reviewable checkpoints.

**Goal:** Finish/verify the pure-Python Survey Sweeper rules with strict TDD discipline, then use the same test-first style to move into ArcPy schema/store/controller integration.

**Architecture:** Keep gameplay rules independent from ArcPy in `toolbox/arcpy_game_rules.py`. Tests in `tests/test_minesweeper_rules.py` define behavior around stable `cell_id`s, board presets, 8-way adjacency, deterministic hazards, reveal/flag actions, win/loss, display-state mapping, and future ArcPy action-result contracts. ArcPy-facing modules must consume these pure rules later rather than duplicating game logic.

**Tech Stack:** Python stdlib dataclasses, pytest via `uv run --with pytest python -m pytest ...`, ArcGIS Pro / ArcPy only in later integration milestones.

---

## Current Context

Repo: `/workspace/projects/arcpyGame`

Relevant existing files discovered:

- `ideas/survey-sweeper-minesweeper-phase-brainstorm.md`
- `ideas/survey-sweeper-milestone-1-implementation-plan.md`
- `ideas/next-steps-survey-sweeper.md`
- `tests/test_minesweeper_rules.py`
- `toolbox/arcpy_game_rules.py`
- `toolbox/__init__.py`

Important note:

- `tests/test_minesweeper_rules.py` and `toolbox/arcpy_game_rules.py` already exist. Do **not** retroactively claim TDD unless the RED/GREEN history is available. From here forward, every behavioral change should be test-first.
- If Griffin wants a purist TDD restart, delete/revert `toolbox/arcpy_game_rules.py` and rebuild from tests one cycle at a time. Otherwise, treat the current files as baseline and use this plan as a TDD audit/hardening path.

---

## Non-Negotiable TDD Rules

For every task that changes behavior:

1. Write or edit exactly one focused failing test first.
2. Run only that test and confirm it fails for the expected reason.
3. Write the smallest implementation change that can pass it.
4. Re-run that specific test and confirm green.
5. Run the relevant test file.
6. Refactor only after green.
7. Commit after a coherent checkpoint.

Commands should generally be run from `/workspace/projects/arcpyGame`.

Preferred test command:

```bash
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py -q
```

Specific-test pattern:

```bash
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py::test_name_here -v
```

Syntax check:

```bash
python -m py_compile toolbox/arcpy_game_rules.py tests/test_minesweeper_rules.py
```

No-ArcPy import check:

```bash
python - <<'PY'
import toolbox.arcpy_game_rules as rules
print(rules.__name__)
PY
```

---

## Phase 0 — Baseline Audit Before Any More Code

### Task 0.1: Run the existing pure rules suite

**Objective:** Establish current baseline without editing code.

**Files:**
- Read only: `tests/test_minesweeper_rules.py`
- Read only: `toolbox/arcpy_game_rules.py`

**Step 1: Run current tests**

```bash
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py -q
```

Expected:

- Ideally: all tests pass.
- If failures occur: do not fix immediately. Record failing test names and decide whether they indicate stale tests, stale implementation, or a real behavioral bug.

**Step 2: Run syntax/import checks**

```bash
python -m py_compile toolbox/arcpy_game_rules.py tests/test_minesweeper_rules.py
python - <<'PY'
import toolbox.arcpy_game_rules as rules
print(rules.__name__)
PY
```

Expected:

- Syntax check passes.
- Import succeeds without ArcPy.

**Step 3: Decide baseline policy**

If tests pass:

- Treat current pure rules as Milestone 1 baseline.
- Do not rewrite working code unless Griffin wants strict restart.

If tests fail:

- For each failure, write a tiny reproducer test or adjust existing test first, verify RED, then fix minimal code.

**Commit checkpoint if baseline is uncommitted:**

```bash
git add tests/test_minesweeper_rules.py toolbox/arcpy_game_rules.py ideas/survey-sweeper-milestone-1-implementation-plan.md
# only commit if these files are intended and green
git commit -m "feat: add Survey Sweeper pure rules baseline"
```

---

## Phase 1 — Pure Rules TDD Contract

These tasks describe the desired RED-GREEN order for Milestone 1. If the existing code already satisfies a task, run the test to verify and mark it complete rather than reimplementing.

### Task 1: Stable cell IDs and MVP board presets

**Objective:** Lock stable row-major `cell_id` generation and accepted board presets.

**Files:**
- Test: `tests/test_minesweeper_rules.py`
- Implement: `toolbox/arcpy_game_rules.py`

**RED test:**

```python
def test_cell_ids_are_zero_padded_and_preserve_board_order():
    ids = rules.generate_cell_ids(5, 5)

    assert len(ids) == 25
    assert len(set(ids)) == 25
    assert ids[0] == "R00C00"
    assert ids[-1] == "R04C04"
    assert sorted(ids) == ids
    assert rules.cell_id(3, 4) == "R03C04"
```

```python
def test_board_presets_are_frozen_for_mvp():
    tiny = rules.get_board_preset("Tiny Demo")
    small = rules.get_board_preset("Small")

    assert (tiny.rows, tiny.cols, tiny.hazard_count) == (5, 5, 4)
    assert (small.rows, small.cols, small.hazard_count) == (7, 7, 8)

    with pytest.raises(ValueError, match="Unknown board preset"):
        rules.get_board_preset("Medium")
```

**Verify RED:**

```bash
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py::test_cell_ids_are_zero_padded_and_preserve_board_order -v
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py::test_board_presets_are_frozen_for_mvp -v
```

Expected initial failure if not implemented:

- `AttributeError` / import failure / missing function.

**GREEN implementation:**

- Add `BoardPreset` dataclass.
- Add `cell_id(row_idx, col_idx)`.
- Add `generate_cell_ids(rows, cols)`.
- Add `get_board_preset(name)` with only `Tiny Demo` and `Small`.

**Verify GREEN:**

```bash
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py::test_cell_ids_are_zero_padded_and_preserve_board_order -v
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py::test_board_presets_are_frozen_for_mvp -v
```

---

### Task 2: 8-way adjacency with edge/corner metadata

**Objective:** Define the Survey Sweeper spatial graph.

**RED test:**

```python
def test_adjacency_has_expected_neighbor_counts_and_metadata():
    adjacency = rules.build_adjacency(5, 5)

    assert len(adjacency["R00C00"]) == 3
    assert len(adjacency["R00C02"]) == 5
    assert len(adjacency["R02C02"]) == 8

    center_neighbors = {link.neighbor_id: link for link in adjacency["R02C02"]}
    assert center_neighbors["R01C02"].touch_type == "edge"
    assert center_neighbors["R01C01"].touch_type == "corner"
    assert center_neighbors["R01C02"].weight == 1.0

    for cid, links in adjacency.items():
        neighbor_ids = [link.neighbor_id for link in links]
        assert cid not in neighbor_ids
        assert len(neighbor_ids) == len(set(neighbor_ids))

    assert sum(len(links) for links in adjacency.values()) == 144
```

**Verify RED:**

```bash
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py::test_adjacency_has_expected_neighbor_counts_and_metadata -v
```

**GREEN implementation:**

- Add `AdjacencyLink(neighbor_id, touch_type, weight=1.0)`.
- Add `build_adjacency(rows, cols)` with directed 8-way adjacency.

**Verify GREEN:** same command.

---

### Task 3: Deterministic hazard placement and clue counts

**Objective:** Lock seed-based hazards and adjacent hazard count semantics.

**RED tests:**

```python
def test_hazard_placement_is_deterministic_unique_and_valid():
    ids = rules.generate_cell_ids(5, 5)

    hazards_a = rules.place_hazards(ids, hazard_count=4, seed=2026)
    hazards_b = rules.place_hazards(ids, hazard_count=4, seed=2026)

    assert hazards_a == hazards_b
    assert len(hazards_a) == 4
    assert hazards_a <= set(ids)

    with pytest.raises(ValueError, match="Cannot place"):
        rules.place_hazards(ids, hazard_count=26, seed=2026)
```

```python
def test_neighbor_counts_for_hand_authored_three_by_three_board():
    ids = rules.generate_cell_ids(3, 3)
    adjacency = rules.build_adjacency(3, 3)
    hazards = {"R00C00", "R02C02"}

    counts = rules.compute_neighbor_counts(ids, hazards, adjacency)

    assert counts["R00C00"] == 0
    assert counts["R00C01"] == 1
    assert counts["R01C01"] == 2
    assert counts["R02C01"] == 1
    assert counts["R02C02"] == 0
```

**Verify RED:** run each test by name.

**GREEN implementation:**

- Add `place_hazards(cell_ids, hazard_count, seed)` using `random.Random(seed).sample(...)`.
- Add `compute_neighbor_counts(cell_ids, hazards, adjacency)`.
- Store `0` for hazard cells to avoid hazard labels/clues.

---

### Task 4: New game initialization

**Objective:** Produce a complete in-memory game ready for ArcPy persistence later.

**RED test:**

```python
def test_new_game_initializes_hidden_playing_state():
    game = rules.new_game("Tiny Demo", seed=2026)

    assert len(game.cells) == 25
    assert sum(len(links) for links in game.adjacency.values()) == 144
    assert game.state.status == "playing"
    assert game.state.seed == 2026
    assert game.state.safe_revealed_count == 0
    assert game.state.flags_count == 0
    assert game.state.action_count == 0
    assert game.state.hazard_count == 4
    assert all(not cell.revealed for cell in game.cells.values())
    assert all(not cell.flagged for cell in game.cells.values())
    assert {cell.display_state for cell in game.cells.values()} == {"hidden"}
```

**Verify RED:** run by name.

**GREEN implementation:**

- Add mutable `CellState` dataclass matching future `GameBoard` fields.
- Add `GameState` dataclass matching future `GameState` keys.
- Add `SurveySweeperGame` dataclass.
- Add `new_game(...)`.
- Add `refresh_display_states(...)` and `display_state_for_cell(...)` minimum hidden mapping.

---

### Task 5: Reveal safe clue, safe empty, and hazard loss

**Objective:** Lock single-cell reveal behavior before adding any ArcPy store code.

**RED tests:**

- Safe clue reveal sets:
  - `revealed=True`
  - `turn_revealed=1`
  - `display_state='revealed_clue'`
  - `safe_revealed_count=1`
  - `action_count=1`
  - status remains `playing`
  - result message includes `Reveal / Scout`, selected cell ID, `Selection cursor`, `Adjacency lookup`

- Safe empty reveal sets:
  - `display_state='revealed_empty'`
  - exactly one cell revealed; no flood reveal in MVP

- Hazard reveal sets:
  - status `lost`
  - hit hazard `hazard_hit`
  - other hazards `hazard_revealed`
  - result message includes `LOST`

**Verify RED:** run each reveal test by name.

**GREEN implementation:**

- Add `ActionResult` dataclass.
- Add `reveal_cells(game, selected_cell_ids)`.
- Enforce one selected cell exactly.
- Mutate only after all validation passes.
- Increment `action_count` only for successful reveals.
- Recompute display states after mutation.

---

### Task 6: Reveal validation remains atomic

**Objective:** Ensure invalid reveal actions do not mutate state.

**RED test cases:**

- no selected cells rejects with `Select exactly one`
- multiple selected cells rejects with `Select exactly one`
- unknown selected cell rejects with `Unknown cell`
- flagged selected cell rejects with `flagged`
- terminal game state rejects with `status is lost` or `status is won`

Use a helper:

```python
def _assert_no_mutation(game, action, expected_message):
    before = copy.deepcopy(game)
    result = action()
    assert result.ok is False
    assert expected_message in result.message
    assert game == before
```

**GREEN implementation:**

- Add `_validate_can_mutate(...)`.
- Add `_error(...)` result helper.
- Perform all selection/cell legality checks before mutation.

---

### Task 7: Flag toggle and flag validation

**Objective:** Define one-or-many `Flag / Mark` behavior.

**RED tests:**

- one or more unrevealed cells toggle `flagged`.
- repeated flag toggles back off.
- `flags_count` updates.
- `action_count` increments per successful flag action.
- result includes `Flag / Mark`, `Selection cursor`, `Field update`, `Display state`.
- no selection rejects.
- unknown cell rejects atomically.
- revealed cell rejects atomically.
- terminal game rejects.

**GREEN implementation:**

- Add `flag_cells(game, selected_cell_ids)`.
- Deduplicate selection while preserving order.
- Validate all selected cells first.
- Mutate only after validation.

---

### Task 8: Win condition and display precedence

**Objective:** Lock terminal state and symbology-facing categories.

**RED tests:**

- revealing last safe cell sets status `won`.
- revealed safe cells map to `won_safe` after win.
- unrevealed hazard stays `hidden` after win.
- `hazard_hit` beats `hazard_revealed`.
- lost non-hit hazards map to `hazard_revealed`.
- flagged unrevealed maps to `flagged` before hidden.

**GREEN implementation:**

- Add `_all_safe_cells_revealed(...)`.
- Implement full `display_state_for_cell(...)` precedence:
  1. won safe revealed → `won_safe`
  2. hazard hit → `hazard_hit`
  3. lost hazard → `hazard_revealed`
  4. flagged unrevealed → `flagged`
  5. unrevealed → `hidden`
  6. revealed with `neighbor_count == 0` → `revealed_empty`
  7. revealed with `neighbor_count > 0` → `revealed_clue`

---

### Task 9: Action-result/log/message contract

**Objective:** Make future ArcPy GP messages and `ActionLog` rows easy to wire.

**RED tests:**

- successful actions return:
  - `ok=True`
  - `action`
  - `changed_cell_ids`
  - `message`
  - `gp_operations`
  - `log_payload`
  - `refresh_required=True`
- failed validation returns:
  - `ok=False`
  - no mutation
  - `refresh_required=False`
- successful `log_payload` includes:
  - `action`
  - `target_cell_ids`
  - `result`
  - `gp_operation`
  - `status`
  - `action_count`

**GREEN implementation:**

- Centralize `_success(...)` and `_error(...)` helpers.
- Do not overfit messages in tests. Check for key fragments and operations, not exact full prose.

---

### Task 10: Golden seed for demo script

**Objective:** Freeze one deterministic 5×5 demo layout.

**RED test:**

```python
def test_golden_seed_2026_is_stable_for_demo_script():
    game = rules.new_game("Tiny Demo", seed=2026)
    hazards = sorted(cid for cid, cell in game.cells.items() if cell.is_hazard)

    assert hazards == ["R00C03", "R02C00", "R03C01", "R04C00"]
    assert game.cells["R00C00"].neighbor_count == 0
    assert game.cells["R00C02"].neighbor_count == 1

    safe_result = rules.reveal_cells(game, ["R00C00"])
    assert safe_result.ok is True
    assert game.cells["R00C00"].display_state == "revealed_empty"

    loss_result = rules.reveal_cells(game, ["R00C03"])
    assert loss_result.ok is True
    assert game.state.status == "lost"
    assert game.cells["R00C03"].display_state == "hazard_hit"
```

**GREEN implementation:**

- Prefer no code change if the deterministic placement is already stable.
- If placement changes, update this test only with intentional approval because it affects demo docs.

---

## Phase 2 — Gaps / Hardening Tests Before ArcPy Integration

These should be added only after Phase 1 is green.

### Task 11: Add compact game summary helper

**Objective:** Provide a pure helper for future `Show Score` action.

**RED test:**

```python
def test_summarize_game_reports_score_fields_for_show_score():
    game = rules.new_game("Tiny Demo", seed=2026)
    rules.reveal_cells(game, ["R00C00"])
    rules.flag_cells(game, ["R00C03"])

    summary = rules.summarize_game(game)

    assert summary["mode"] == "survey"
    assert summary["status"] == "playing"
    assert summary["seed"] == 2026
    assert summary["safe_revealed_count"] == 1
    assert summary["total_safe_count"] == 21
    assert summary["flags_count"] == 1
    assert summary["hazard_count"] == 4
    assert summary["action_count"] == 2
    assert "last_message" in summary
```

**Verify RED:**

```bash
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py::test_summarize_game_reports_score_fields_for_show_score -v
```

**GREEN implementation:**

- Add `summarize_game(game) -> dict[str, int | str]`.
- Keep it pure and ArcPy-free.

**Commit checkpoint:**

```bash
git add tests/test_minesweeper_rules.py toolbox/arcpy_game_rules.py
git commit -m "feat: add Survey Sweeper score summary"
```

---

### Task 12: Add explicit serialize/deserialize boundary only if needed

**Objective:** Prepare for ArcPy store without importing ArcPy.

Only do this if Milestone 2 store integration needs a stable contract.

**RED test idea:**

- `cell_to_record(cell)` returns field-compatible values for `GameBoard`.
- `record_to_cell(row_dict)` reconstructs `CellState`.
- Boolean-like fields are plain `0/1` or `bool` according to store needs.

**Caution:** Do not overbuild this until schema/store code needs it. YAGNI.

---

## Phase 3 — TDD Plan for ArcPy Integration Milestone

After pure rules are green and committed, move to Milestone 2 with the same discipline.

### Task 13: Plan fake-store action tests before real ArcPy

**Objective:** Test controller/action orchestration without ArcPy.

**Files likely created later:**

- `toolbox/arcpy_game_actions.py`
- `tests/test_action_contracts.py`

**TDD idea:**

- Define an `ActionContext` that carries selected `cell_id`s, action name, game state, and params.
- Define action handlers that call pure rules.
- Use a fake in-memory store rather than ArcPy.

**Acceptance:**

- `Reveal / Scout` handler calls `rules.reveal_cells`.
- `Flag / Mark` handler calls `rules.flag_cells`.
- Every mutating handler returns an `ActionResult` ready for GP messages/logging.

### Task 14: TDD schema definitions with an ArcPy adapter boundary

**Objective:** Make schema idempotency testable without requiring ArcPy for every assertion.

**Files likely created later:**

- `toolbox/arcpy_game_schema.py`
- `tests/test_schema_contract.py`

**TDD idea:**

- Unit-test field/index definition lists as pure data.
- ArcPy smoke tests can later verify `ensure_schema()` inside ArcGIS Pro.

**Critical spike-informed tests:**

- index existence check should look for any index covering `cell_id`, not just a name.
- `ensure_schema()` and `assert_schema()` are separate.
- `assert_schema()` must not mutate.

### Task 15: TDD selected-cell store contract with fake rows first

**Objective:** Encode the spike finding: cursor-over-layer is primary path; FIDSet is fallback/diagnostic.

**Files likely created later:**

- `toolbox/arcpy_game_store.py`
- `tests/test_store_contract.py`

**TDD idea:**

- Unit-test pure helpers that convert selected row dictionaries into `cell_id`s.
- Do not import ArcPy in pure unit tests.
- Add ArcPy manual smoke test later for real cursor-over-selected-layer behavior.

---

## Commit Strategy

Use reviewable checkpoints:

1. Baseline pure rules green:

```bash
git add tests/test_minesweeper_rules.py toolbox/arcpy_game_rules.py toolbox/__init__.py
 git commit -m "feat: add Survey Sweeper pure rules"
```

2. TDD plan/docs:

```bash
git add .hermes/plans/2026-05-09_221347-survey-sweeper-tdd-plan.md ideas/survey-sweeper-milestone-1-implementation-plan.md
 git commit -m "docs: add Survey Sweeper TDD plan"
```

3. Any new hardening behavior:

```bash
git add tests/test_minesweeper_rules.py toolbox/arcpy_game_rules.py
 git commit -m "feat: add Survey Sweeper score summary"
```

4. Milestone 2 planning/tests:

```bash
git add tests/test_action_contracts.py tests/test_schema_contract.py toolbox/arcpy_game_actions.py toolbox/arcpy_game_schema.py
 git commit -m "feat: add Survey Sweeper ArcPy integration contracts"
```

Remove the accidental leading spaces in the example commands before copy/pasting if your shell treats them specially.

---

## Done Criteria

Milestone 1 pure rules are done when:

- `uv run --with pytest python -m pytest tests/test_minesweeper_rules.py -q` passes.
- `python -m py_compile toolbox/arcpy_game_rules.py tests/test_minesweeper_rules.py` passes.
- `toolbox/arcpy_game_rules.py` imports without ArcPy.
- Tests cover:
  - stable IDs,
  - presets,
  - adjacency,
  - deterministic hazards,
  - neighbor counts,
  - new-game state,
  - safe reveal,
  - hazard reveal,
  - reveal validation atomicity,
  - flag toggles,
  - flag validation atomicity,
  - win/loss,
  - display-state precedence,
  - action-result/log/message contract,
  - golden demo seed.
- No behavior was added after this point without first watching a test fail.

Milestone 2 can begin only after Milestone 1 is green and committed.
