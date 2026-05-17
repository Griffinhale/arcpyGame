# Survey Sweeper Second Opinion — Plan Critique and Test Matrix

Date: 2026-05-09

## Purpose

Second-opinion synthesis on `ideas/survey-sweeper-minesweeper-phase-brainstorm.md`, considering:

- fit with the broader Minesweeper → Containment Commander → Bufferlands plan,
- whether the Survey Sweeper fallback is scoped correctly,
- which ArcPy / ArcGIS Pro behaviors still need evidence,
- which automated and manual tests should be written before implementation.

Method: three independent review lenses were used:

1. ArcGIS Pro / ArcPy domain expert.
2. Implementation lead / TDD planner.
3. Adversarial product-demo QA auditor.

Artifacts reviewed:

- `ideas/survey-sweeper-minesweeper-phase-brainstorm.md`
- `ideas/minesweeper-to-containment-implementation-plan-v2.md`
- `ideas/feasibility-spike-results.md`

---

## Executive Summary

The panel strongly agrees that **Survey Sweeper is a feasible, well-scoped fallback submission** and a good architectural stepping stone toward Containment Commander. The feasibility spike materially de-risked the core ArcGIS Pro loop: Python toolbox loading, staged parameters, map selection input, selected-layer cursors, field updates, reset via `DeleteRows`, and memory buffer/select all passed.

The main critique is not “this will not work.” The critique is: **the plan needs sharper contracts before coding** so the playable fallback does not become brittle in a live class demo and does not accidentally overbuild toward Containment too early.

Highest-priority changes:

1. Treat `.lyrx` / display-state rendering as a milestone gate, not late polish.
2. Update stale plan language that still implies FIDSet-first selection; cursor-over-selected-layer should be primary.
3. Add explicit wrong-layer / stale-layer / session validation.
4. Keep MVP reveal single-cell only; allow multi-cell flag if easy.
5. Defer flood reveal, first-click safety, exact-flag win, risk bias, Feature Set drawing, and real data.
6. Add reusable pure-Python contracts: stable IDs, adjacency shape, action result shape, display mapper precedence, GameState keys.
7. Promote golden seed into a regression harness and operator demo runbook.
8. Do not start Containment Commander until Survey Sweeper passes a cold-start fallback-lock checklist.

Consensus level: **strong consensus**.

---

## Consensus Strengths

- **Spike findings were correctly incorporated.** The brainstorm uses the most important discovery: `arcpy.da.SearchCursor(layer, ...)` and `arcpy.da.UpdateCursor(layer, ...)` respect map selections in Pro 3.6.
- **Fallback-first staging is sound.** Polished Survey Sweeper is a valid endpoint if Containment Commander slips.
- **Small board sizes are correct.** 5×5 first, 7×7 second. No medium boards until demo timing is proven.
- **Data model is ArcGIS-friendly.** Stable `cell_id`, `SHORT` booleans, file geodatabase tables, `display_state` as renderer-only, no durable OID dependence.
- **Reset strategy is validated.** Keep FC/table names stable and clear/reseed rows; do not delete displayed feature classes during normal reset.
- **Pure rules before ArcPy integration is the right sequencing.** Survey Sweeper rules should run outside ArcGIS Pro first.
- **Survey Sweeper reuses the same architecture Containment needs.** Board cells, adjacency, selected-cell actions, action logs, GameState, display mapping, and GP controller all carry forward.
- **Operation-aware messages are a cheap win.** They make the demo read as GIS-native rather than a generic game drawn on polygons.

---

## Main Concerns

### 1. Plan inconsistency: selection contract

The brainstorm correctly says cursor-over-selected-layer should be the primary path. The broader v2 plan still contains FIDSet-first language in places.

Decision: update implementation guidance before coding:

- Primary path: cursor directly over selected `GPFeatureLayer`.
- Diagnostics: log `Describe(layer).FIDSet` and selected count.
- Fallback: explicit OID/FID parsing only for diagnostics or exceptional cases.

### 2. Wrong/stale layer handling is under-specified

The spike validated a happy-path layer. It did not fully validate:

- wrong layer passed,
- duplicated layer,
- renamed layer,
- stale workspace,
- layer with definition query,
- selected rows from an old/reset board,
- no selection accidentally becoming all-row cursor behavior.

Recommendation: add `game_id` / `session_id` to `GameBoard`, `GameState`, and `ActionLog`. Reject selected rows whose `game_id` does not match current `GameState`.

### 3. Symbology is a hard dependency for demo quality

The spike only got automatic redraw after unique-value priming. A pre-classed `.lyrx` is not polish; it is the UI layer.

Gate before Containment:

- fresh Pro session,
- apply/load `.lyrx`,
- run `New Game`,
- reveal/flag/loss/win,
- close/reopen,
- confirm all states render without “Add unlisted values.”

### 4. Labels could become a time sink

Clue labels are nice, but not mandatory. If label expressions get brittle, use a simple `label_text` field or `notes` fallback:

- hidden / flagged / hazard cells: empty label,
- revealed clue cells: neighbor count string,
- revealed empty cells: empty or dot.

### 5. Multi-reveal increases accidental demo risk

Recommendation for MVP:

- `Reveal / Scout`: exactly one selected unrevealed, unflagged cell.
- `Flag / Mark`: one or many selected unrevealed cells allowed.

This reduces accidental loss, validation complexity, and action atomicity edge cases.

### 6. Reset should clear selection

Retaining selection during reveal/flag is acceptable if repeated illegal actions are blocked. Retaining selection across `New Game` / `Reset` is demo-risky.

Recommended policy:

- `New Game` / `Reset`: clear selection and message “Selection cleared; choose a parcel.”
- `Reveal` / `Flag`: retain selection after success for now, but reject already-revealed / flagged misuse.
- On error: leave selection intact so the operator can fix it.
- On win/loss: block mutating actions; clearing selection optional.

### 7. GameState contract needs to be typed and tested

One-row-per-key is acceptable for ArcPy, but tests need to define:

- required keys,
- text vs numeric storage,
- status enum,
- missing-key behavior,
- action count semantics,
- mode-specific keys for future Containment reuse.

### 8. Action orchestration needs fake-store tests

Pure rules alone are not sufficient. The risky boundary is:

- validate selection,
- load board/state/adjacency,
- apply rule,
- recompute display state,
- write changed cells,
- write GameState,
- append ActionLog,
- emit GP messages,
- signal refresh.

Most of this can be tested without ArcPy using a fake store and fake message sink.

---

## Recommended Scope Decisions for Survey Sweeper MVP

Adopt:

- 5×5 `Tiny Demo`, 4 hazards.
- 7×7 `Small`, 8 hazards only after 5×5 is stable.
- Zero-based stable IDs: `R00C00` through `R04C04` for 5×5.
- 8-way adjacency, directed pairs in `Adjacency` table.
- `touch_type` on adjacency: `edge` vs `corner`.
- Deterministic hazard placement from seed.
- Win by revealing all safe cells.
- Loss by revealing a hazard.
- Single-cell reveal only.
- Multi-cell flag toggle if validation stays simple.
- `display_state` as derived output only.
- `label_text` fallback if label expressions are annoying.
- `game_id` / `session_id` for stale-selection protection.
- Golden seed as both automated test and demo script source.

Defer / reject for MVP:

- flood reveal,
- first-click safety,
- exact-flag win condition,
- risk-source-biased hazards,
- real data,
- Feature Set drawing,
- geometry/topology-derived adjacency,
- runtime symbology authoring beyond applying prebuilt `.lyrx`,
- medium boards,
- complex scoring,
- generalized action engine,
- Containment code before Survey Sweeper fallback lock.

---

## Proposed Stage Gates

### Gate A — Milestone 1 Pure Rules Green

Done when pure Python tests pass for:

- cell IDs,
- board presets,
- adjacency,
- hazard placement,
- neighbor counts,
- initial state,
- reveal safe clue,
- reveal safe empty,
- reveal hazard loss,
- flag toggle,
- illegal actions,
- win condition,
- display-state precedence,
- golden seed layout.

### Gate B — Action Contract Green Without ArcPy

Done when fake-store tests prove:

- `New Game` writes board/state/adjacency/log,
- `Reveal` validates selected cells and writes exact changed rows,
- `Flag` validates selected cells and writes exact changed rows,
- `Show Score` works without selection,
- failed validation does not mutate board,
- ordinary actions call `assert_schema`, not `ensure_schema`,
- messages include required GIS/game facts.

### Gate C — ArcPy Store / Schema Green

Done when Pro-Python integration tests prove:

- gdb and datasets are created idempotently,
- fields and indexes are idempotent,
- `DeleteRows` reset preserves paths,
- board/state/adjacency/log roundtrip works,
- selected-layer cursors return only selected rows,
- wrong/stale layer fails safely.

### Gate D — Survey Sweeper Fallback Lock

Do not start Containment Commander until this passes from a cold Pro start:

1. Open project.
2. Load toolbox without red-X / corruption.
3. Run `New Game`.
4. Confirm 25 hidden board cells render with prebuilt `.lyrx`.
5. Reveal known safe cell.
6. Flag/unflag known cell.
7. Show Score.
8. Trigger loss path.
9. Reset.
10. Trigger win or near-win path.
11. Close/reopen project.
12. Run abbreviated smoke test.
13. Confirm demo script can run under time limit.

---

## Test Matrix

## A. Pure Python Tests — No ArcPy

### P0: Required before production rules

- Cell ID generation:
  - 5×5 produces 25 unique IDs.
  - first = `R00C00`, last = `R04C04`.
  - lexical sort matches board order.

- Board presets:
  - `Tiny Demo` = 5×5, 4 hazards.
  - `Small` = 7×7, 8 hazards.
  - invalid preset raises clean error.

- 8-way adjacency:
  - corner has 3 neighbors.
  - edge non-corner has 5 neighbors.
  - center has 8 neighbors.
  - no self-neighbor.
  - no duplicate neighbor IDs per cell.

- Adjacency metadata:
  - orthogonal neighbor = `edge`.
  - diagonal neighbor = `corner`.
  - optional weight defaults to `1.0`.

- Directed adjacency count:
  - 5×5 has 144 directed pairs:
    - 4 corners × 3 = 12,
    - 12 edge non-corners × 5 = 60,
    - 9 centers × 8 = 72.

- Deterministic hazards:
  - same seed => same hazard set.
  - hazard count exact.
  - no duplicates.
  - all hazards are valid cell IDs.

- Neighbor counts:
  - hand-authored board verifies clue counts.
  - define whether hazard cells also store neighbor counts; test chosen behavior.

- Initial state:
  - all cells unrevealed.
  - all cells unflagged.
  - all cells map to `hidden`.
  - `safe_revealed_count=0`.
  - `flags_count=0`.
  - `action_count=0`.
  - status is chosen and tested, likely `playing` after `New Game`.

- Reveal safe clue:
  - selected cell becomes revealed.
  - `turn_revealed` set.
  - safe revealed count increments.
  - status remains `playing` unless final safe cell.
  - display maps to `revealed_clue`.

- Reveal safe empty:
  - selected safe zero-neighbor cell becomes revealed.
  - no flood reveal in MVP.
  - display maps to `revealed_empty`.

- Reveal hazard loss:
  - status becomes `lost`.
  - hit cell maps to `hazard_hit`.
  - other hazards map to `hazard_revealed`.
  - later mutating actions reject.

- Flag toggle:
  - unrevealed cell toggles `flagged` 0→1→0.
  - flags count updates.
  - flagged unrevealed maps to `flagged`.

- Illegal action rejection:
  - cannot reveal flagged cell.
  - cannot flag revealed cell.
  - cannot reveal/flag after won/lost.
  - unknown cell ID rejects cleanly.
  - state remains unchanged on failed validation.

- Win by safe reveal:
  - last safe reveal sets status `won`.
  - safe revealed count equals total safe.
  - safe/revealed cells map to `won_safe`.

- Display-state precedence:
  - `hazard_hit` beats `hazard_revealed`.
  - lost hazards reveal.
  - flagged unrevealed maps before hidden.
  - hidden unrevealed maps to `hidden`.
  - won safe maps to `won_safe`.
  - game rules do not inspect `display_state`.

### P1: Required before ArcPy integration

- Action result shape:
  - stable `changed_cell_ids`, no OIDs.
  - status / ok / message / log payload present.

- Multi-selection policy:
  - reveal with more than one selected cell rejects.
  - flag supports multiple cells or explicitly rejects; chosen behavior tested.
  - mixed legal/illegal selection is atomic: no partial mutation.

- Action count policy:
  - successful reveal increments.
  - successful flag increments.
  - failed validation either increments or not; choose and test.

- Message contract:
  - contains action name.
  - contains selected cell ID(s) or count.
  - names at least one GIS operation: selection cursor, adjacency lookup, field update, display-state recompute.
  - exact full strings should not be overfit; test required substrings.

- Golden seed regression:
  - exact seed.
  - exact hazard cells.
  - known safe first reveal.
  - known hazard/loss cell.
  - expected clue counts for demo cells.

### P2: Parked until MVP is stable

- flood reveal BFS,
- first-click safety,
- exact-flag win,
- risk-source-biased hazards,
- geometry-derived adjacency.

---

## B. Pure Action / Controller Tests with Fake Store

These run without ArcPy and protect future Containment reuse.

- New Game action:
  - calls setup path,
  - clears/reseeds store,
  - writes board rows,
  - writes adjacency,
  - writes GameState,
  - appends initial ActionLog,
  - returns refresh required.

- Reveal happy path:
  - reads selected IDs from store,
  - loads board/state/adjacency,
  - applies rule,
  - writes changed cells only,
  - writes GameState,
  - appends exactly one log row,
  - emits GIS-native message.

- Reveal no selection:
  - no board mutation,
  - warning/error result,
  - no accidental cursor over all rows.

- Reveal wrong/stale cell:
  - selected ID not in current board rejects clearly.

- Flag happy path:
  - writes toggled cells,
  - updates flags count,
  - appends one log row.

- Show Score:
  - no selection required,
  - no board mutation,
  - message reports status, seed, counts, last message.

- Schema boundary:
  - `New Game` / `Reset` call `ensure_schema`.
  - `Reveal` / `Flag` / `Show Score` call `assert_schema` only.
  - no schema mutation during ordinary turns.

---

## C. ArcPy Data / Integration Tests

Run only in ArcGIS Pro Python environment.

### A0: Schema and persistence

- Create file geodatabase if missing; rerun idempotently.
- Create `GameBoard`, `GameState`, `Adjacency`, `ActionLog`.
- Required fields exist with correct types/lengths where practical.
- Field aliases exist for demo-readable fields.
- Index idempotency:
  - run `ensure_schema` twice,
  - no duplicate index,
  - no `ERROR 000192`.
- `assert_schema` passes valid schema and fails missing fields without repairing.
- Reset preserves feature class path and layer references.
- Board row insert/read roundtrip by `cell_id`.
- GameState read/write roundtrip with text/numeric values.
- Adjacency write/read roundtrip; 5×5 directed pair count = 144.
- ActionLog append stores `cell_id`s and `game_id`, not OIDs.

### A1: Selection and layer behavior

- `SearchCursor(layer, ...)` returns selected rows only.
- `UpdateCursor(layer, ...)` updates selected rows only.
- Explicitly test no-selection behavior before opening update cursor.
- `GetCount(layer)` with selection returns selected count.
- FIDSet diagnostic parser handles:
  - `None`,
  - empty string,
  - `'5'`,
  - `'5; 9'`,
  - `[5, 9]`.
- Wrong layer without required fields fails clearly.
- Stale layer / wrong `game_id` fails clearly.
- Renamed layer still works if data source is correct.
- Definition-query layer behavior is documented.
- Selection policy after reset/new game is verified.

### A2: Symbology / refresh / project lifecycle

- Apply `GameBoard_SurveySweeper.lyrx` to board layer.
- All `display_state` classes are preconfigured:
  - `hidden`,
  - `flagged`,
  - `revealed_empty`,
  - `revealed_clue`,
  - `hazard_hit`,
  - `hazard_revealed`,
  - `won_safe`.
- New board renders hidden without manual “Add unlisted values.”
- Reveal/flag/loss/win field updates visually redraw or documented refresh works.
- `arcpy.RefreshLayer` behavior is tested or explicitly avoided.
- `ApplySymbologyFromLayer` behavior is tested for fresh board, reset board, and reopened project.
- Labels or `label_text` fallback update after field changes.
- Close/reopen project keeps layer, symbology, toolbox, and data paths usable.

---

## D. Manual ArcGIS Pro Smoke Tests

Run after each major milestone.

### M0 — Toolbox health

- Open project.
- Add toolbox.
- Confirm no red-X/corrupted toolbox.
- Confirm parameters render.
- Change mode/action and confirm parameter enabling behaves.

### M1 — New Game

- Run `New Game`.
- Board appears in map.
- Attribute table has 25 rows.
- `GameState` initialized.
- `Adjacency` has 144 directed pairs.
- All cells render as hidden.
- Selection is cleared after new game.

### M2 — Reveal safe

- Select known safe cell from golden seed.
- Run `Reveal / Scout`.
- Confirm:
  - exactly one row changed,
  - `revealed=1`,
  - clue count correct,
  - display state correct,
  - message names selection cursor / adjacency lookup / field update,
  - ActionLog row appended.

### M3 — Flag / unflag

- Select unrevealed cell.
- Run `Flag / Mark`.
- Confirm `flagged=1`, display state `flagged`, flags count increments.
- Run again or select same cell; confirm unflag behavior if supported.

### M4 — Illegal actions

- Reveal with no selection.
- Flag with no selection.
- Reveal flagged cell.
- Flag revealed cell.
- Reveal after loss.
- Confirm no unintended mutation.

### M5 — Loss path

- Select known hazard.
- Run `Reveal / Scout`.
- Confirm status `lost`, hit hazard `hazard_hit`, other hazards `hazard_revealed`, Show Score still works, mutating actions rejected.

### M6 — Win path

- Follow golden seed win or near-win script.
- Confirm status `won`, safe revealed count complete, `won_safe` display applied, Show Score accurate.

### M7 — Reset and reopen

- Run `Reset`.
- Confirm same FC/layer survives.
- Confirm selection cleared.
- Close/reopen project.
- Run `Show Score`.
- Run another reveal.
- Confirm no broken paths, no duplicate indexes, no schema locks.

---

## Demo Script Requirements

The demo script should be an operator runbook, not just gameplay notes.

Required sections:

- Environment:
  - ArcGIS Pro version,
  - project path,
  - toolbox path,
  - gdb path,
  - required panes open.

- Pre-demo state:
  - project already opened or cold start,
  - toolbox already added or add steps,
  - board layer present or generated live,
  - symbology already applied or apply steps.

- Golden seed:
  - board size,
  - hazard count,
  - seed,
  - exact hazard cells,
  - known safe first cell,
  - known hazard/loss cell,
  - expected clue cells.

- Step-by-step runbook:
  - action,
  - GP parameters,
  - selection method,
  - selected `cell_id`s,
  - expected message,
  - expected visual state,
  - expected GameState / ActionLog proof.

- Recovery lines:
  - no selection warning,
  - symbology not refreshing,
  - toolbox red-X/corrupted,
  - wrong layer selected,
  - GP pane state confusing.

- Panic path:
  - pre-opened project,
  - pre-generated board,
  - 3–5 reliable actions,
  - screenshots or saved project state if live refresh fails.

---

## Minority / Dissenting Notes

- One reviewer would clear selection after successful reveal/flag to reduce accidental repeat actions. Consensus accepts retaining selection during ordinary actions if illegal repeats are blocked, but clearing on `New Game` / `Reset` is strongly recommended.
- One reviewer would add `game_id` / `session_id` even though it slightly expands the Stage 1 field set. This is recommended because it protects against stale-selection and reset weirdness.
- Labels should be considered optional. Symbology, GP messages, fields, and ActionLog are more important for demo reliability.
- Containment Commander should not start merely because Survey Sweeper “basically works.” It should start only after cold-start fallback lock passes.

---

## Concrete Next Actions

1. Patch the broader v2 plan selection-contract language to cursor-over-layer primary.
2. Decide and freeze MVP policies:
   - zero-based `cell_id`,
   - single-cell reveal,
   - multi-cell flag if simple,
   - safe-reveal-only win,
   - clear selection on New Game / Reset,
   - add `game_id` / `session_id`.
3. Write Milestone 1 TDD plan using the P0/P1 pure tests above.
4. Implement pure rules only after failing tests exist.
5. Add fake-store action tests before `.pyt` wiring.
6. Validate `.lyrx`, project reopen, renamed layer, wrong/stale layer, and label fallback before starting Containment Commander.

