# Minesweeper to Containment Commander Implementation Plan v2

> **For Hermes / implementers:** Planning artifact only. Do not start coding from this document until Griffin explicitly asks. When implementation begins, build the smallest vertical slice first, test inside ArcGIS Pro early, and commit at reasonable checkpoints.

**Goal:** Build a staged ArcGIS Pro + ArcPy game where geoprocessing is the gameplay verb: first ship a polished Survey Sweeper fallback, then evolve the same board/state/controller architecture into deterministic selected-cell Containment Commander, then add one or two Bufferlands-style geoprocessing powers as stretch/demo polish.

**Architecture:** One small feature-class board; durable state in feature classes/tables; precomputed adjacency; one Python toolbox controller with staged `Action` dropdowns; map selections as the first player input mechanism; optional Feature Set geometry only after selected-cell gameplay works; preconfigured symbology/labels driven by a dedicated `display_state` field.

**Tech Stack:** ArcGIS Pro, ArcPy, Python toolbox (`.pyt`), file geodatabase, core vector geoprocessing, `arcpy.da` cursors, `memory\\...` intermediates, `.lyrx` symbology, pure-Python tests for rule logic where possible.

---

## 1. What Changed from v1

This v2 folds in the second Delphi improvement panel.

### Highest-priority changes

1. **The final MVP is now tiered.**
   - Minimum: polished Survey Sweeper.
   - Target: deterministic selected-cell Containment Commander.
   - Stretch: Bufferlands powers.
2. **ArcGIS Pro feasibility spike moves to the front.**
   - Prove `.pyt`, parameters, selections, `FIDSet`, OID-to-`cell_id`, cursor updates, refresh, and symbology before deeper implementation.
3. **Action dropdown is staged.**
   - Do not expose every future action at once.
4. **ArcPy contracts are explicit.**
   - Stable `cell_id`, selection resolution, schema setup vs validation, reset behavior, indexes, memory cleanup, refresh behavior.
5. **`display_state` is separated from rule state.**
   - Gameplay rules use domain fields; symbology uses `display_state`.
6. **Containment is deterministic and all-visible first.**
   - No fog-of-war, probabilistic spread, Feature Set drawing, or complex durations in the first target implementation.
7. **GIS legitimacy is concrete but bounded.**
   - Learning objectives, synthetic `RiskSources` and `Assets`, operation-aware messages, field aliases, asset exposure scoring.
8. **Demo seed/action script becomes an early deliverable.**
   - The project should be demoable reliably even if ArcGIS Pro gets fussy.

---

## 2. North Star Design

### One-sentence pitch

**A turn-based ArcGIS Pro game where feature selections, adjacency, buffers, spatial joins, and field updates are not implementation details — they are the moves.**

### Class-demo promise

> “ArcPy is not drawing a game on top of a map. ArcPy is resolving the game by operating on real GIS feature classes, attributes, selections, spatial relationships, and geoprocessing outputs.”

### What the project must prove

- ArcGIS Pro’s normal GP workflow can act as a game controller.
- Feature classes/tables can hold durable game state.
- Map selections can be player input.
- Symbology and labels can be the renderer.
- Geoprocessing concepts can be gameplay verbs.

### Non-goals

Do not build:

- custom game UI,
- card/deck UI,
- real-time animation,
- always-running loops,
- RPG inventory systems,
- large simulations,
- live Spatial Analyst / Network Analyst turn logic,
- a generalized game engine before one playable board exists,
- real-data cleanup as part of the MVP.

---

## 3. Final Submission Acceptance Tiers

This section replaces v1’s single “Final MVP Acceptance Criteria.”

## 3.1 Minimum / Fallback Submission — Polished Survey Sweeper

This is the shippable endpoint if time gets tight.

Required:

- One Python toolbox controller loads in ArcGIS Pro.
- Stage 1 action dropdown includes only:
  - `New Game`
  - `Reveal / Scout`
  - `Flag / Mark`
  - `Show Score`
  - `Reset`
- `New Game` creates or resets a small board without breaking existing map layer references.
- Player selects cells on the map and runs `Reveal / Scout`.
- Player selects cells and runs `Flag / Mark`.
- Win/loss logic works.
- State persists in:
  - `GameBoard`
  - `GameState`
  - `Adjacency`
  - `ActionLog`
- Symbology and labels clearly show hidden, revealed, flagged, clue, and hazard-hit states.
- GP messages explain both gameplay outcome and GIS/data operation.
- Known demo seed/action script exists.
- No schema mutation during ordinary reveal/flag turns.
- Board stays small: 25–64 cells preferred; 75 max unless proven safe.

Minimum submission is considered successful even if Containment Commander and Bufferlands powers are not finished.

## 3.2 Target Submission — Deterministic Selected-Cell Containment Commander

Only build after Minimum is stable.

Required:

- Same controller/data model supports `Scenario Mode = Containment Commander`.
- Stage 2 action dropdown includes:
  - `New Game`
  - `Scout`
  - `Treat / Clear`
  - `Place Barrier`
  - `Resolve Turn`
  - `Show Score`
  - `Reset`
- Threat spread is deterministic and all-visible.
- Player uses selected cells for `Treat / Clear` and `Place Barrier`.
- 2 AP per turn by default.
- Barriers/treatments visibly alter spread.
- Critical assets create stakes.
- Score is based on asset exposure / protected value / threat threshold.
- A 5–10 turn scripted demo runs in under 5 minutes.

Target is successful even with no Feature Set drawing, no fog-of-war, no real data, and no probabilistic spread.

## 3.3 Stretch Submission — Bufferlands-Style GP Powers

Only build after Target is stable.

Priority order:

1. `Buffer Defense`
   - Best first wow move.
   - Uses real `Buffer` plus spatial selection/intersection.
2. `Spatial Join Harvest / Score`
   - Only if a tiny synthetic `Assets` layer exists.
   - Uses real Spatial Join or a clearly documented fallback until Spatial Join is ready.
3. Optional `Suppress Hotspot` / `Erase Hotspot`
   - Prefer selection/intersection-based treatment.
   - Actual `Erase` is optional and must not be a hard dependency.

Future only:

- `Clip Quarantine`
- `Dissolve Safe Zone`
- fog-of-war
- real data
- complex duration/cooldown systems
- generalized power/action data tables

---

## 4. Recommended Project Structure

Create this structure during implementation:

```text
/workspace/projects/arcpyGame/
  README.md
  ideas/
    arcpy-geoprocessing-ui-environment-constraints.md
    delphi-panel-shortlist.md
    delphi-plan-improvement-panel.md
    minesweeper-to-containment-implementation-plan-v2.md
    feasibility-spike-syntax-feature-inventory.md
  toolbox/
    arcpy_game.pyt
    arcpy_game_actions.py
    arcpy_game_display.py
    arcpy_game_gp.py
    arcpy_game_rules.py
    arcpy_game_scenarios.py
    arcpy_game_schema.py
    arcpy_game_store.py
  data/
    README.md
    arcpy_game.gdb/
      GameBoard
      GameState
      ActionLog
      Adjacency
      RiskSources      # target/stretch, tiny synthetic layer
      Assets           # target/stretch, tiny synthetic layer
  symbology/
    GameBoard_SurveySweeper.lyrx
    GameBoard_Containment.lyrx
    Assets.lyrx
    RiskSources.lyrx
  docs/
    demo-script.md
    quickstart.md
    manual-smoke-test.md
  tests/
    test_minesweeper_rules.py
    test_containment_rules.py
    test_display_state.py
    test_action_contracts.py
    test_schema_contract.py
```

### Module responsibilities

#### `toolbox/arcpy_game.pyt`

- ArcGIS Pro Python toolbox entrypoint.
- Defines `GameController` tool.
- Owns GP parameters, validation, and dispatch.
- Keeps validation lightweight.
- Does not contain core game rules.

#### `toolbox/arcpy_game_actions.py`

- Action dispatch and action handlers.
- Defines lightweight `ActionContext` / `ActionResult` contracts.
- Converts tool parameters into game actions.

#### `toolbox/arcpy_game_rules.py`

- Pure-ish Python game rules.
- No ArcPy import unless absolutely unavoidable.
- Survey Sweeper reveal/flag/win/loss.
- Containment spread/treatment/barrier/scoring.

#### `toolbox/arcpy_game_schema.py`

- File geodatabase and schema creation.
- `ensure_schema()` for setup/reset/migration.
- `assert_schema()` for cheap per-action checks.
- Field/index definitions.

#### `toolbox/arcpy_game_store.py`

- ArcPy cursor helpers.
- Read/write `GameState`.
- Read/write `GameBoard` rows.
- Resolve selected OIDs/FIDs to stable `cell_id`s.
- Write `ActionLog` rows.

#### `toolbox/arcpy_game_display.py`

- Converts domain fields into `display_state`.
- Keeps symbology logic out of game rules.

#### `toolbox/arcpy_game_gp.py`

- Thin wrappers around ArcPy geoprocessing tools:
  - `Buffer`
  - `SelectLayerByLocation`
  - `SpatialJoin`
  - optional `Erase`
  - optional `Clip`
  - optional `Dissolve`
- Handles `memory\\...` naming/cleanup.

#### `toolbox/arcpy_game_scenarios.py`

- Tiny scenario definitions.
- Not a scenario editor.
- Stores board size, seed, hazards/threats, AP rules, demo notes.

---

## 5. Core Data Model

## 5.1 `GameBoard` Feature Class

Geometry: polygon cells. Start with generated square grid. Hex/tessellation is optional after square grid works.

### Stable identity fields

- `cell_id` — text or long; durable gameplay key.
- `row_idx` — long; generated-grid row.
- `col_idx` — long; generated-grid column.

Rules:

- `cell_id` is the canonical game ID.
- `OBJECTID` / FID is only a transient ArcGIS storage/selection handle.
- `Adjacency`, `ActionLog`, tests, and rule functions use `cell_id`.

### Stage 1 Survey Sweeper domain fields

- `is_hazard` — short integer boolean, `0/1`.
- `revealed` — short integer boolean, `0/1`.
- `flagged` — short integer boolean, `0/1`.
- `neighbor_count` — short integer.
- `turn_revealed` — long; `-1` if never revealed.
- `notes` — text, optional.

### Display field

- `display_state` — text; symbology driver.

Survey Sweeper values:

- `hidden`
- `flagged`
- `revealed_empty`
- `revealed_clue`
- `hazard_hit`
- `hazard_revealed`
- `won_safe`

Do not make game rules depend on `display_state`; recompute it from domain fields after actions.

### Stage 2 Containment domain fields

- `threat` — short integer boolean, `0/1`.
- `threat_level` — short integer, `0–3`.
- `susceptibility` — double, `0.0–1.0`.
- `treated_turn` — long; `-1` if never.
- `barrier` — short integer boolean, `0/1`.
- `asset_value` — double or long.
- `critical_asset` — short integer boolean, `0/1`.
- `defended` — short integer boolean, `0/1`.
- `defended_until_turn` — long; optional if temporary defense is used.
- `lost_asset` — short integer boolean, `0/1`.
- `spread_seed` — double or text; optional deterministic tie-break/random source.
- `last_changed_turn` — long.

Avoid ambiguous `protected` in core logic. If used at all, define it as display-only or deprecated.

Containment `display_state` values:

- `safe`
- `threat_low`
- `threat_medium`
- `threat_high`
- `treated`
- `barrier`
- `defended`
- `critical_asset`
- `lost_asset`

## 5.2 `Adjacency` Table

Fields:

- `cell_id`
- `neighbor_id`
- `touch_type`
- `weight`

Rules:

- Store stable `cell_id` values, never OIDs.
- For Survey Sweeper square grid, use 8-way adjacency.
- For Containment square grid, default to 4-way adjacency unless a scenario explicitly uses 8-way.
- Load into a Python dictionary per action.
- Add indexes on `cell_id` and `neighbor_id`.

## 5.3 `GameState` Table

Use a one-row-per-key table.

Fields:

- `key` — text.
- `value_text` — text.
- `value_num` — double.

Required keys:

- `schema_version`
- `mode`
- `status`
- `turn`
- `seed`
- `board_rows`
- `board_cols`
- `hazard_count`
- `safe_revealed_count`
- `flags_count`
- `action_points_remaining`
- `max_turns`
- `score`
- `threat_count`
- `threat_threshold`
- `critical_assets_remaining`
- `last_message`

Add index on `key`.

## 5.4 `ActionLog` Table

Fields:

- `log_id` — long; explicit sequential ID is fine.
- `turn` — long.
- `action` — text.
- `target_cell_ids` — text; comma-separated stable IDs.
- `result` — text.
- `score_delta` — double.
- `timestamp` — date.
- `gp_operation` — text; e.g. `Selection`, `Adjacency`, `Buffer`, `SpatialJoin`.

Purpose:

- Durable turn history.
- Debugging.
- Demo narration.
- Backup if GP messages disappear.

## 5.5 Optional Synthetic GIS Context Layers

### `RiskSources`

Tiny synthetic point/line/polygon layer.

Fields:

- `risk_id`
- `risk_type`
- `risk_weight`
- `notes`

Examples:

- industrial source,
- road corridor,
- river/stream,
- invasive source.

Use:

- Stage 1 polish: spatially biased hazards.
- Stage 2 target/stretch: susceptibility and threat seed bias.

### `Assets`

Tiny synthetic point/polygon layer.

Fields:

- `asset_id`
- `asset_type`
- `asset_value`
- `critical`
- `status`

Examples:

- town center,
- water intake,
- habitat core,
- school/hospital,
- infrastructure node.

Use:

- Containment stakes.
- Spatial Join Harvest scoring.

---

## 6. Python Toolbox Controller Layout

## 6.1 Tool shape

```text
Toolbox: ArcPy Game
  Tool: Game Controller
```

## 6.2 Parameters

Define full controller shape up front because Python toolbox parameter structure cannot be freely changed at runtime.

Recommended parameters:

1. `Game Workspace`
   - Type: `DEWorkspace` or `GPString`.
   - Default: project `data/arcpy_game.gdb` where possible.
2. `Game Layer`
   - Type: `GPFeatureLayer`.
   - Required for most actions after `New Game`.
3. `Scenario Mode`
   - Type: `GPString` with `ValueList`.
   - Values:
     - `Survey Sweeper`
     - `Containment Commander`
   - Most relevant for `New Game`.
4. `Action`
   - Type: `GPString` with staged `ValueList`.
5. `Board Size / Difficulty`
   - Type: `GPString` with `ValueList`.
   - Values:
     - `Tiny Demo`
     - `Small`
     - `Medium`
6. `Random Seed`
   - Type: `GPLong`.
   - Optional.
7. `Amount / Radius`
   - Type: `GPDouble`.
   - Optional; enabled for buffer/power actions.
8. `Placement Feature`
   - Type: `GPFeatureRecordSetLayer`.
   - Optional; disabled until Feature Set / Buffer Defense stretch.
9. `Output Game Layer`
   - Type: derived `GPFeatureLayer`.

## 6.3 Staged action lists

### Stage 1: Survey Sweeper actions

- `New Game`
- `Reveal / Scout`
- `Flag / Mark`
- `Show Score`
- `Reset`

### Stage 2: Containment Commander actions

- `New Game`
- `Scout`
- `Treat / Clear`
- `Place Barrier`
- `Resolve Turn`
- `Show Score`
- `Reset`

### Stage 3: Bufferlands stretch actions

- `Buffer Defense`
- `Spatial Join Harvest / Score`
- optional `Suppress Hotspot`

Do not show these before implemented:

- `Clip Quarantine`
- `Dissolve Safe Zone`
- actual `Erase Hotspot`
- drawn Feature Set variants

## 6.4 ActionContext / ActionResult contracts

### `ActionContext`

Carries parsed, validated input into handlers:

```text
workspace
board_layer
mode
action
selected_cell_ids
game_state
seed
turn
board_size
amount_or_radius
placement_feature
message_sink/logger
```

### `ActionResult`

Returned by handlers:

```text
status: success | warning | error
changed_cell_ids
score_delta
state_updates
messages
log_payload
refresh_required
output_layer
```

Rules:

- `.pyt` parses parameters and emits GP messages.
- Handlers mutate board/state through store helpers.
- Every mutating action writes one `ActionLog` row.
- Every mutating action updates `display_state` for affected cells or all cells if needed.

---

## 7. ArcPy Implementation Contracts

## 7.1 Stable identity contract

- `cell_id` is the gameplay key.
- `OBJECTID` / FID is a temporary ArcGIS handle.
- Never store OIDs/FIDs in durable gameplay state.
- `ActionLog.target_cell_ids` stores `cell_id`s.
- `Adjacency` stores `cell_id` / `neighbor_id`.

## 7.2 Selection contract

For selection-based actions, use the Pro 3.6 spike result as the default contract:

1. Receive a selected `GPFeatureLayer`.
2. Primary path: open `arcpy.da.SearchCursor(layer, ...)` or `arcpy.da.UpdateCursor(layer, ...)` directly over the layer; the spike confirmed these cursors respect map-layer selection.
3. Read stable `cell_id`s from those selected rows before calling rule logic.
4. Validate selection count and selected-cell legality.
5. Pass only `cell_id`s into game rules.
6. Diagnostics path: log selected count plus classic `Describe(layer).FIDSet` / `arcpy.da.Describe(layer)['FIDSet']` values for debugging.
7. Fallback path: normalize FIDSet forms and query by explicit OID only if cursor-over-layer behavior is unavailable or a diagnostic action needs it:
   - `None`
   - empty string
   - semicolon-delimited string
   - list/tuple of IDs

Validation cases:

- no selection,
- too many selected for single-cell action,
- selected cells not in current game/session,
- selected cell already revealed,
- selected cell already invalid for action,
- stale layer or wrong layer.

## 7.3 Schema contract

### `ensure_schema(workspace, mode)`

Allowed during:

- setup,
- `New Game`,
- `Reset`,
- explicit migration/rebuild.

May:

- create geodatabase,
- create feature classes/tables,
- add fields,
- add indexes,
- seed rows.

### `assert_schema(workspace, mode)`

Used during ordinary actions.

May:

- verify datasets exist,
- verify required fields exist,
- verify `schema_version`.

Must not:

- add fields,
- delete datasets,
- mutate schema,
- repair automatically during play.

## 7.4 New Game / Reset contract

Preferred behavior:

- Create schema once if missing.
- If schema exists, clear rows and insert new board rows.
- Avoid deleting `GameBoard` while it is displayed in the map.
- Preserve path/name so layer references and symbology survive.
- If schema is incompatible, tell player to use explicit rebuild/manual cleanup.

## 7.5 Indexing contract

Add indexes during setup:

- `GameBoard.cell_id`
- `Adjacency.cell_id`
- `Adjacency.neighbor_id`
- `GameState.key`

Optional later:

- `GameBoard.display_state`
- `GameBoard.revealed`
- `GameBoard.flagged`
- `GameBoard.threat`
- `GameBoard.barrier`

## 7.6 Memory workspace contract

- Use `memory\\...`, not `in_memory\\...`, unless compatibility requires otherwise.
- Use predictable action-specific names:
  - `memory\\arcpy_game_buffer_defense`
  - `memory\\arcpy_game_spatial_join`
- Delete before reuse if exists.
- Delete after action unless intentionally displaying an intermediate.
- Never store durable game state in memory workspace.

## 7.7 Refresh / visibility contract

After each mutating action:

- Update durable fields first.
- Update `display_state`.
- Write `ActionLog`.
- Emit GP messages.
- Set derived output.
- Try `arcpy.RefreshLayer(layer_name)` if available/useful.
- If redraw lags, fields and logs are still source of truth.

Define successful visible update as:

- attribute row changed,
- `display_state` changed,
- GP message emitted,
- layer visually redraws or can be manually refreshed,
- selection behavior is documented: either retained or cleared deliberately.

---

## 8. Stage 0.5 — ArcGIS Pro Feasibility Spike

This is the first implementation task when coding starts.

### Goal

Prove the ArcGIS Pro GP interaction loop before building the game.

### What to create

A deliberately tiny Python toolbox / spike tool, separate or clearly marked temporary, that can:

1. Create a tiny 3x3 board or use an existing tiny board.
2. Load as a `.pyt` in ArcGIS Pro.
3. Show `Scenario Mode` and `Action` dropdowns.
4. Accept a `GPFeatureLayer` board layer.
5. Read selected OIDs/FIDs.
6. Resolve selected features to `cell_id`.
7. Update a field such as `display_state` or `notes`.
8. Emit GP messages with observed values.
9. Trigger derived output / refresh behavior.
10. Optionally test a minimal buffer into `memory\\...`.

### Spike actions

Recommended spike `Action` values:

- `Ping Environment`
- `Create Tiny Board`
- `Describe Selection`
- `Mark Selected`
- `Test Refresh`
- `Test Memory Buffer`
- `Reset Tiny Board`

This is not the final game UI. It is a diagnostic tool.

### Spike acceptance

Pass if:

- toolbox loads,
- parameters display correctly,
- a tiny board can be created or selected,
- selected features are read correctly,
- OIDs map to `cell_id`,
- a selected row updates,
- symbology/labels can reflect the field update,
- GP messages record observations,
- no unrecoverable locks occur after repeated runs.

Failing any item is useful data; the spike’s job is to expose risk early.

See `ideas/feasibility-spike-syntax-feature-inventory.md` for the detailed checklist.

---

## 9. Stage 1 — Survey Sweeper Minimum

## 9.1 Goal

Ship the smallest complete ArcGIS Pro game loop.

Player flow:

1. Run `New Game`.
2. Select cells on map.
3. Run `Reveal / Scout`.
4. Read spatial clue count.
5. Run `Flag / Mark` on suspected cells.
6. Win by revealing all safe cells or exactly flagging hazards.
7. Lose by revealing a hazard.

## 9.2 Theme

Use **Survey Sweeper** framing:

- board cells = survey parcels,
- hazards = contamination / protected artifacts / restricted sites,
- clue count = adjacent hazard indicators,
- reveal = survey/sample,
- flag = mark for follow-up / avoidance.

GP messages should sound GIS-native:

> “Reveal / Scout: selected 1 survey parcel -> updated revealed field and adjacent hazard clue. Display state refreshed.”

## 9.3 Board generation

Start with square grid.

Board sizes:

- `Tiny Demo`: 5x5, 4 hazards.
- `Small`: 7x7, 8 hazards.
- `Medium`: 8x8 or 9x9 only if performance is fine.

Implementation order:

1. Direct ArcPy geometry construction for square grid.
2. Optional later: `GenerateTessellation` if Pro syntax behaves well.
3. Optional later: spatially biased hazards near synthetic `RiskSources`.

## 9.4 Stage 1 actions

### `New Game`

Flow:

1. Call `ensure_schema(workspace, 'survey')`.
2. Clear rows without deleting displayed feature classes where possible.
3. Generate board with stable `cell_id`s.
4. Write `Adjacency`.
5. Place hazards deterministically from seed.
6. Compute `neighbor_count`.
7. Initialize domain fields.
8. Compute `display_state='hidden'`.
9. Write `GameState`.
10. Write `ActionLog`.
11. Emit GP message.

### `Reveal / Scout`

Flow:

1. Call `assert_schema()`.
2. Resolve selected OIDs -> `cell_id`s.
3. Validate selected cells.
4. For each selected cell:
   - if hazard: reveal and lose,
   - if safe: reveal and show clue.
5. Optional flood reveal for zero-neighbor safe cells after single reveal works.
6. Recompute counts and win/loss.
7. Update `display_state`.
8. Log and message.
9. Refresh.

### `Flag / Mark`

Flow:

1. Resolve selected OIDs -> `cell_id`s.
2. Toggle `flagged` only on unrevealed cells.
3. Recompute flag count.
4. Check exact-flag win condition.
5. Update `display_state`.
6. Log and message.

### `Show Score`

No selection required.

Message:

- mode,
- status,
- seed,
- turn/action count,
- safe revealed / total safe,
- flags / hazards,
- last message.

### `Reset`

Same seed by default if available; otherwise user-provided/default seed.

No complex history preservation.

## 9.5 Survey Sweeper acceptance

Done when:

- board appears and renders hidden,
- selection-based reveal works,
- selection-based flag works,
- clue counts are correct,
- win/loss state works,
- `ActionLog` and GP messages match visible state,
- known demo seed script works,
- no schema mutation during reveal/flag,
- map refresh behavior is documented and tolerable.

---

## 10. Stage 2 — Deterministic Selected-Cell Containment Commander

## 10.1 Goal

Reuse the same architecture for a spreading spatial threat.

Conceptual mapping:

- adjacency clue graph -> spread graph,
- survey cells -> threatened/defended territory,
- flags -> selected interventions,
- reveal/scout -> situational awareness,
- win/loss -> protect critical assets by final turn.

## 10.2 Scenario setup

`New Game` with `Scenario Mode='Containment Commander'`:

1. Use same `GameBoard` geometry.
2. Ensure Stage 2 fields exist.
3. Set `mode='containment'`.
4. Assign deterministic `susceptibility`.
5. Assign `asset_value`.
6. Mark 1–3 `critical_asset` cells.
7. Seed 1–3 threat cells.
8. Set all cells visible for target MVP.
9. Initialize AP:
   - `action_points_remaining=2`
   - `max_turns=6` or `10`
10. Compute `display_state`.
11. Log setup.

## 10.3 Deterministic spread algorithm

On `Resolve Turn`:

1. Load current threat source cells.
2. For each source, gather adjacent candidate targets from `Adjacency`.
3. Exclude existing threat cells.
4. Exclude or heavily reduce cells with `barrier=1`.
5. Suppress cells treated this turn if rule says treatment blocks spread.
6. Compute deterministic candidate score:
   - `score = source_threat_level * susceptibility * adjacency_weight`
   - optional `+ asset_pressure_modifier`
7. Sort by:
   - score descending,
   - `cell_id` ascending.
8. Infect top `N` candidates.
9. Apply simultaneously.
10. Mark `lost_asset=1` if threat reaches critical asset.
11. Update score/status.
12. Advance turn.
13. Reset AP.
14. Update `display_state`.
15. Log/message.

No randomness in target MVP. Seeded probability is future/stretch only.

## 10.4 Fixed AP rules

Default target rules:

- Each turn starts with 2 AP.
- `Scout`: 1 AP.
- `Treat / Clear`: 1 AP, up to 1 selected cell for first version.
- `Place Barrier`: 1 AP, up to 2 selected cells for first version.
- `Resolve Turn`: 0 AP, ends turn.
- `Show Score`: 0 AP.
- `New Game` / `Reset`: out-of-game.

## 10.5 Containment actions

### `Scout`

For all-visible MVP, this can be simple:

- reports selected cells’ threat/asset/susceptibility info,
- optionally sets `last_changed_turn`,
- costs 1 AP if used as a real move.

If redundant, keep it as an information action and do not make fog-of-war.

### `Treat / Clear`

- Requires selected cells.
- Costs 1 AP.
- Clears or reduces threat.
- Sets `treated_turn=current_turn`.
- May set `defended=1` for immediate/short-term suppression.

### `Place Barrier`

- Requires selected cells.
- Costs 1 AP.
- Sets `barrier=1` on up to 2 cells.
- Spread cannot enter barrier cells in target MVP.

### `Resolve Turn`

- Applies deterministic spread.
- Advances turn.
- Resets AP.
- Checks win/loss.

## 10.6 Win/loss and scoring

Recommended target conditions:

Lose immediately if:

- threat reaches any `critical_asset`, or
- threatened asset value exceeds threshold.

Win if:

- player survives through `max_turns`,
- all critical assets remain safe,
- threatened asset value remains below threshold.

Score message should report:

- current turn / max turns,
- AP remaining,
- threatened cells,
- threatened asset value,
- safe/defended asset value,
- critical asset status,
- last spread summary.

---

## 11. Stage 3 — Bufferlands Stretch Powers

## 11.1 Scope rule

Do not begin Stage 3 until:

- Survey Sweeper is shippable,
- Containment selected-cell version works,
- demo script exists,
- refresh/symbology are stable enough.

## 11.2 Power 1: Buffer Defense

### Player input

First implementation options, in priority order:

1. Selected cell(s) as buffer center proxy.
2. Existing point/line layer feature.
3. `GPFeatureRecordSetLayer` drawn geometry only after spike validates Feature Set behavior.

### GP operations

- `arcpy.analysis.Buffer(input_geometry, 'memory\\arcpy_game_buffer_defense', radius)`
- `arcpy.management.SelectLayerByLocation(GameBoard, 'INTERSECT', buffer_output)`
- Update affected cells.

### Fields updated

- `defended=1`
- `defended_until_turn` optional
- `barrier=1` optional, if hard defense
- `last_changed_turn=current_turn`
- recompute `display_state`

### Message pattern

> “Buffer Defense: Buffer + Select By Location found 6 cells within 150 map units -> defended through Turn 4.”

## 11.3 Power 2: Spatial Join Harvest / Score

Only build if `Assets` exists.

### GP operation

- Select safe/defended cells.
- Spatial Join assets to safe/defended cells or vice versa.
- Sum `asset_value`.
- Update `GameState.score`.

### Message pattern

> “Spatial Join Harvest: joined protected cells to Assets -> 8 assets saved, +42 score.”

## 11.4 Optional: Suppress Hotspot / Erase Hotspot

Prefer name `Suppress Hotspot` unless actual `Erase` is used visibly.

Implementation:

- selected threat cells or treatment zone,
- optional buffer/intersect,
- field updates to reduce/clear threat.

Actual `arcpy.analysis.Erase` is optional only.

## 11.5 Future-only powers

Move out of implementation plan unless extra time remains:

- `Clip Quarantine`
- `Dissolve Safe Zone`

These are good presentation concepts but too risky for core delivery.

---

## 12. GIS Pedagogy Layer

## 12.1 Learning objectives

By the end of the demo, viewers should understand:

- Feature classes can store application/game state.
- Attribute fields can drive both rules and cartography.
- Map selection can serve as player input.
- Adjacency / `Touches` relationships can define clues and spread.
- Buffering can model intervention zones.
- Select By Location / Intersect can transfer geometry effects to cells.
- Spatial Join can score assets saved or exposed.
- Symbology and labels can act as a lightweight UI.
- GP messages and action logs can explain turn resolution.

## 12.2 Message style

Every nontrivial action should name:

1. the spatial/data operation,
2. the game effect.

Examples:

- “Selection: 1 survey parcel selected -> revealed adjacent hazard clue count 2.”
- “Adjacency lookup: threat spread to 3 neighboring cells; 2 candidates blocked by barriers.”
- “Buffer + Select By Location: 6 cells intersected defense zone -> defended through next turn.”
- “Spatial Join: counted 8 safe assets -> +42 score.”

## 12.3 Field aliases

Use readable aliases where practical:

- `cell_id`: Cell ID
- `neighbor_count`: Nearby Hazard Clues
- `display_state`: Map Display State
- `critical_asset`: Critical Asset
- `asset_value`: Asset Value
- `defended_until_turn`: Defended Until Turn
- `treated_turn`: Last Treated Turn

## 12.4 Demo show-and-tell checkpoints

During the class demo, deliberately show:

- `GameBoard` attribute table after an action.
- `GameState.last_message`.
- `ActionLog` row.
- `Adjacency` table or explanation of neighbor pairs.
- Buffer output or selection result for Buffer Defense if Stage 3 exists.
- `Assets` layer and Spatial Join result if Stage 3 scoring exists.

---

## 13. Replacement Milestone Structure

## Milestone 0 — Planning Freeze and Scope Gates

Deliverables:

- v2 plan saved.
- feasibility-spike inventory saved.
- Minimum / Target / Stretch scope accepted.
- Deferred-feature list accepted.

Acceptance:

- Team agrees polished Survey Sweeper is shippable if later stages slip.

## Milestone 0.5 — ArcGIS Pro Feasibility Spike

Deliverables:

- temporary/minimal `.pyt`,
- tiny board,
- parameter tests,
- selection/FIDSet tests,
- OID-to-`cell_id` test,
- cursor update test,
- refresh/symbology test,
- memory buffer smoke test,
- written observations.

Acceptance:

- Select a feature in Pro, run a GP action, update state, and see/map/log the result.

Commit:

```bash
git add ideas/ toolbox/ docs/
git commit -m "spike: validate ArcGIS Pro toolbox interaction loop"
```

## Milestone 1 — Pure Survey Sweeper Rules

Deliverables:

- `toolbox/arcpy_game_rules.py`,
- `tests/test_minesweeper_rules.py`,
- grid IDs,
- adjacency,
- hazard placement,
- neighbor counts,
- reveal,
- flag,
- win/loss,
- optional flood reveal.

Acceptance:

- rules pass outside ArcGIS Pro.

Commit:

```bash
git add toolbox/arcpy_game_rules.py tests/test_minesweeper_rules.py
git commit -m "feat: add Survey Sweeper rule logic"
```

## Milestone 2 — Schema / Store / Display Foundation

Deliverables:

- `arcpy_game_schema.py`,
- `arcpy_game_store.py`,
- `arcpy_game_display.py`,
- `ensure_schema()`,
- `assert_schema()`,
- `schema_version`,
- core datasets,
- indexes,
- clear/reseed behavior,
- display-state mapper.

Acceptance:

- New board can be created repeatedly without deleting displayed feature classes during normal reset.

## Milestone 3 — Playable Survey Sweeper in ArcGIS Pro

Deliverables:

- production `arcpy_game.pyt`,
- Stage 1 action dropdown,
- selection resolution helper,
- `New Game`,
- `Reveal / Scout`,
- `Flag / Mark`,
- `Show Score`,
- `Reset`,
- `ActionLog`,
- refresh/messages.

Acceptance:

- Player can complete a Survey Sweeper game in ArcGIS Pro.

## Milestone 4 — Survey Sweeper Polish / Fallback Lock

Deliverables:

- `.lyrx` symbology,
- labels,
- field aliases,
- known demo seed,
- `docs/demo-script.md`,
- `docs/quickstart.md`,
- manual smoke test,
- project reopen/refresh check.

Acceptance:

- If development stopped here, the project is still a valid class submission.

## Milestone 5 — Pure Containment Rules

Deliverables:

- deterministic spread,
- fixed AP,
- treatment,
- barrier,
- critical assets,
- scoring,
- win/loss,
- golden scenario tests.

Acceptance:

- scripted containment scenario resolves predictably outside map UI.

## Milestone 6 — Selected-Cell Containment Commander in Pro

Deliverables:

- containment scenario setup,
- Stage 2 action dropdown,
- selected-cell `Treat / Clear`,
- selected-cell `Place Barrier`,
- `Resolve Turn`,
- containment display mapper,
- score messages,
- 5–10 turn demo script.

Acceptance:

- deterministic Containment Commander is playable in under 5 minutes.

## Milestone 7 — Bounded GIS Legitimacy Layer

Deliverables:

- GIS learning objectives in docs/README,
- synthetic `RiskSources`,
- synthetic `Assets`,
- asset exposure scoring,
- messages naming operation + effect,
- field aliases.

Acceptance:

- Demo clearly reads as GIS-native, not a generic game drawn on a map.

## Milestone 8 — Bufferlands Stretch Powers

Deliverables, priority order:

1. `Buffer Defense`
2. `Spatial Join Harvest / Score`
3. optional `Suppress Hotspot`

Acceptance:

- At least one visible core vector GP operation changes game state.

## Milestone 9 — Final Packaging / Class Demo

Deliverables:

- README update,
- quickstart,
- exact demo script,
- final manual smoke checklist,
- `.aprx` / `.ppkx` if feasible,
- fallback if packaging fails.

Acceptance:

- A classmate/instructor can open, understand, and run the project in minutes.

---

## 14. Testing Strategy

## 14.1 Pure Python tests

Use for:

- grid cell IDs,
- adjacency,
- hazard placement,
- neighbor counts,
- reveal/flood reveal,
- flag/win/loss,
- containment deterministic spread,
- AP costs,
- treatment/barrier effects,
- scoring,
- display-state mapping.

Do not import ArcPy in these tests.

## 14.2 ArcPy data tests

Run only in ArcGIS Pro Python environment:

- geodatabase creation,
- feature class/table creation,
- field existence,
- index creation,
- `GameState` read/write,
- `ActionLog` insert,
- selection helper if possible,
- memory buffer smoke test.

## 14.3 Manual ArcGIS Pro tests

Run after every major milestone:

1. Open project.
2. Add/load toolbox.
3. Run `Ping Environment` / equivalent.
4. Run `New Game`.
5. Select one feature.
6. Run legal action.
7. Run illegal action.
8. Confirm message clarity.
9. Confirm attribute fields changed.
10. Confirm symbology/labels update.
11. Confirm `ActionLog` row.
12. Close/reopen project and confirm paths/layers still work.

## 14.4 Golden demo tests

For each demo seed, maintain expected:

- board size,
- selected cells,
- action sequence,
- final board state,
- expected messages,
- expected score/status.

Use this as both regression harness and class-demo script.

---

## 15. Risks and Mitigations

## Risk: ArcGIS Pro toolbox/selection behavior differs from expectations

Mitigation:

- Run Milestone 0.5 first.
- Record exact syntax and observed values.
- Keep selected-cell flow before Feature Set drawing.

## Risk: Layer refresh/symbology does not update reliably

Mitigation:

- Test derived outputs and `RefreshLayer` in spike.
- Keep state verifiable in fields/logs.
- Preconfigure `.lyrx` rather than authoring runtime symbology.

## Risk: Schema locks break New Game/Reset

Mitigation:

- Create schema once.
- Clear/update rows instead of deleting displayed FCs.
- Keep cursors short-lived.
- Use `TestSchemaLock` before schema changes.

## Risk: Plan becomes too ambitious again

Mitigation:

- Treat Minimum as real submission target.
- Do not start Stage 3 until Stage 2 works.
- Keep deferred-feature list visible.

## Risk: Project feels like Minesweeper on a map

Mitigation:

- Use Survey Sweeper framing.
- Add GIS learning objectives.
- Use operation-aware messages.
- Add synthetic risk/assets only after core stability.

## Risk: Class demo is slow or brittle

Mitigation:

- Exact demo seed/action script.
- Operator flow checklist.
- Fallback screenshots/precomputed state if needed.
- Keep board small.

---

## 16. Deferred Feature List

Do not implement until explicitly re-approved after target is stable:

- custom UI,
- card/deck interface,
- fog-of-war,
- probabilistic spread,
- complex duration/cooldown system,
- `PlayerActions` table,
- real data,
- hex board before square board,
- Feature Set drawing before selected-cell actions work,
- actual `Erase` dependency,
- `Clip Quarantine`,
- `Dissolve Safe Zone`,
- persistent `Barriers` / `Treatments` feature classes,
- per-turn Spatial Analyst / Network Analyst.

---

## 17. First Implementation Step When Approved

When Griffin asks to start coding, do **not** begin with the full game.

Begin with:

1. Create the feasibility spike `.pyt`.
2. Test it inside ArcGIS Pro tonight/next available Pro session.
3. Fill out the spike inventory results.
4. Adjust the plan based on observed ArcGIS behavior.
5. Then implement Survey Sweeper rules and schema.

Recommended first commit after spike:

```bash
git add ideas/feasibility-spike-results.md toolbox/arcpy_game_spike.pyt
 git commit -m "spike: validate ArcGIS Pro GP interaction loop"
```

If the spike fails, fix the architecture before writing game rules.
