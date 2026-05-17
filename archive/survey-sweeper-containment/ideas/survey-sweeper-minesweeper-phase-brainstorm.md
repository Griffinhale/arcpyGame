# Brainstorm — Survey Sweeper / Minesweeper Phase

Date: 2026-05-09

Context:
- Based on `ideas/feasibility-spike-results.md` and `ideas/minesweeper-to-containment-implementation-plan-v2.md`.
- The ArcGIS Pro spike passed the must-have loop: Python toolbox, parameter staging, map selection input, cursor updates, automatic redraw after symbology priming, memory buffer/select, repeated runs, and reset-without-deleting-FC.
- Biggest implementation update from the spike: `arcpy.da.SearchCursor(layer, ...)` and `arcpy.da.UpdateCursor(layer, ...)` respect map layer selection in Pro 3.6. Use cursor-over-layer as the primary selection path; keep FIDSet parsing as diagnostics/fallback.

---

## Frame

Topic: Details for the first playable minesweeper phase, branded as **Survey Sweeper**.

Audience/user:
- Primary: Griffin building a class/demo-worthy ArcGIS Pro + ArcPy game.
- Secondary: instructor/classmates who should see real GIS concepts as gameplay verbs.

Constraints:
- ArcGIS Pro / ArcPy / Python toolbox controller.
- Turn-based GP pane interaction; no custom game UI or real-time loop.
- Board should stay small: 5×5 first, then 7×7 if comfortable.
- Core path should avoid Spatial Analyst, Network Analyst, Feature Set drawing, real data cleanup, and heavy per-turn GP.
- Must remain shippable as fallback if Containment Commander slips.

Criteria:
- Feasibility inside Pro.
- Demo clarity.
- GIS-native feel.
- Fast operator flow.
- Clean transition path into Containment Commander.
- Avoid scope creep.

Quantity target:
- 30+ raw/detail ideas.
- Cluster into implementation themes.
- Shortlist concrete design decisions for Milestones 1–4.

---

## Spike Findings That Should Change the Minesweeper Design

1. **Primary selection implementation can be simpler than planned.**
   - Use `SearchCursor(game_layer, fields)` and `UpdateCursor(game_layer, fields)` over the selected `GPFeatureLayer`.
   - The cursor respects the map selection, so action handlers can avoid building `OBJECTID IN (...)` clauses for normal execution.
   - Still log `FIDSet` in debug/diagnostic mode because it is useful for no-selection / stale-selection error messages.

2. **Symbology must be a first-class deliverable, not polish.**
   - Automatic redraw worked after initial unique-value class priming.
   - Avoid first-run manual “Add unlisted values” by shipping/preconfiguring `.lyrx` with all Survey Sweeper `display_state` classes.

3. **Reset strategy is validated.**
   - `DeleteRows` on displayed layer worked.
   - Keep feature class path/name stable; clear and reseed rows instead of deleting/recreating displayed feature classes.

4. **Schema idempotency matters.**
   - `AddIndex` is not idempotent; duplicate name caused `ERROR 000192`.
   - `ensure_schema()` must check existing fields/indexes before any schema mutation.

5. **Messages should use one API.**
   - `messages.addMessage(...)` and `arcpy.AddMessage(...)` both work, but using both duplicates output.
   - Prefer toolbox-native `messages.*` methods.

6. **Buffer/select is validated for later, but not needed for core Survey Sweeper.**
   - Keep it out of Stage 1 unless used as a demo teaser.

---

## Raw Ideas

### Core rules / game feel

1. Use a 5×5 `Tiny Demo` board with 4 hazards for the first playable loop.
2. Keep 7×7 with 8 hazards as the only “real” larger setting until demo timing is proven.
3. Brand hidden cells as “unsurveyed parcels.”
4. Brand hazards as “contaminated parcels,” “restricted sites,” or “buried hazards.”
5. Brand clue number as “adjacent hazard indicators.”
6. `Reveal / Scout` should reveal exactly selected cells first; flood reveal is optional after the single-cell loop is stable.
7. If multiple cells are selected for reveal, allow it only if all are unrevealed/unflagged; otherwise fail with a precise message.
8. `Flag / Mark` toggles suspected hazards on unrevealed cells.
9. Loss on revealing a hazard should reveal all hazards and set `status='lost'`.
10. Win condition should be “all safe cells revealed”; exact hazard flagging can be a secondary/alternate win.
11. Keep a `turn` or `action_count` even though Minesweeper is not turn-based, because it makes `ActionLog` and demo narration cleaner.
12. Include a `last_message` in `GameState` matching the last GP message summary.

### GIS-native framing

13. Each action message should explicitly name the data operation: “Selection cursor,” “Adjacency lookup,” “Field update,” “Display state recompute.”
14. Show the `Adjacency` table during demo to explain clue counts as spatial neighbor relationships.
15. Use `row_idx` / `col_idx` only for generation; explain `cell_id` as stable GIS/game ID.
16. Optional later: compute adjacency by geometry touching/intersection instead of row/col math, then mention GIS topology.
17. Add tiny synthetic `RiskSources` only after core game works to spatially bias hazards near a line/point.
18. Use field aliases so attribute table reads like game state and GIS state.
19. Name the mode “Survey Sweeper” in the UI, not “Minesweeper,” to fit the class-demo premise.

### Data model details

20. `GameBoard` fields for Stage 1: `cell_id`, `row_idx`, `col_idx`, `is_hazard`, `revealed`, `flagged`, `neighbor_count`, `turn_revealed`, `display_state`, `notes`.
21. Store booleans as `SHORT` 0/1 for file geodatabase compatibility.
22. Use text `cell_id` like `R03C05`; make it zero-padded for lexical sorting.
23. `Adjacency` rows should include 8-way neighbors for Survey Sweeper.
24. Add `neighbor_rank` or `direction` only if useful for debugging; otherwise skip.
25. `GameState` one-row-per-key is simple but clunky; still acceptable for ArcPy.
26. `ActionLog.target_cell_ids` can be comma-separated text; no need for a normalized log-target join table.
27. `display_state` should never be the source of truth.
28. For clue labels, use `neighbor_count`, but only visually show it for revealed clue cells via display/label expression if possible.

### Controller / operator flow

29. Stage 1 actions should be exactly: `New Game`, `Reveal / Scout`, `Flag / Mark`, `Show Score`, `Reset`.
30. `Game Layer` required for everything except `New Game` and maybe `Show Score` if workspace is enough.
31. `Board Size / Difficulty` and `Random Seed` enabled only for `New Game` / `Reset`.
32. Retain map selection after actions at first; clearing selection may annoy the operator who wants to flag/reveal adjacent cells.
33. Add a warning if no features are selected for reveal/flag.
34. Add a warning if selected cursor returns all rows unexpectedly; that means selection was not applied or wrong layer was passed.
35. `Show Score` should not require a selection and should be safe to run anytime.
36. After game is won/lost, mutating actions should error unless `Reset` / `New Game` is run.

### Display / symbology

37. Pre-class all Survey Sweeper display states in `.lyrx`: `hidden`, `flagged`, `revealed_empty`, `revealed_clue`, `hazard_hit`, `hazard_revealed`, `won_safe`.
38. Label revealed clue cells with `neighbor_count`; hide labels for hidden/flagged/hazard cells if practical.
39. Use strong color semantics: hidden gray, flagged blue/purple, revealed empty pale green/white, clue yellow/orange, hazard red/black, won safe green.
40. Add `notes` as a backup label/debug field if clue labels are annoying.
41. If `.lyrx` creation becomes a time sink, ship a manual symbology setup doc plus screenshots as fallback.
42. Include field aliases before generating `.lyrx` so table and symbology class names are readable.

### Testing / demo

43. Pure Python tests should cover adjacency, hazard placement determinism, neighbor counts, reveal, flag, loss, win, display-state mapping.
44. Golden seed should include a known first safe reveal and a known hazard-hit reveal.
45. Demo script should include exact cells: first reveal, clue reveal, flag, score, loss/win path.
46. Keep a “panic demo” seed with only 5×5 and 4 hazards where the entire script is under 2 minutes.
47. Manual smoke test after each milestone should check Pro reload, toolbox load, new game, reveal, flag, score, reset.
48. Keep fallback screenshots/precomputed project state in case live Pro refresh acts weird during demo.

### Scope traps to avoid

49. Do not implement flood reveal until basic reveal/flag/win/loss works in Pro.
50. Do not implement real data or risk-source bias before core Survey Sweeper is shippable.
51. Do not build Feature Set drawing for Minesweeper.
52. Do not overbuild a generalized action engine.
53. Do not change schema during `Reveal / Scout` or `Flag / Mark`.
54. Do not rely on deleting/recreating feature classes during reset.
55. Do not spend too long on perfect labels; GP messages + attribute table are acceptable fallback UI.

---

## Clusters

### A. Minimum playable loop

- New Game creates board and state.
- Reveal selected cells.
- Flag selected cells.
- Win/loss.
- Show Score.
- Reset.

### B. ArcPy execution contracts

- Cursor-over-selected-layer primary path.
- FIDSet logging/fallback.
- Idempotent schema setup.
- Stable feature class path/name.
- No schema mutation during play.

### C. Data model / display separation

- Domain fields drive rules.
- `display_state` drives symbology.
- `GameState`, `Adjacency`, `ActionLog` are visible proof of GIS-backed state.

### D. Demo / pedagogy layer

- Survey Sweeper framing.
- Operation-aware messages.
- Field aliases.
- Golden seed/action script.
- Show attribute table/action log/adjoining cells.

### E. Polish / fallback management

- `.lyrx` with pre-classed states.
- Label strategy.
- Quickstart/manual smoke test.
- Screenshots/precomputed fallback state.

---

## Shortlisted Concept Cards

### 1. Minimum Vertical Slice — 5×5 Survey Sweeper

- Pitch: The smallest playable ArcGIS Pro Minesweeper loop: create a 5×5 survey grid, select cells on the map, reveal/flag them through the GP pane, and see fields/symbology update.
- User value: Proves the whole game architecture with minimal moving parts.
- How it works: `New Game` seeds hazards and adjacency; selected-layer cursor reads player selections; rule functions mutate domain fields; display mapper sets `display_state`; GP messages narrate the result.
- MVP version: 5×5, 4 hazards, no flood reveal, win by revealing all safe cells, lose by revealing hazard.
- Stretch version: 7×7, flood reveal for zero-clue cells, alternate exact-flag win.
- Risks: Symbology/labels can consume time; selection behavior could differ on reopened/renamed layers.
- First validation step: Pure Python rules tests, then one Pro smoke test: New Game → select safe cell → Reveal → select hidden cell → Flag → Show Score.

### 2. GIS-Legible Action Messages

- Pitch: Every GP run doubles as a class-demo narration of what GIS operation just resolved gameplay.
- User value: Prevents the project from feeling like “Minesweeper drawn on a map.”
- How it works: Action handlers emit concise messages naming selection/cursor/adjacency/field updates and gameplay effect.
- MVP version: Hardcoded message templates per action.
- Stretch version: Include counts from ActionLog and references to tables/layers touched.
- Risks: Verbose messages could slow demo readability.
- First validation step: Draft expected messages for the golden demo script.

### 3. Pre-Classed Symbology Layer Package

- Pitch: Ship a `.lyrx` so `display_state` values render correctly on first run without manual unique-value priming.
- User value: Makes the demo feel polished and avoids the spike’s main visual gotcha.
- How it works: Create all possible `display_state` classes before demo; generated boards use only those values.
- MVP version: Manual `.lyrx` authored in Pro and committed/exported.
- Stretch version: Runtime `ApplySymbologyFromLayer` if robust.
- Risks: `.lyrx` paths/project packaging can be brittle.
- First validation step: Create `GameBoard_SurveySweeper.lyrx` against the spike board and test New Game/reveal after Pro reopen.

### 4. Golden Demo Seed as Regression Harness

- Pitch: Treat the demo script as both presentation notes and a manual test spec.
- User value: Keeps development honest and protects against demo-day brittleness.
- How it works: Pick a seed/board; document exact selected cells, actions, expected messages, expected display states.
- MVP version: One 5×5 seed with 6–8 actions.
- Stretch version: One win path and one loss path; optional 7×7 script.
- Risks: Seeds may change if hazard placement algorithm changes.
- First validation step: Freeze hazard placement algorithm before writing final script.

### 5. Optional Flood Reveal

- Pitch: Make Survey Sweeper feel like real Minesweeper by revealing connected zero-clue regions.
- User value: More satisfying gameplay, faster demo.
- How it works: Pure Python BFS over `Adjacency` reveals zero-neighbor safe cells and boundary clue cells.
- MVP version: Not included.
- Stretch version: Single-cell reveal only triggers flood; multi-cell reveal stays simple.
- Risks: More display updates, more edge cases, harder golden script.
- First validation step: Implement in pure Python only after basic Pro loop works.

---

## Scorecard

Scoring: Value / Feasibility / Novelty / Strategic Fit / Risk

- Minimum Vertical Slice: 5 / 5 / 3 / 5 / low
- GIS-Legible Action Messages: 5 / 5 / 4 / 5 / low
- Pre-Classed Symbology Layer Package: 4 / 3 / 2 / 5 / medium
- Golden Demo Seed as Regression Harness: 5 / 5 / 2 / 5 / low
- Optional Flood Reveal: 3 / 4 / 2 / 3 / medium
- Synthetic RiskSources Bias: 3 / 3 / 4 / 4 / medium-high
- Exact-Flag Win Condition: 2 / 4 / 2 / 2 / low
- Runtime ApplySymbologyFromLayer: 2 / 3 / 2 / 3 / medium

---

## Recommended Minesweeper Phase Shape

### Milestone 1 — Pure Survey Sweeper Rules

Build first outside ArcGIS Pro:

- Board generation:
  - `Tiny Demo`: 5×5, 4 hazards.
  - `Small`: 7×7, 8 hazards.
- Stable IDs:
  - Use zero-padded text IDs: `R00C00`, `R00C01`, etc.
- Adjacency:
  - 8-way for Survey Sweeper.
- Hazard placement:
  - Deterministic from seed.
  - Exclude first reveal from hazards only if implementing first-click safety; otherwise document known safe first reveal in demo script.
- Actions:
  - reveal selected cell IDs.
  - flag/unflag selected cell IDs.
  - show score/status.
- Display mapper:
  - `hidden`, `flagged`, `revealed_empty`, `revealed_clue`, `hazard_hit`, `hazard_revealed`, `won_safe`.
- Tests:
  - adjacency counts corners/edges/center,
  - deterministic hazards,
  - neighbor counts,
  - reveal safe,
  - reveal hazard loss,
  - flag toggle,
  - win by revealing safe cells,
  - display-state mapping.

### Milestone 2 — Schema / Store / Display

Implement ArcPy storage helpers:

- `ensure_schema(workspace, mode='survey')`:
  - create gdb if missing,
  - create `GameBoard`, `GameState`, `Adjacency`, `ActionLog`,
  - add fields/indexes only if missing,
  - check indexes by fields, not just names.
- `assert_schema(...)`:
  - verifies required datasets/fields/schema_version,
  - no mutation during ordinary actions.
- Reset/New Game:
  - `DeleteRows` existing tables/FCs,
  - reseed rows,
  - preserve feature class paths and layer references.
- Store helpers:
  - read selected board rows via cursor over selected `game_layer`,
  - fallback to FIDSet/explicit OID where only for diagnostics/edge cases,
  - write rows by `cell_id`,
  - write `GameState`,
  - append `ActionLog`.

### Milestone 3 — Playable Survey Sweeper in Pro

Controller actions:

- `New Game`
  - enabled params: mode, board size/difficulty, seed.
  - no selected layer required.
- `Reveal / Scout`
  - requires selected `Game Layer`.
  - rejects no selection, revealed cells, flagged cells, completed games.
- `Flag / Mark`
  - requires selected `Game Layer`.
  - toggles unrevealed cells.
- `Show Score`
  - no selection required if workspace can locate `GameState`; otherwise use layer/workspace.
- `Reset`
  - same as new game using current/stored seed if none provided.

Operator-flow policy:
- Retain selection after mutating actions initially.
- Document that selection persists; user may manually clear/change selection.
- Revisit only if retained selections cause accidental repeat actions.

### Milestone 4 — Fallback Lock / Polish

Must-have polish:

- `GameBoard_SurveySweeper.lyrx` with all display states pre-classed.
- Field aliases.
- Labels for clue counts if practical.
- `docs/demo-script.md` with exact seed/actions.
- `docs/quickstart.md` with Pro setup and cache-hygiene note:
  - avoid moving `.pyt` while Pro is running;
  - if toolbox gets red-X/corrupted after moves, clear `__pycache__` and `.pyt.xml`, then re-add toolbox.
- `docs/manual-smoke-test.md`.

---

## Proposed Field Set for Stage 1

### `GameBoard`

- `cell_id` — TEXT(16), stable gameplay key.
- `row_idx` — LONG.
- `col_idx` — LONG.
- `is_hazard` — SHORT, 0/1.
- `revealed` — SHORT, 0/1.
- `flagged` — SHORT, 0/1.
- `neighbor_count` — SHORT.
- `turn_revealed` — LONG, `-1` default.
- `display_state` — TEXT(32).
- `notes` — TEXT(255).

Indexes:
- unique or normal index on `cell_id`, after checking no existing index already covers the field.
- optional normal index on `display_state` only if useful.

### `Adjacency`

- `cell_id` — TEXT(16).
- `neighbor_id` — TEXT(16).
- `touch_type` — TEXT(16), e.g. `edge`, `corner`.
- `weight` — DOUBLE, default `1.0`.

Indexes:
- `cell_id`.
- `neighbor_id`.

### `GameState`

- `key` — TEXT(64).
- `value_text` — TEXT(255).
- `value_num` — DOUBLE.

Minimum keys:
- `schema_version`
- `mode`
- `status` — `ready`, `playing`, `won`, `lost`
- `seed`
- `board_rows`
- `board_cols`
- `hazard_count`
- `safe_revealed_count`
- `flags_count`
- `action_count`
- `last_message`

### `ActionLog`

- `log_id` — LONG.
- `turn` or `action_count` — LONG.
- `action` — TEXT(64).
- `target_cell_ids` — TEXT(512).
- `result` — TEXT(512).
- `score_delta` — DOUBLE, probably `0` for Survey Sweeper.
- `timestamp` — DATE.
- `gp_operation` — TEXT(128), e.g. `SelectionCursor;AdjacencyLookup;FieldUpdate`.

---

## Display State Mapping

Recommended deterministic mapping order:

1. If game status is `won` and cell is safe/revealed: `won_safe`.
2. If cell is hazard and was hit: `hazard_hit`.
3. If status is `lost` and cell is any other hazard: `hazard_revealed`.
4. If `flagged=1` and `revealed=0`: `flagged`.
5. If `revealed=0`: `hidden`.
6. If `revealed=1` and `neighbor_count=0`: `revealed_empty`.
7. If `revealed=1` and `neighbor_count>0`: `revealed_clue`.

Rule: no game rule should inspect `display_state`; it is output-only.

---

## Message Templates

### `New Game`

> New Game: created 5×5 Survey Sweeper board with seed 2026 and 4 hidden hazards. GIS state: GameBoard rows=25, Adjacency pairs=144, GameState initialized. Select a parcel and run Reveal / Scout.

### `Reveal / Scout` safe clue

> Reveal / Scout: Selection cursor read 1 parcel (`R02C03`). Adjacency lookup found 2 neighboring hazard indicators. Updated `revealed`, `turn_revealed`, and `display_state=revealed_clue`.

### `Reveal / Scout` safe empty

> Reveal / Scout: Selection cursor read 1 parcel (`R01C01`). Adjacency lookup found 0 neighboring hazard indicators. Parcel is safe; display state updated to `revealed_empty`.

### `Reveal / Scout` hazard

> Reveal / Scout: selected parcel `R03C04` contains a hidden hazard. Status set to LOST; all hazard cells revealed for inspection.

### `Flag / Mark`

> Flag / Mark: Selection cursor read 2 parcels. Toggled `flagged` for `R00C03,R02C04`; display state updated for marked parcels. Flags: 2 / 4 hazards.

### `Show Score`

> Survey Sweeper score: status=playing; safe revealed=6/21; flags=2/4; actions=8; seed=2026. Last action: `R02C03` revealed with clue count 2.

---

## Top Recommendations

1. **Implement the 5×5 minimum vertical slice first.**
   - No flood reveal, no risk bias, no real data, no Feature Set drawing.

2. **Promote `.lyrx` and demo script into the minesweeper phase, not final polish.**
   - The spike showed symbology priming is the biggest visible gotcha.

3. **Use cursor-over-selected-layer as the normal code path.**
   - This is the biggest simplification from the spike.
   - Keep FIDSet parsing only for diagnostics/fallback.

4. **Make messages explicitly GIS-native.**
   - This is cheap and dramatically improves the class-demo story.

5. **Freeze a golden seed early.**
   - Use it as both regression checklist and presentation script.

---

## Weird / High-Upside Wildcard

### “First Click Creates the Survey Plan”

Instead of hazards being fully placed at `New Game`, the first `Reveal / Scout` could finalize hazard placement while guaranteeing the selected first parcel is safe. Message:

> “Survey design: first selected parcel reserved as initial sample site; hazards seeded outside its 8-neighbor buffer.”

Why it is interesting:
- Makes Minesweeper fairer.
- Can be framed as GIS sampling design.

Why to park initially:
- More state complexity.
- Golden seed becomes slightly less obvious.
- Not necessary for the first playable loop.

---

## Parked Ideas

- Flood reveal until the single-cell loop works in Pro.
- Spatially biased hazards near `RiskSources` until fallback is shippable.
- Feature Set drawing.
- Runtime symbology authoring beyond applying a prebuilt `.lyrx`.
- Hex board.
- Real data.
- Exact-flag-only win as primary win condition.
- Complex scoring.
- Player action tables beyond simple `ActionLog`.

---

## Immediate Next Action

Write a focused implementation plan for **Milestone 1: Pure Survey Sweeper Rules** and start with tests for:

1. cell ID generation,
2. 8-way adjacency,
3. deterministic hazard placement,
4. neighbor counts,
5. reveal safe / reveal hazard,
6. flag toggle,
7. win/loss,
8. display-state mapping.

Then integrate with schema/store/controller only after those pure tests are green.
