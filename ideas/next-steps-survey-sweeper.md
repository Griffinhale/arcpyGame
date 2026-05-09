# Next Steps — Survey Sweeper Phase

Date: 2026-05-09

Purpose: define the immediate path after the successful ArcGIS Pro feasibility spike.

## Decision

Proceed to **Survey Sweeper / Minesweeper Minimum**.

Do not start Containment Commander yet. Do not add Bufferlands powers yet. The next goal is a shippable fallback: a polished Survey Sweeper game that proves the architecture end-to-end.

---

## Immediate Sequence

### Step 1 — Freeze Milestone 1 scope

Milestone 1 is pure Python rule logic only. It should not import ArcPy.

Build:
- cell ID generation,
- square board generation,
- 8-way adjacency,
- deterministic hazard placement,
- neighbor clue counts,
- reveal action,
- flag/unflag action,
- win/loss checks,
- display-state mapping.

Defer:
- ArcPy schema/store/controller,
- `.lyrx` symbology,
- flood reveal,
- synthetic risk sources,
- real data,
- Containment Commander.

### Step 2 — Create first implementation plan

Write a task-by-task TDD plan for Milestone 1 at:

`docs/plans/2026-05-09-survey-sweeper-rules.md`

The plan should be bite-sized and include exact tests before production code.

### Step 3 — Implement with strict TDD

Create:
- `toolbox/arcpy_game_rules.py`
- `tests/test_minesweeper_rules.py`

Expected first test order:
1. `cell_id_for(row, col)` returns zero-padded IDs like `R00C00`.
2. `generate_cell_ids(rows, cols)` creates row-major IDs.
3. `build_square_adjacency(rows, cols)` handles corner/edge/center neighbor counts.
4. deterministic hazard placement from seed.
5. neighbor clue counts.
6. reveal safe cell.
7. reveal hazard loses game and reveals hazards.
8. flag toggle.
9. win by revealing all safe cells.
10. display-state mapping.

### Step 4 — Commit after the pure rules are green

Suggested commit:

```bash
git add toolbox/arcpy_game_rules.py tests/test_minesweeper_rules.py docs/plans/2026-05-09-survey-sweeper-rules.md
git commit -m "feat: add Survey Sweeper rule logic"
```

### Step 5 — Then build ArcPy integration

Only after Milestone 1 tests are green, move to:

- `arcpy_game_schema.py`
- `arcpy_game_store.py`
- `arcpy_game_display.py`
- production `arcpy_game.pyt`

Primary spike-informed rule:

> Use cursor-over-selected-`GPFeatureLayer` as the normal selected-cell path; keep FIDSet parsing only as diagnostics/fallback.

---

## Recommended First Artifact to Write Next

`docs/plans/2026-05-09-survey-sweeper-rules.md`

It should answer:
- What exact API should `arcpy_game_rules.py` expose?
- What tests define correctness?
- What is the minimal state representation outside ArcPy?
- How does this pure model map to future geodatabase fields?

---

## Proposed Pure Rules API

This API is intentionally boring and testable:

```python
@dataclass(frozen=True)
class Cell:
    cell_id: str
    row: int
    col: int
    is_hazard: bool = False
    revealed: bool = False
    flagged: bool = False
    neighbor_count: int = 0
    hit: bool = False

@dataclass(frozen=True)
class SurveyGame:
    rows: int
    cols: int
    hazard_count: int
    seed: int
    status: str
    action_count: int
    cells: dict[str, Cell]
    adjacency: dict[str, list[str]]


def cell_id_for(row: int, col: int) -> str: ...
def generate_cell_ids(rows: int, cols: int) -> list[str]: ...
def build_square_adjacency(rows: int, cols: int) -> dict[str, list[str]]: ...
def new_survey_game(rows: int, cols: int, hazard_count: int, seed: int) -> SurveyGame: ...
def reveal_cells(game: SurveyGame, cell_ids: list[str]) -> SurveyGame: ...
def toggle_flags(game: SurveyGame, cell_ids: list[str]) -> SurveyGame: ...
def display_state_for(cell: Cell, game_status: str) -> str: ...
def summarize_game(game: SurveyGame) -> dict[str, int | str]: ...
```

Use immutable-ish dataclasses for tests, even if ArcPy integration later writes mutable geodatabase rows.

---

## Acceptance Criteria for This Next Slice

Milestone 1 is done when:

- `pytest tests/test_minesweeper_rules.py -q` passes.
- No ArcPy import is required.
- A deterministic 5×5 / 4 hazard game can be created.
- Safe reveals, hazard reveals, flagging, win/loss, and display-state mapping are covered by tests.
- The code can be called later from ArcPy action handlers without depending on map/layer objects.

---

## After Milestone 1

Next phase will be **Milestone 2: Schema / Store / Display Foundation**:

- Create gdb/datasets.
- Add fields and indexes idempotently.
- Store/retrieve `SurveyGame` state in `GameBoard`, `GameState`, `Adjacency`, and `ActionLog`.
- Preserve layer references on reset by clearing rows instead of deleting feature classes.

Then **Milestone 3: Playable Survey Sweeper in ArcGIS Pro**:

- production `.pyt`,
- `New Game`,
- `Reveal / Scout`,
- `Flag / Mark`,
- `Show Score`,
- `Reset`.
