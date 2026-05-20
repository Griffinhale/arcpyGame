# Minesweeper to Containment Commander Implementation Plan

> **For Hermes:** This is a planning-only artifact. Do not start coding until Griffin explicitly asks. When implementation begins, use small vertical slices and commit at reasonable checkpoints.

**Goal:** Build a staged ArcGIS Pro + ArcPy game where geoprocessing is the gameplay verb: first prove the loop with Map Minesweeper / Survey Sweeper, then evolve the same board/state/controller architecture into Containment Commander, then add Bufferlands-style geoprocessing powers as the demo polish layer.

**Architecture:** Use one small feature-class board, durable state fields/tables, precomputed adjacency, one Python toolbox controller with an `Action` dropdown, map selections / Feature Set geometry as player input, and preconfigured symbology/labels as the renderer. Avoid custom UI, real-time loops, schema mutation during play, Spatial Analyst / Network Analyst dependencies, and large boards.

**Tech Stack:** ArcGIS Pro, ArcPy, Python toolbox (`.pyt`), file geodatabase feature classes/tables, core vector geoprocessing tools, `arcpy.da` cursors, `memory\\...` intermediates, `.lyrx` symbology layers.

---

## 1. Source Context Read Before Planning

This plan is based on the existing project notes:

- `README.md`
  - Original concept set and ArcGIS-as-game-engine premise.
  - Strong warning that the game should use GIS mechanics directly, not merely display a game on a map.
  - Identified Map Minesweeper as the safest polished prototype and Bufferlands as the flashiest stretch.
- `ideas/delphi-panel-shortlist.md`
  - Final consensus: build **Map Minesweeper / Survey Sweeper first**, then **Containment Commander**, then **Bufferlands-style powers**.
  - Strongest design principle: geoprocessing is the verb.
  - Best implementation pattern: one controller tool, feature-class state, selections/editing as input, symbology as display.
- `ideas/arcpy-geoprocessing-ui-environment-constraints.md`
  - GP pane is form-based, not a custom UI framework.
  - Use `GPString` `ValueList` action dropdown, `GPFeatureLayer`, optional `GPFeatureRecordSetLayer`, GP messages, derived outputs, and preconfigured symbology.
  - Store state in fields/tables; avoid per-turn schema changes.
  - Keep boards around 20–75 features and turns around 5–15.

---

## 2. North Star Design

### One-Sentence Pitch

**A map-based puzzle/strategy game where selecting, buffering, intersecting, erasing, clipping, dissolving, and spatial joining are the moves.**

### Design Promise

The class-demo line should be:

> “Every action is a GIS operation. ArcPy is not drawing the game; ArcPy is resolving the game.”

### Non-Goals

Do not build:

- A custom game UI.
- A card/deck interface.
- A real-time animation loop.
- A large simulation.
- RPG inventory or narrative bloat.
- Per-turn raster, hydrology, Network Analyst, or Spatial Analyst operations.
- A generalized game framework before a playable vertical slice exists.

---

## 3. Recommended Project Structure

Create this structure during implementation:

```text
/workspace/projects/arcpyGame/
  README.md
  ideas/
    delphi-panel-shortlist.md
    arcpy-geoprocessing-ui-environment-constraints.md
    minesweeper-to-containment-implementation-plan.md
  toolbox/
    arcpy_game.pyt
    arcpy_game_core.py
    arcpy_game_schema.py
    arcpy_game_rules.py
    arcpy_game_gp.py
  data/
    README.md
    arcpy_game.gdb/
      GameBoard
      GameState
      ActionLog
      Adjacency
      PlayerActions          # optional in Stage 2+
      Barriers               # optional in Stage 2+
      Treatments             # optional in Stage 2+
  symbology/
    GameBoard_Minesweeper.lyrx
    GameBoard_Containment.lyrx
    Barriers.lyrx
    Treatments.lyrx
  docs/
    demo-script.md
    quickstart.md
  tests/
    test_minesweeper_rules.py
    test_containment_rules.py
    test_schema_contract.py
```

### File Responsibilities

- `toolbox/arcpy_game.pyt`
  - ArcGIS Pro Python toolbox entrypoint.
  - Defines `GameController` tool and GP parameters.
  - Keeps validation lightweight.
- `toolbox/arcpy_game_core.py`
  - Shared controller dispatch and utility functions.
  - Reads/writes `GameState`, writes `ActionLog`, refreshes layers.
- `toolbox/arcpy_game_schema.py`
  - Creates/validates geodatabase, feature classes, fields, indexes, and seed board.
  - Only called by `New Game`, `Reset`, or setup tools — not every turn.
- `toolbox/arcpy_game_rules.py`
  - Pure-ish Python game rules that are testable without Pro map UI.
  - Minesweeper reveal/flag/win logic.
  - Containment spread/action/scoring logic.
- `toolbox/arcpy_game_gp.py`
  - Thin wrappers around ArcPy tools: Generate Tessellation/Fishnet, Buffer, Intersect, Erase/SelectLayerByLocation, Dissolve, Spatial Join.
  - Keeps geoprocessing operations isolated from rule decisions.

---

## 4. Core Data Model

## 4.1 `GameBoard` Feature Class

Geometry: polygon cells. Start with generated squares or hexes; optionally later use curated parcels.

### Required Fields for Stage 1

- `cell_id` — long or text; stable unique gameplay ID.
- `row_idx` — long; useful for generated grid tests/debugging.
- `col_idx` — long; useful for generated grid tests/debugging.
- `is_hazard` — short integer boolean, `0/1`.
- `revealed` — short integer boolean, `0/1`.
- `flagged` — short integer boolean, `0/1`.
- `neighbor_count` — short integer; count of adjacent hazards.
- `state` — text; symbol driver.
  - `hidden`
  - `revealed_empty`
  - `revealed_clue`
  - `flagged`
  - `hazard_hit`
  - `hazard_revealed_win`
- `turn_revealed` — long; `-1` or null when unrevealed.
- `notes` — text; optional debug/player-facing note.

### Additional Fields for Stage 2

- `threat` — short integer boolean, `0/1`.
- `threat_level` — short integer, suggested `0–3`.
- `susceptibility` — double, suggested `0.0–1.0`.
- `protected` — short integer boolean, `0/1`.
- `treated_turn` — long; last turn treated, `-1` or null if never.
- `barrier` — short integer boolean, `0/1`.
- `asset_value` — double or long; score weight.
- `visible` — short integer boolean, `0/1` for fog-of-war.
- `spread_seed` — double; deterministic per-cell random value.
- `last_changed_turn` — long; useful for labels/debugging.

### Optional Stage 3 Fields

- `buffered` — short integer boolean; currently protected by buffer action.
- `quarantined` — short integer boolean; inside quarantine area.
- `safe_zone_id` — long/text; dissolve grouping ID.
- `harvest_score` — double; score contribution from Spatial Join / saved assets.

## 4.2 `Adjacency` Table

Precompute once per new board.

Fields:

- `cell_id` — source cell.
- `neighbor_id` — adjacent cell.
- `touch_type` — text; `edge`, `corner`, `overlap`, or `near`.
- `weight` — double; default `1.0`, optionally lower for corner-only adjacency.

Rules:

- For square-grid Minesweeper, include 8-way adjacency.
- For Containment Commander, default to 4-way/edge adjacency if using square cells, or polygon `Touches` if using parcels/hexes.
- Keep the table small and query it into an in-memory Python dictionary each action.

## 4.3 `GameState` Table

One-row key/value table is simplest.

Fields:

- `key` — text.
- `value_text` — text.
- `value_num` — double.

Suggested keys:

- `mode` — `minesweeper` or `containment`.
- `status` — `ready`, `playing`, `won`, `lost`.
- `turn` — current turn number.
- `seed` — deterministic random seed.
- `board_rows` / `board_cols` or `board_size`.
- `hazard_count`.
- `safe_revealed_count`.
- `flags_count`.
- `action_points_remaining`.
- `max_turns`.
- `score`.
- `threat_count`.
- `threat_threshold`.
- `protected_assets_remaining`.
- `last_message`.

## 4.4 `ActionLog` Table

Fields:

- `log_id` — long/autoincrement if available or explicit sequential ID.
- `turn` — long.
- `action` — text.
- `target_ids` — text; comma-separated cell IDs or feature OIDs.
- `result` — text; concise outcome.
- `score_delta` — double.
- `timestamp` — date.

Purpose:

- Durable feedback beyond transient GP messages.
- Helps debugging and class demo narration.

## 4.5 Optional Stage 2/3 Feature Classes

### `Barriers`

Geometry: line or polygon.

Fields:

- `barrier_id`
- `placed_turn`
- `duration_turns`
- `strength`
- `active`

### `Treatments`

Geometry: point, line, or polygon depending action.

Fields:

- `treatment_id`
- `placed_turn`
- `radius`
- `effect`
- `active`

### `PlayerActions`

Optional table if action costs/cooldowns outgrow hardcoded constants.

Fields:

- `action_name`
- `cost_ap`
- `cooldown_turns`
- `requires_selection`
- `requires_geometry`
- `enabled`

Do not add this until Stage 2 or 3 needs it. For Stage 1, hardcode actions in the controller.

---

## 5. Python Toolbox Layout

## 5.1 `arcpy_game.pyt` Controller Tool

Use one tool class:

```text
Toolbox: ArcPy Game
  Tool: Game Controller
```

### Parameters

1. `Game Workspace`
   - Type: `DEWorkspace` or `GPString` path.
   - Default: project `data/arcpy_game.gdb` if possible.
2. `Game Layer`
   - Type: `GPFeatureLayer`.
   - Required for most actions after setup.
3. `Action`
   - Type: `GPString` with `ValueList`.
   - Values by stage:
     - `New Game`
     - `Reveal / Scout`
     - `Flag / Mark`
     - `Treat / Clear`
     - `Place Barrier`
     - `Buffer Defense`
     - `Erase Hotspot`
     - `Clip Quarantine`
     - `Dissolve Safe Zone`
     - `Spatial Join Harvest / Score`
     - `Resolve Turn`
     - `Show Score`
     - `Reset`
4. `Scenario Mode`
   - Type: `GPString` with `ValueList`.
   - Values: `Survey Sweeper`, `Containment Commander`.
   - Enabled mainly for `New Game`.
5. `Board Size / Difficulty`
   - Type: `GPString` with `ValueList`.
   - Values: `Tiny Demo`, `Small`, `Medium`.
   - Stage 1 mapping: `5x5`, `7x7`, `9x9` or equivalent 25/49/81 cells. Prefer <= 75 for class demo.
6. `Placement Feature`
   - Type: `GPFeatureRecordSetLayer`.
   - Optional for barriers, buffer center/line, treatment zone, quarantine geometry.
7. `Amount / Radius`
   - Type: `GPDouble`.
   - Optional; default reasonable values.
8. `Random Seed`
   - Type: `GPLong`.
   - Optional; if blank, generate but store in `GameState`.
9. `Output Game Layer`
   - Type: derived `GPFeatureLayer`.

### Validation Rules

Keep validation cheap:

- `New Game`
  - Does not require selected features.
  - Requires writable workspace.
  - Warns that existing board state may be reset.
- `Reveal / Scout`
  - Requires one or more selected board cells.
  - Error if game status is `won` or `lost`.
- `Flag / Mark`
  - Requires one or more selected board cells.
  - Error if selected cells are already revealed.
- `Treat / Clear`
  - Requires selected board cells.
  - Error if no action points remain.
- `Place Barrier`, `Buffer Defense`, `Clip Quarantine`
  - Requires placement geometry or selected geometry depending implementation.
  - Warn if radius is large enough to affect too many cells.
- `Resolve Turn`
  - Requires active containment game.
  - Error if game already ended.
- `Show Score`
  - No selection required.
- `Reset`
  - Requires workspace and existing game datasets.

### Execution Rules

Every action should:

1. Load `GameState`.
2. Validate schema.
3. Read selected `cell_id`s if relevant.
4. Dispatch to a small action handler.
5. Update fields/tables using short-lived `arcpy.da` cursors.
6. Write one `ActionLog` entry.
7. Add concise GP messages.
8. Set derived output.
9. Call `arcpy.RefreshLayer("GameBoard")` where useful.

---

## 6. Stage 1 — Map Minesweeper / Survey Sweeper MVP

## 6.1 Goal

Prove the ArcGIS game loop with the smallest complete game:

1. Generate a small board.
2. Hide hazards/artifacts/contamination.
3. Player selects cells on the map.
4. `Reveal / Scout` reveals cells and clue counts.
5. `Flag / Mark` marks suspected hazards.
6. Win/loss state is stored and rendered.

## 6.2 Theme Recommendation

Use **Survey Sweeper** rather than generic Minesweeper in presentation copy.

Suggested framing:

- Cells are survey parcels.
- Hidden hazards are contamination/artifact/protected-site cells.
- Neighbor counts are environmental survey clues.
- Flags are marked restricted parcels.

This makes the GIS connection stronger than “Minesweeper on a square grid.”

## 6.3 Board Generation Plan

### Initial MVP Board

Use generated square or hex cells in a file geodatabase.

Implementation choices:

- Safer: use ArcPy geometry construction with cursors for a simple square grid.
- More GIS-flavored: use `arcpy.management.GenerateTessellation` if available/comfortable.
- Avoid external real data until the core loop works.

Board sizes:

- `Tiny Demo`: 5x5 = 25 cells, 4 hazards.
- `Small`: 7x7 = 49 cells, 8 hazards.
- `Medium`: 8x8 = 64 cells or 9x9 = 81 cells only if performance is fine.

### Hazard Placement

- Use deterministic `random.Random(seed)`.
- Choose hazard cells after board creation.
- Store `is_hazard=1`.
- For the first version, pure random placement is fine.
- Stretch: spatially biased hazards near synthetic “road/river/industry” line features.

### Adjacency Precomputation

For generated grids:

- Store `row_idx` and `col_idx`.
- Create 8-way neighbor pairs for Minesweeper.
- Write `Adjacency` rows directly from row/col offsets.

For later parcel/hex boards:

- Compute neighbors using polygon touches/intersections.
- Cache in `Adjacency`.

### Neighbor Count

For each cell:

- Look up adjacent `neighbor_id`s.
- Count neighbors where `is_hazard=1`.
- Store `neighbor_count`.

## 6.4 Stage 1 Actions

### `New Game`

Flow:

1. Create/clear `GameBoard`, `GameState`, `Adjacency`, `ActionLog`.
2. Create required fields if missing.
3. Generate cells and stable `cell_id`s.
4. Precompute adjacency.
5. Place hazards with seeded randomness.
6. Compute `neighbor_count`.
7. Initialize visual state:
   - `revealed=0`
   - `flagged=0`
   - `state='hidden'`
   - `turn_revealed=-1`
8. Write `GameState`:
   - `mode='minesweeper'`
   - `status='playing'`
   - `turn=0`
   - `hazard_count=N`
   - `safe_revealed_count=0`
9. Add GP message:
   - “Survey Sweeper started: 49 cells, 8 hidden hazards. Select cells and run Reveal / Scout.”

Acceptance:

- Board appears with all cells hidden.
- Attribute table has all required fields.
- Neighbor counts are populated but not visually shown for hidden cells.

### `Reveal / Scout`

Flow:

1. Read selected cells from `Describe(layer).FIDSet`.
2. Error if no cells selected.
3. Error or warning if selected cell is flagged.
4. If selected cell is hazard:
   - Set `revealed=1`, `state='hazard_hit'`.
   - Set `GameState.status='lost'`.
   - Reveal all hazards optionally as `state='hazard_revealed_win'` or `hazard_hit`.
   - Log loss.
5. If selected cell is safe:
   - Reveal it.
   - Set `state='revealed_empty'` if `neighbor_count=0`; otherwise `state='revealed_clue'`.
   - Set `turn_revealed=current_turn`.
6. If `neighbor_count=0`, run recursive flood reveal if feasible.
7. Recompute `safe_revealed_count`.
8. Check win condition.
9. Add GP messages summarizing revealed count and status.

### Recursive Zero-Neighbor Reveal

Implement after single-cell reveal works.

Algorithm:

1. Start queue with selected safe zero-neighbor cells.
2. Maintain visited set.
3. For each zero-neighbor cell:
   - Reveal all adjacent safe cells.
   - If an adjacent safe cell also has `neighbor_count=0`, enqueue it.
4. Never reveal hazards.
5. Do not reveal flagged cells unless design chooses to auto-unflag. Safer: skip flagged cells.

Testing priority:

- This logic should be pure Python using `dict[cell_id] -> cell_state` and `adjacency` before integrating with ArcPy cursors.

### `Flag / Mark`

Flow:

1. Read selected cells.
2. Error if no selection.
3. For each selected unrevealed cell:
   - Toggle `flagged`.
   - If now flagged, `state='flagged'`.
   - If unflagged, `state='hidden'`.
4. Do not allow flagging revealed cells.
5. Recompute `flags_count`.
6. Check win condition.
7. Log action and add GP message.

### `Show Score`

Message content:

- Mode.
- Status.
- Turn.
- Revealed safe cells / total safe cells.
- Flags / hazards.
- Remaining unrevealed safe cells.
- If game ended, show win/loss reason.

### `Reset`

MVP behavior:

- Equivalent to `New Game` with same parameters or current seed depending user choice.
- Do not try to preserve complex history.

## 6.5 Win/Loss Conditions

Lose:

- Revealing a hazard immediately loses for MVP.

Win if either:

- All safe cells are revealed; or
- All hazards are flagged and no safe cells are incorrectly flagged.

Recommended MVP rule:

- Primary win: all safe cells revealed.
- Secondary win: exact hazard flag set.

This avoids accidental win when the player flags many cells incorrectly.

## 6.6 Symbology Plan

Drive symbology from `state` and labels from fields.

Suggested styles:

- `hidden`: medium gray fill, thin white outline.
- `flagged`: orange/yellow fill with flag icon if possible.
- `revealed_empty`: pale green or transparent fill.
- `revealed_clue`: light blue fill, label `neighbor_count`.
- `hazard_hit`: red fill, hazard symbol/label.
- `hazard_revealed_win`: muted red/purple fill.

Label expression:

- Show `neighbor_count` only where `revealed=1 AND neighbor_count > 0`.
- Optionally show `⚑` or `F` for flagged cells if symbolization cannot handle icons.

Layer setup:

- Create `symbology/GameBoard_Minesweeper.lyrx` during implementation.
- Use preconfigured layer in `.aprx` if packaging.
- Do not rely on runtime symbol authoring for the MVP.

## 6.7 Stage 1 Testing Strategy

### Pure Rule Tests

Create tests for:

- Hazard placement count is deterministic by seed.
- Adjacency for a 3x3 board has correct neighbor counts.
- Revealing a safe clue cell reveals one cell.
- Revealing a zero cell flood-reveals expected region.
- Revealing a hazard returns loss.
- Toggling a flag changes state and prevents reveal.
- Win triggers when all safe cells are revealed.
- Win triggers only when exact hazards are flagged.

### ArcPy Integration Tests

If ArcPy is available:

- Create a temporary file geodatabase.
- Run `New Game` setup helper.
- Validate required fields exist.
- Validate row count equals expected board size.
- Validate `Adjacency` has rows.
- Run action handlers against known selected IDs via helper functions.

### Manual ArcGIS Pro Tests

Checklist:

1. Add toolbox to ArcGIS Pro.
2. Run `New Game`.
3. Confirm board renders hidden.
4. Select one cell and run `Reveal / Scout`.
5. Confirm map updates and label appears.
6. Select one cell and run `Flag / Mark`.
7. Confirm flag state appears.
8. Reveal until win/loss.
9. Confirm `GameState`, `ActionLog`, and GP messages match visual result.

## 6.8 Stage 1 MVP Acceptance Criteria

Stage 1 is done when:

- `New Game` creates a playable 25–64 cell board.
- Player can select cells on the map and run `Reveal / Scout`.
- Player can select cells and run `Flag / Mark`.
- Revealed clue counts are correct.
- Zero-cell recursive reveal works or is explicitly disabled with a documented reason.
- Win/loss status is stored in `GameState` and visible through `Show Score`.
- Symbology makes hidden/revealed/flagged/hazard states obvious.
- Turns/actions complete quickly on a small board.
- No schema changes occur during reveal/flag actions.
- The project has a reliable fallback demo even if later stages are incomplete.

---

## 7. Stage 2 — Containment Commander

## 7.1 Goal

Reuse the Stage 1 architecture to create the main game: a spreading spatial threat that the player contains with limited actions/resources.

## 7.2 Conceptual Conversion from Minesweeper

Minesweeper concepts map directly to Containment Commander:

- Hidden hazards -> hidden threat seeds.
- Neighbor counts -> local risk/threat adjacency clues.
- Revealed cells -> visible / scouted cells.
- Flags -> marked suspected threat / protected cells.
- Reveal action -> Scout action.
- Board adjacency -> spread graph.
- Win/loss -> contain below threshold by final turn.

Do not fork the architecture. Add fields and new action handlers while preserving:

- `GameBoard` as board layer.
- `GameState` as global state.
- `ActionLog` as durable event history.
- `Adjacency` as precomputed graph.
- `GameController` as the only UI surface.

## 7.3 Containment Setup

`New Game` with `Scenario Mode='Containment Commander'` should:

1. Generate or reuse board geometry.
2. Ensure Stage 2 fields exist.
3. Assign `asset_value` to cells.
   - MVP: random deterministic values like `1–10`.
   - Better demo: higher values clustered near a synthetic town/asset zone.
4. Assign `susceptibility`.
   - MVP: deterministic random `0.25–1.0`.
   - Stretch: spatially biased from synthetic land-use/roads/water.
5. Pick 1–3 starting infected/threat cells.
6. Set `threat=1`, `threat_level=1 or 2` for seeds.
7. Set some protected/high-value assets.
8. Initialize `visible`.
   - Simple mode: all cells visible.
   - Fog mode: only scouted/near threat visible.
9. Initialize resources:
   - `turn=1`
   - `max_turns=10`
   - `action_points_remaining=2` per turn.
   - `threat_threshold`, e.g. 35% of total asset-weighted board.
10. Set `state` values for symbology.

## 7.4 Spread Algorithm

### MVP Deterministic Spread

Each `Resolve Turn`:

1. Load current threatened cells.
2. For each threatened source cell:
   - Consider adjacent cells from `Adjacency`.
   - Skip cells with `barrier=1` if barrier blocks spread.
   - Skip or reduce chance for `protected=1` / recently treated cells.
3. Compute candidate risk score:
   - `risk = source_threat_level * susceptibility * adjacency_weight`.
   - Apply modifiers:
     - `barrier`: `risk = 0` or multiply by `0.1`.
     - `treated_turn == current_turn`: `risk = 0`.
     - `protected`: multiply by `0.3`.
4. Use deterministic seeded randomness:
   - Seed per turn/cell from stored game seed: `hash(seed, turn, source_id, target_id)` or `random.Random(f"{seed}:{turn}:{source}:{target}")`.
   - If random roll < risk threshold, spread to target.
5. Update new threats after evaluating all sources; do not let newly infected cells spread until next turn.
6. Increase `threat_level` for existing threats optionally.
7. Decrease treatment/protection duration if using duration.
8. Score assets lost/saved.
9. Advance turn and reset action points.
10. Check win/loss.

### Simpler Fully Deterministic Option

If seeded probability is too fiddly, use this for MVP:

- Sort candidate target cells by `risk DESC`, then `cell_id`.
- Infect top `N` candidates per turn, where `N` depends on difficulty.

This is easier to demo and test, while still feeling spatial.

## 7.5 Turn Resolution Order

Use a fixed order so messages/tests are predictable:

1. Validate game is active.
2. Apply any queued placement geometries from the current action, if relevant.
3. Expire old temporary barriers/treatments.
4. Resolve treatment effects.
5. Resolve barrier/protection effects.
6. Compute spread candidates from threat cells.
7. Apply spread simultaneously.
8. Update visibility/fog-of-war.
9. Update score and status.
10. Advance `turn`.
11. Reset action points.
12. Log and message summary.

## 7.6 Stage 2 Actions

### `Reveal / Scout`

Purpose:

- Reuse Stage 1 reveal action as scouting/fog-of-war.

Effect:

- Selected cells get `visible=1`.
- If a scouted cell has threat, reveal its threat state.
- Optionally reveal neighbor threat clue count using existing `neighbor_count` pattern, renamed conceptually as “risk clue.”
- Costs 1 action point.

Message:

- “Scouted 3 cells. Found 1 active threat and 2 high-risk neighbors.”

### `Treat / Clear`

Purpose:

- Remove or reduce threat in selected cells.

Effect:

- Costs 1 action point per selected cell or per action.
- If selected cell has `threat=1`:
  - Set `threat=0` or reduce `threat_level`.
  - Set `treated_turn=current_turn`.
  - Set `protected=1` for one turn optionally.
- If selected cell has no threat:
  - Still set `treated_turn` / `protected` to prevent near-future spread.

Message:

- “Treatment cleared 2 cells and protected them through next turn.”

### `Place Barrier`

Two MVP options:

Option A — selected-cell barrier:

- Player selects cells.
- Tool sets `barrier=1` on those cells.
- Spread cannot enter or leave barrier cells, or risk is heavily reduced.
- Cheapest to implement.

Option B — drawn-line barrier:

- Player draws a line with `GPFeatureRecordSetLayer`.
- Tool selects cells intersecting/touched by line.
- Sets `barrier=1` for affected cells.
- More geoprocessing-visible and demo-friendly.

Recommended implementation order:

1. Implement selected-cell barrier first.
2. Add drawn-line barrier after Stage 2 core loop works.

### `Buffer Defense`

Stage 2 or Stage 3 bridge action.

Effect:

- Player provides point/line/polygon placement geometry.
- Tool runs `Buffer` into `memory\\buffer_defense`.
- Selects/intersects board cells with buffer.
- Sets `protected=1` or `barrier=1` for affected cells.
- Costs action points based on radius/affected cells.

Message:

- “Buffer Defense protected 7 cells for 2 turns.”

### `Resolve Turn`

Purpose:

- Advance the spreading threat.

Effect:

- Applies spread algorithm.
- Updates score/status.
- Resets action points.

Message:

- “Turn 4 resolved: threat spread to 3 cells, 1 barrier blocked spread, 42 asset points remain safe.”

### `Show Score`

Message content:

- Turn / max turns.
- Threatened cells and threatened asset value.
- Protected/safe asset value.
- Action points remaining.
- Win/loss threshold.
- Last event summary.

## 7.7 Scoring

MVP score:

```text
score = safe_asset_value - threatened_asset_value - action_cost_penalty
```

Better class-demo score:

- `asset_value` saved at game end.
- Bonus for connected safe zones.
- Penalty for threat reaching protected/high-value cells.
- Penalty for excessive action use.

Win:

- Reach `max_turns` with threat below threshold and protected assets intact.

Lose:

- Threat exceeds area or asset threshold.
- Threat reaches a special protected asset cell.
- Turn limit expires with too much threat.

Recommended MVP:

- Win after 10 turns if threatened asset value <= 30% of total asset value.
- Lose immediately if threat reaches any `protected=1` critical asset cell, or if threat exceeds 50% of total asset value.

## 7.8 Fog-of-War

Optional after base containment works.

Simple model:

- `visible=1` for scouted cells, treated cells, barrier cells, and cells adjacent to player actions.
- Hidden cells still participate in spread, but symbology shows them as unknown.
- `Show Score` can report known threat separately from total threat if desired.

Do not let fog-of-war complicate the MVP. All-visible containment is acceptable for first playable Stage 2.

## 7.9 Stage 2 Symbology

Drive from `state` or a computed display field such as `state`:

- `unknown`: dark gray.
- `safe`: pale green.
- `threat_1`: yellow/orange.
- `threat_2`: orange/red.
- `threat_3`: dark red.
- `treated`: blue/teal hatch.
- `barrier`: black or purple outline/hatch.
- `protected_asset`: gold outline.
- `lost_asset`: red crosshatch.

Labels:

- Asset value for visible cells.
- Threat level for visible threat cells.
- Optional clue count / risk marker.

## 7.10 Performance Constraints

- Keep board <= 75 cells.
- Load adjacency into Python once per action.
- Use set/dict operations for spread decisions.
- Use one or two update cursor passes per action, not one cursor per cell.
- Use `memory\\...` only for small buffer/intersection actions.
- Delete or overwrite memory intermediates each action.
- Do not run full polygon overlay for basic adjacency spread; use precomputed `Adjacency`.

## 7.11 Stage 2 Acceptance Criteria

Stage 2 is done when:

- `New Game` can start a containment scenario using the same datasets/controller.
- Threat starts on the board and is visibly distinct.
- Player has limited action points per turn.
- `Scout`, `Treat`, and `Place Barrier` work from selected cells.
- `Resolve Turn` spreads threat predictably by adjacency.
- Barriers/treatments alter spread outcomes.
- Win/loss checks are implemented.
- `Show Score` explains the scenario status.
- A 5–10 turn scenario is playable in under 5 minutes.

---

## 8. Stage 3 — Bufferlands-Style Geoprocessing Powers

## 8.1 Goal

Add visible geoprocessing “wow” moves without building a custom card/deck UI.

Use the same `Action` dropdown. Keep powers few, legible, and tied to core containment rules.

Recommended Stage 3 minimum:

1. `Buffer Defense`
2. `Erase Hotspot`
3. `Spatial Join Harvest / Score`

Then add `Clip Quarantine` and `Dissolve Safe Zone` if time allows.

## 8.2 Power: Buffer Defense

### Player Input

- `Placement Feature`: point, line, or polygon drawn in GP parameter.
- `Amount / Radius`: buffer distance in map units.

### ArcPy / GP Operation

1. `arcpy.analysis.Buffer(placement, "memory\\buffer_defense", radius)`.
2. `arcpy.management.SelectLayerByLocation(GameBoard, "INTERSECT", "memory\\buffer_defense")` or `arcpy.analysis.Intersect` if a physical intermediate is useful.
3. Update selected/intersecting cells.

### Fields Updated

- `protected=1`
- `barrier=1` optionally if this is a hard quarantine buffer.
- `last_changed_turn=current_turn`
- `state='protected'` or composite display state.

### Message

- “Buffer Defense: buffered 150 meters and protected 6 cells. Cost: 1 AP.”

### Simplicity Guardrails

- Cap radius.
- Cap affected cells.
- Use default radius if blank.
- Do not persist buffer geometry unless useful for demo; optional copy into `Treatments`/`Barriers` later.

## 8.3 Power: Erase Hotspot

### Player Input

Option A:

- Select threat cells.

Option B:

- Draw treatment zone polygon/point with radius.

### ArcPy / GP Operation

For selected cells:

- No heavy GP needed; update selected threat cells.

For geometry zone:

1. If point/line, buffer into `memory\\erase_zone`.
2. Select/intersect `GameBoard` with zone.
3. Clear or reduce threat in affected cells.

Note: Actual `Erase` requires Advanced license in some ArcGIS contexts depending tool availability. For maximum compatibility, implement the gameplay effect with `SelectLayerByLocation` + field updates and describe it as “Erase Hotspot” conceptually. If the local license supports `arcpy.analysis.Erase`, optionally use it for a visual treatment-zone output, not as a required mechanic.

### Fields Updated

- `threat=0` or `threat_level=max(0, threat_level-2)`.
- `treated_turn=current_turn`.
- `protected=1` for one turn.
- `state='treated'` or `safe` if cleared.

### Message

- “Erase Hotspot cleared 3 active threat cells and suppressed spread this turn.”

## 8.4 Power: Clip Quarantine

### Player Input

- Draw polygon quarantine zone or select an existing polygon/area.

### ArcPy / GP Operation

1. Copy/draw quarantine geometry to `memory\\quarantine_zone`.
2. Use `SelectLayerByLocation(GameBoard, "INTERSECT", quarantine_zone)`.
3. Mark cells inside zone as `quarantined=1`.
4. During spread, block or reduce spread crossing from inside to outside and outside to inside.

Optional visible operation:

- Use `arcpy.analysis.Clip(GameBoard, quarantine_zone, "memory\\quarantine_cells")` for a demo intermediate, but do not depend on storing clipped fragments for core gameplay.

### Fields Updated

- `quarantined=1`
- `barrier=1` or spread-crossing rule flag.
- `last_changed_turn=current_turn`

### Message

- “Clip Quarantine isolated 8 cells. Spread across the quarantine boundary is blocked for 2 turns.”

### Simplicity Guardrails

- Quarantine is a cell-state effect, not a permanent geometry split.
- Do not change `GameBoard` geometry during play.

## 8.5 Power: Dissolve Safe Zone

### Player Input

- Select safe/protected cells or run globally.

### ArcPy / GP Operation

1. Select cells where `threat=0 AND protected=1` or selected safe cells.
2. `arcpy.management.Dissolve(selected_cells, "memory\\safe_zone_dissolve", dissolve_field)`.
3. Use output for visual score summary or optional layer.

### Fields Updated

- `safe_zone_id` if assigning connected groups.
- `harvest_score` or `score` bonus.
- No core geometry mutation in `GameBoard`.

### Message

- “Dissolve Safe Zone merged 11 protected cells into 2 safe zones for +15 score.”

### Simplicity Guardrails

- Treat dissolve output as a visual/score layer, not the new board.
- Keep connected-zone logic simple; either use selected cells as one group or compute groups from `Adjacency`.

## 8.6 Power: Spatial Join Harvest / Score

### Player Input

- Usually no selection required; optionally selected safe/protected zone.

### ArcPy / GP Operation

Possible data setup:

- Add synthetic `Assets` points or polygons with `asset_value`.
- Spatially join assets to safe/protected board cells or dissolved safe zones.

Flow:

1. Build/select safe/protected cells.
2. `arcpy.analysis.SpatialJoin(safe_cells, Assets, "memory\\safe_asset_join", ...)`.
3. Sum asset values.
4. Update `GameState.score`.

Simpler MVP without separate `Assets` feature class:

- Sum `asset_value` directly from `GameBoard` where safe/protected.
- Still call the action `Spatial Join Harvest` only after adding an actual tiny `Assets` layer for demo legitimacy.

### Fields Updated

- `harvest_score` on cells or safe zones.
- `GameState.score`.

### Message

- “Spatial Join Harvest counted 12 protected assets worth 84 points.”

## 8.7 Stage 3 Acceptance Criteria

Stage 3 is done when:

- At least two powers visibly run real core vector GP operations.
- Powers update `GameBoard` fields and affect containment outcomes.
- Intermediate outputs use `memory\\...` and do not clutter the geodatabase.
- Messages explicitly name the geoprocessing operation and gameplay effect.
- The demo can show “select/draw geometry -> run GP action -> map state changes.”
- No custom deck/card UI exists.

---

## 9. Staged Milestones and Vertical Slices

## Milestone 0 — Repo/Data Skeleton Plan Only

Objective:

- Prepare implementation structure when coding starts.

Deliverables:

- This plan.
- No code yet.

Acceptance:

- Plan saved at `ideas/minesweeper-to-containment-implementation-plan.md`.

## Milestone 1 — Rule Logic Without ArcGIS UI

Objective:

- Build testable game rules separately from GP tool UI.

Tasks:

1. Create `toolbox/arcpy_game_rules.py`.
2. Add pure Python helpers for:
   - grid adjacency,
   - hazard placement,
   - neighbor counts,
   - reveal/flood reveal,
   - flag toggle,
   - win/loss checks.
3. Create `tests/test_minesweeper_rules.py`.
4. Run tests outside ArcGIS if possible.
5. Commit.

Acceptance:

- Minesweeper rules pass tests without opening ArcGIS Pro.

## Milestone 2 — Schema and Board Creation

Objective:

- Create the file geodatabase schema and generated board.

Tasks:

1. Create `toolbox/arcpy_game_schema.py`.
2. Implement workspace/geodatabase creation.
3. Implement `GameBoard`, `GameState`, `Adjacency`, `ActionLog` creation.
4. Implement field validation.
5. Implement square/hex board generation.
6. Implement adjacency table writing.
7. Add schema tests where ArcPy is available.
8. Commit.

Acceptance:

- A generated board exists in `data/arcpy_game.gdb` with all required fields.

## Milestone 3 — Python Toolbox Controller Shell

Objective:

- Expose the game through ArcGIS Pro GP pane.

Tasks:

1. Create `toolbox/arcpy_game.pyt`.
2. Define `GameController` parameters.
3. Implement `getParameterInfo`.
4. Implement lightweight `updateParameters` and `updateMessages`.
5. Implement action dispatch stubs.
6. Add `New Game` execution path.
7. Test in ArcGIS Pro.
8. Commit.

Acceptance:

- ArcGIS Pro can load the toolbox and run `New Game`.

## Milestone 4 — Stage 1 Playable Survey Sweeper

Objective:

- Complete the fallback playable game.

Tasks:

1. Implement selected-cell reading helper.
2. Implement `Reveal / Scout` for safe/hazard cells.
3. Implement win/loss checks.
4. Implement `Flag / Mark`.
5. Implement `Show Score`.
6. Add `ActionLog` writes.
7. Add refresh and messages.
8. Configure `GameBoard_Minesweeper.lyrx`.
9. Manual test in Pro.
10. Commit.

Acceptance:

- The game is playable to win/loss in a short class demo.

## Milestone 5 — Stage 1 Polish

Objective:

- Make Minesweeper feel reliable and presentable.

Tasks:

1. Add zero-neighbor flood reveal.
2. Improve validation messages.
3. Add labels for clue counts.
4. Add `docs/quickstart.md`.
5. Add a known seed for demo.
6. Run manual demo script once.
7. Commit.

Acceptance:

- Demo can be repeated with a known board and predictable reveal path.

## Milestone 6 — Containment Rule Logic

Objective:

- Add Stage 2 rules without GP geometry powers yet.

Tasks:

1. Extend `arcpy_game_rules.py` with containment state helpers.
2. Implement deterministic spread candidate selection.
3. Implement treatment/barrier modifiers.
4. Implement action points.
5. Implement scoring and win/loss.
6. Add `tests/test_containment_rules.py`.
7. Commit.

Acceptance:

- Spread and intervention logic is tested outside map UI.

## Milestone 7 — Stage 2 Playable Containment Commander

Objective:

- Make the main game playable using selected-cell actions.

Tasks:

1. Extend schema fields.
2. Add `Scenario Mode='Containment Commander'` setup.
3. Implement `Treat / Clear`.
4. Implement selected-cell `Place Barrier`.
5. Implement `Resolve Turn`.
6. Implement containment `Show Score`.
7. Configure `GameBoard_Containment.lyrx`.
8. Manual test 10-turn scenario.
9. Commit.

Acceptance:

- Player can contain or lose to a spreading threat in 5–10 turns.

## Milestone 8 — Feature Set Placement Geometry

Objective:

- Add map-drawn inputs for barriers/treatments.

Tasks:

1. Configure `GPFeatureRecordSetLayer` parameter schema.
2. Implement drawn-line or drawn-polygon barrier.
3. Implement drawn treatment zone if easy.
4. Use `memory\\...` buffers/intersections.
5. Add validation for missing placement geometry.
6. Manual test in Pro.
7. Commit.

Acceptance:

- Player can draw a geometry, run an action, and see affected cells update.

## Milestone 9 — Bufferlands Wow Powers

Objective:

- Add 2–3 named geoprocessing powers.

Tasks:

1. Implement `Buffer Defense`.
2. Implement `Erase Hotspot`.
3. Implement `Spatial Join Harvest / Score` with a tiny `Assets` layer if time allows.
4. Optionally implement `Clip Quarantine`.
5. Optionally implement `Dissolve Safe Zone`.
6. Add messages that explain GP operation + game effect.
7. Commit.

Acceptance:

- Demo visibly shows geoprocessing operations as powers, not hidden implementation details.

## Milestone 10 — Packaging and Class Demo

Objective:

- Make the project easy to run and grade.

Tasks:

1. Update `README.md` with final game description.
2. Write `docs/demo-script.md`.
3. Write `docs/quickstart.md`.
4. Include known demo seed and recommended action sequence.
5. Package `.aprx`/`.ppkx` if possible from ArcGIS Pro.
6. Do a final manual smoke test.
7. Commit.

Acceptance:

- A classmate/instructor can open the project, run the toolbox, and understand the gameplay in minutes.

---

## 10. Detailed Testing Strategy

## 10.1 Test Pyramid

### Level 1 — Pure Python Tests

Fast tests for algorithms:

- Board grid IDs.
- Adjacency generation.
- Hazard placement.
- Neighbor counts.
- Flood reveal.
- Flag/win/loss logic.
- Containment spread.
- AP costs.
- Scoring.

These should not import `arcpy` if avoidable.

### Level 2 — ArcPy Data Tests

Run only in ArcGIS Pro Python environment:

- Geodatabase creation.
- Feature class fields.
- Cursor update helpers.
- `GameState` key/value reads/writes.
- `ActionLog` insert.
- Memory workspace buffer/intersect smoke tests.

### Level 3 — ArcGIS Pro Manual Tests

Manual UI workflow:

- Toolbox loads.
- Parameter validation makes sense.
- Selection-based actions see selected cells.
- Feature Set placement can accept drawn geometry.
- Symbology/labels refresh.
- GP messages are clear.

## 10.2 Suggested Test Commands

Outside ArcGIS Pro, if tests are pure Python:

```bash
cd /workspace/projects/arcpyGame
python -m pytest tests/test_minesweeper_rules.py -v
python -m pytest tests/test_containment_rules.py -v
```

Inside ArcGIS Pro Python, if available:

```powershell
cd <project path>
<ArcGIS Pro Python> -m pytest tests/test_schema_contract.py -v
```

Use the actual ArcGIS Pro Python executable on the Windows machine when implementing; ArcPy is not expected to work inside this Docker environment.

## 10.3 Manual Smoke-Test Checklist

For every major milestone:

- Start from a clean or reset geodatabase.
- Run `New Game`.
- Confirm field schema.
- Confirm board symbology.
- Run one legal action.
- Run one illegal action and confirm useful validation/error message.
- Confirm `ActionLog` row added.
- Confirm `GameState.last_message` matches GP message.
- Confirm layer redraws; add `arcpy.RefreshLayer("GameBoard")` if not.

---

## 11. Validation and Error Handling Plan

## 11.1 Common Validation Errors

- Missing workspace.
- Workspace not writable.
- Missing `GameBoard` for non-`New Game` action.
- Missing required fields.
- No selected cells for selection-based action.
- Too many selected cells for an action that only supports one.
- Game status is `won` or `lost`.
- Action points exhausted.
- Placement geometry missing for geometry-based power.
- Radius too large or <= 0.
- Board too large for demo mode.

## 11.2 Validation Style

Use direct player-facing messages:

- Bad: “FIDSet invalid.”
- Good: “Select one or more board cells before running Reveal / Scout.”

- Bad: “State transition not allowed.”
- Good: “This game is already over. Run New Game or Reset to play again.”

## 11.3 Runtime Error Handling

In `execute`:

- Fail early for schema/status issues.
- Wrap action execution enough to log useful context, but do not swallow exceptions silently.
- Always release cursors by using `with` blocks.
- Do not leave partial schema changes during `New Game`; if creation fails, emit a clear message.
- For memory intermediates, delete existing names before reuse when needed.

---

## 12. Risks and Mitigations

## Risk: The project feels like plain Minesweeper, not GIS

Mitigations:

- Theme as Survey Sweeper / contamination survey.
- Use adjacency, buffers, and spatial clues in presentation.
- Move quickly to Containment Commander after Stage 1.
- Add at least two visible GP powers in Stage 3.

## Risk: ArcGIS GP UI feels clunky

Mitigations:

- Use one controller tool with stable parameters.
- Keep actions to 3–5 initially.
- Use map selection as the primary interaction.
- Provide clear GP messages and labels.
- Prepare a known demo seed/action script.

## Risk: Schema locks / edit sessions cause failures

Mitigations:

- Avoid schema changes during play.
- Keep cursors short-lived.
- Create fields only during `New Game`/setup.
- Use file geodatabase, not versioned/topology-heavy datasets.

## Risk: Map does not visually refresh after cursor updates

Mitigations:

- Use derived output parameter.
- Call `arcpy.RefreshLayer("GameBoard")` after updates.
- Preconfigure symbology/labels on fields that change.

## Risk: Spread randomness is hard to test/demo

Mitigations:

- Store seed in `GameState`.
- Use deterministic random per turn/source/target.
- Prefer sorted deterministic spread for MVP if needed.
- Provide a known class-demo seed.

## Risk: Bufferlands powers bloat scope

Mitigations:

- Add powers only after Stage 2 is playable.
- Limit to 2–3 powers.
- Use dropdown actions, not cards/decks.
- Powers update existing cell fields; they do not create a second game system.

## Risk: ArcPy is unavailable in the development container

Mitigations:

- Keep algorithm tests pure Python.
- Isolate ArcPy code in schema/GP modules.
- Perform final integration tests inside ArcGIS Pro Python on the target machine.

## Risk: Real data cleanup consumes project time

Mitigations:

- Use generated grid/hex board first.
- Add real parcels/tracts only as optional presentation polish.
- Use synthetic assets/susceptibility for reliable demo.

---

## 13. Demo Script for Class Presentation

## 13.1 Opening Framing — 30 Seconds

Say:

> “This project abuses ArcGIS Pro as a turn-based game engine. The feature class is the game state, the map is the renderer, selections are input, and geoprocessing tools are the player’s moves.”

Show:

- `GameBoard` layer.
- `GameState` table.
- `ActionLog` table.
- `Game Controller` tool with `Action` dropdown.

## 13.2 Stage 1 Demo — Survey Sweeper — 2 Minutes

1. Run `New Game` with `Scenario Mode = Survey Sweeper`, `Tiny Demo` or `Small`, known seed.
2. Point out hidden survey cells.
3. Select one cell.
4. Run `Reveal / Scout`.
5. Show clue count label.
6. Select a suspected cell.
7. Run `Flag / Mark`.
8. Reveal a zero-neighbor cell if known from demo seed to show flood reveal.
9. Run `Show Score`.

Narration:

> “This proves the core ArcPy loop: select features, run a GP action, update fields, redraw symbology, and log the turn.”

## 13.3 Stage 2 Demo — Containment Commander — 3 Minutes

1. Run `New Game` with `Scenario Mode = Containment Commander`.
2. Show initial threat cells, assets, and turn/action points.
3. Select a threatened cell.
4. Run `Treat / Clear`.
5. Select/draw barrier line or select barrier cells.
6. Run `Place Barrier`.
7. Run `Resolve Turn`.
8. Show threat spread blocked/reduced.
9. Run `Show Score`.
10. Repeat one turn if time allows.

Narration:

> “The same board and controller now support a different game. Adjacency is no longer a clue system; it is the spread graph.”

## 13.4 Stage 3 Demo — Bufferlands Powers — 2 Minutes

Pick two powers:

### Buffer Defense

1. Draw a point/line near threatened cells.
2. Choose `Buffer Defense`, radius e.g. `150` map units.
3. Run tool.
4. Show buffered/protected cells.

Say:

> “Buffer is not just analysis output; buffer is a defensive move.”

### Erase Hotspot or Spatial Join Harvest

Erase Hotspot:

1. Draw/select treatment zone.
2. Run `Erase Hotspot`.
3. Show cleared threat cells.

Spatial Join Harvest:

1. Run `Spatial Join Harvest / Score`.
2. Show assets saved and score message.

Say:

> “The GIS operation is the move, and the map state is the game result.”

## 13.5 Closing — 30 Seconds

Say:

> “The important design choice was not to build a separate game UI. The game lives in normal GIS objects: features, attributes, selections, symbology, and geoprocessing tools.”

---

## 14. Final MVP Acceptance Criteria

The final submission should meet these minimum criteria:

- One Python toolbox controller runs inside ArcGIS Pro.
- `New Game`, `Reveal / Scout`, `Flag / Mark`, `Treat / Clear`, `Place Barrier`, `Resolve Turn`, `Show Score`, and `Reset` are available or staged clearly.
- Stage 1 Survey Sweeper is fully playable.
- Stage 2 Containment Commander is playable for a 5–10 turn scenario.
- At least two Bufferlands-style powers work and are demo-friendly.
- State is stored in `GameBoard`, `GameState`, and `ActionLog`.
- Symbology/labels make state understandable without a custom UI.
- Boards are small and actions run quickly.
- No per-turn schema changes are required.
- Core gameplay uses only ArcGIS core vector functionality.
- Documentation includes quickstart and demo script.

---

## 15. Implementation Guardrails

When coding starts:

- Build vertical slices in order.
- Do not start with Bufferlands powers.
- Do not build a custom UI.
- Keep action handlers small.
- Keep ArcPy wrappers thin and isolated.
- Make rule logic testable outside ArcGIS where possible.
- Commit after each working milestone or small group of related tasks.
- Prefer a reliable generated board over a beautiful but messy real dataset.
- If scope gets tight, ship Stage 1 polished plus a small Stage 2 spread demo rather than half-building everything.

---

## 16. Suggested First Implementation Step When Approved

When Griffin asks to start coding, begin with:

1. Create `toolbox/arcpy_game_rules.py`.
2. Create `tests/test_minesweeper_rules.py`.
3. Implement pure Python grid adjacency, hazard placement, neighbor counts, reveal, flag, and win/loss.
4. Run tests.
5. Commit.

This keeps the first implementation slice independent of ArcGIS Pro availability and gives the toolbox something reliable to call later.
