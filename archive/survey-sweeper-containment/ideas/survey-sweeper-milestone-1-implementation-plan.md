# Survey Sweeper Milestone 1 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill for future multi-agent implementation. For this session, implement the pure rules directly with strict TDD: tests first, verify RED, then implementation.

**Goal:** Build the pure-Python Survey Sweeper / minesweeper rule engine that can run outside ArcGIS Pro and later be wired into the ArcPy toolbox.

**Architecture:** Keep all Stage 1 gameplay logic in `toolbox/arcpy_game_rules.py` with no `arcpy` import. Represent board cells as dataclasses keyed by stable `cell_id`; return explicit action-result objects that use `cell_id`s only. ArcPy schema/store/controller modules will consume these pure functions later.

**Tech Stack:** Python 3.11+, stdlib dataclasses, pytest via `uv run --with pytest pytest ...`. No ArcPy dependency in Milestone 1.

---

## Scope Decisions Frozen for Milestone 1

- Board presets:
  - `Tiny Demo`: 5×5, 4 hazards.
  - `Small`: 7×7, 8 hazards.
- Stable cell IDs: zero-padded text IDs such as `R00C00`.
- Adjacency: 8-way directed pairs for Survey Sweeper.
- Reveal: exactly one selected cell in MVP.
- Flag: one or many selected cells, atomic validation.
- Win: reveal all safe cells.
- Loss: reveal a hazard.
- Deferred: flood reveal, first-click safety, exact-flag win, risk-source bias, real data, Feature Set drawing, ArcPy schema/store/controller.

---

## Files

Create:

- `toolbox/arcpy_game_rules.py`
- `tests/test_minesweeper_rules.py`

Later milestones will create:

- `toolbox/arcpy_game_schema.py`
- `toolbox/arcpy_game_store.py`
- `toolbox/arcpy_game_display.py`
- `toolbox/arcpy_game.pyt`

---

## Task 1: Test cell IDs and board presets

**Objective:** Define stable board identity and preset contracts.

**Test file:** `tests/test_minesweeper_rules.py`

**Steps:**

1. Write tests for `cell_id`, `generate_cell_ids`, and `get_board_preset`.
2. Run:
   ```bash
   uv run --with pytest python -m pytest tests/test_minesweeper_rules.py -q
   ```
   Expected RED: import or symbol failure.
3. Implement minimal code in `toolbox/arcpy_game_rules.py`.
4. Re-run tests until green.

Acceptance:

- 5×5 creates 25 IDs.
- First ID is `R00C00`; last is `R04C04`.
- `Tiny Demo` = rows 5, cols 5, hazards 4.
- `Small` = rows 7, cols 7, hazards 8.
- Unknown preset raises `ValueError`.

---

## Task 2: Test 8-way adjacency

**Objective:** Define Survey Sweeper neighbor graph.

Tests:

- Corner has 3 neighbors.
- Edge non-corner has 5 neighbors.
- Center has 8 neighbors.
- No self-neighbor.
- No duplicate neighbor IDs per cell.
- `touch_type` is `edge` for orthogonal and `corner` for diagonal.
- 5×5 directed pair count is 144.

Implementation:

- `build_adjacency(rows, cols) -> dict[str, list[AdjacencyLink]]`
- `AdjacencyLink(neighbor_id, touch_type, weight=1.0)`

---

## Task 3: Test deterministic hazard placement and neighbor counts

**Objective:** Define seeded hazard layout and clue numbers.

Tests:

- Same seed gives same hazards.
- Hazard count exact.
- No duplicate hazards.
- All hazards are valid cell IDs.
- Hand-authored 3×3 board with hazards at opposite corners produces expected counts.

Implementation:

- `place_hazards(cell_ids, hazard_count, seed) -> set[str]`
- `compute_neighbor_counts(cell_ids, hazards, adjacency) -> dict[str, int]`

---

## Task 4: Test new game state

**Objective:** Produce a complete in-memory game state for later ArcPy persistence.

Tests:

- `new_game('Tiny Demo', seed=2026)` returns 25 cells and 144 adjacency links.
- All cells are unrevealed and unflagged.
- All cells initially map to `hidden`.
- Counts/status: `safe_revealed_count=0`, `flags_count=0`, `action_count=0`, `status='playing'`.

Implementation:

- `CellState`
- `GameState`
- `SurveySweeperGame`
- `new_game(...)`
- `display_state_for_cell(...)`
- `refresh_display_states(...)`

---

## Task 5: Test reveal safe, reveal empty, and reveal hazard

**Objective:** Define single-cell reveal behavior.

Tests:

- Revealing a safe clue cell sets `revealed=1`, increments count/action count, returns `revealed_clue`.
- Revealing a safe zero-neighbor cell sets `revealed_empty`; no flood reveal.
- Revealing a hazard sets status `lost`, hit cell `hazard_hit`, other hazards `hazard_revealed`.
- Reveal with zero selected cells rejects.
- Reveal with multiple selected cells rejects.
- Reveal flagged cell rejects without mutation.
- Reveal after win/loss rejects without mutation.

Implementation:

- `reveal_cells(game, selected_cell_ids) -> ActionResult`
- Atomic validation before mutation.

---

## Task 6: Test flag toggle and illegal actions

**Objective:** Define one-or-many flag behavior.

Tests:

- Flag toggles unrevealed cells 0→1→0.
- Multi-cell flag works.
- Mixed legal/illegal selection rejects atomically.
- Cannot flag revealed cells.
- Cannot flag after won/lost.
- Unknown cell rejects.

Implementation:

- `flag_cells(game, selected_cell_ids) -> ActionResult`

---

## Task 7: Test win condition and display precedence

**Objective:** Lock final game-state semantics.

Tests:

- Revealing last safe cell sets `status='won'`.
- Won safe cells map to `won_safe`.
- `hazard_hit` beats generic hazard reveal.
- Lost hazards map to `hazard_revealed`.
- Flagged unrevealed maps to `flagged` before `hidden`.

Implementation:

- Ensure `display_state_for_cell` uses explicit precedence.
- Ensure reveal win path refreshes display states.

---

## Task 8: Test action-result/message contract

**Objective:** Make future ArcPy messages/logs easy to wire.

Tests:

- Successful actions return `ok=True`, `changed_cell_ids`, `message`, `gp_operations`, and `log_payload`.
- Failed validation returns `ok=False` and does not mutate the game.
- Messages include action name and selected cell IDs/count.
- Messages name at least one GIS/data operation such as `Selection cursor`, `Adjacency lookup`, `Field update`, or `Display state`.

Implementation:

- `ActionResult` dataclass.
- Consistent message templates that are human-readable but not overfit in tests.

---

## Task 9: Golden seed test

**Objective:** Freeze one deterministic demo seed for docs and regression.

Tests:

- `new_game('Tiny Demo', seed=2026)` has a known hazard set.
- At least one known safe reveal and one known hazard/loss cell are documented in the test.

Implementation:

- No special code unless deterministic placement needs adjustment.

---

## Verification Commands

Run pure test suite:

```bash
uv run --with pytest python -m pytest tests/test_minesweeper_rules.py -q
```

Run syntax check:

```bash
python -m py_compile toolbox/arcpy_game_rules.py tests/test_minesweeper_rules.py
```

Confirm no ArcPy dependency:

```bash
python - <<'PY'
import toolbox.arcpy_game_rules as r
print(r.__name__)
PY
```

---

## Commit Checkpoints

After plan only:

```bash
git add ideas/survey-sweeper-minesweeper-phase-brainstorm.md ideas/survey-sweeper-second-opinion-test-plan.md ideas/survey-sweeper-milestone-1-implementation-plan.md
git commit -m "docs: plan Survey Sweeper rules milestone"
```

After pure rules green:

```bash
git add toolbox/arcpy_game_rules.py tests/test_minesweeper_rules.py
git commit -m "feat: add Survey Sweeper pure rules"
```

---

## Done Criteria

Milestone 1 is done when:

- All pure Python tests pass outside ArcGIS Pro.
- `toolbox/arcpy_game_rules.py` imports without ArcPy.
- Action results use stable `cell_id`s only.
- Rules do not know about OIDs, FIDs, feature classes, layers, or symbology files.
- The implementation is ready for fake-store action tests and ArcPy schema/store integration in Milestone 2.
