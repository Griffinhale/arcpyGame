# GUI Validation Spike

Date: 2026-05-14

Purpose: validate whether an ArcGIS Pro geoprocessing tool can safely hand off to a short-lived Python GUI and still support the planned game mechanics for Survey Sweeper, Containment Commander, and Bufferlands-style powers.

Implemented toolbox:

- `toolbox/arcpy_game_gui_spike.pyt`
- Toolbox label: `ArcPy Game GUI Spike`
- Tool: `GUI Command Spike`

This is a validation tool, not the final game controller. It records durable command/session rows, runs safe dry-runs, and mutates only probe fields on selected board cells.

## What It Validates

### 1. GP pane -> GUI -> command table

`Open Command Dialog` opens a Tkinter modal and records the selected command to `UICommand`.

Scenario-specific GUI commands:

- Survey Sweeper: `Reveal / Scout`, `Flag / Mark`, `Show Score`
- Containment Commander: `Scout`, `Treat / Clear`, `Place Barrier`, `Resolve Turn`, `Show Score`
- Bufferlands Stretch: `Buffer Defense`, `Spatial Join Harvest / Score`, `Suppress Hotspot`, `Show Score`

### 2. Planned feature readiness

`Validate Scenario Inputs` checks the inputs required by each planned phase feature without executing final game rules.

Checks include:

- selected Game Layer cells,
- positive radius for Bufferlands buffer powers,
- Support Layer presence for spatial-join scoring,
- optional support-layer fields: `asset_value`, `critical_asset`,
- first Containment barrier limit warning when more than two cells are selected.

### 3. Live GUI-to-map update

`Live Preview Update` opens a Tkinter modal with preview buttons.

Each preview button:

- updates selected cells in `ui_preview_state`,
- calls `arcpy.RefreshLayer(...)`,
- records the result in `UICommand`.

Manual observation is required: while the modal remains open, inspect whether the map redraws immediately, only after dialog close, or not reliably.

### 4. GUI new/load session flow

`New Game / Load Game GUI` opens a Tkinter modal for session control.

It writes/updates `GameSession` rows with:

- `game_id`,
- `scenario_mode`,
- `seed`,
- `status`,
- `active`,
- `created_utc`,
- `loaded_utc`.

The spike does not reset board features. It validates durable session state and layer-reference safety before the final game controller owns board setup.

### 5. Crash and recovery behavior

Two actions intentionally fail:

- `Simulate Crash After Command Insert`
- `Simulate Crash During Apply`

Expected behavior: ArcGIS Pro reports a GP error, but the command row remains in `UICommand`.

Then run:

- `Recover Pending Commands`

It marks `created` or `applying` commands as `abandoned`, increments `attempt_count`, and records recovery metadata.

### 6. Idempotent command apply

`Apply Last Command Idempotency` applies a generated command id to selected cells in `last_command_id`, then applies the same command id again.

Expected result:

- first apply updates selected cells,
- second apply skips cells already carrying that command id,
- `UICommand.payload_json` records applied/skipped counts.

### 7. Containment dry-run

`Dry Run Containment Mechanics` validates planned selected-cell Containment features:

- `Scout`,
- `Treat / Clear`,
- `Place Barrier`,
- `Resolve Turn`,
- `Show Score`.

It records selection count, board count, and per-feature ready/blocked status.

### 8. Bufferlands dry-run

`Dry Run Bufferlands Mechanics` validates the planned Bufferlands-style geoprocessing powers.

It attempts:

- `Buffer` on selected Game Layer cells to `memory\arcpy_game_gui_spike_buffer`,
- `SelectLayerByLocation` back onto the Game Layer,
- optional `SpatialJoin` from Support Layer to Game Layer into memory.

It records:

- buffer feature count,
- affected Game Layer count,
- spatial join count,
- any errors or skipped checks.

### 9. Lock/edit-state behavior

`Test Lock / Edit State` checks:

- `arcpy.TestSchemaLock(layer)`,
- adding harmless probe field `ui_lock_probe`,
- selected-layer `UpdateCursor` behavior while Pro panes/tables may be open.

Run this with normal selection, with the attribute table open, and during any pending-edit situations worth testing.

### 10. Close/reopen persistence

`Close Reopen Persistence Check` validates whether command/session state survives project close/reopen.

Recommended use:

1. Run several spike actions.
2. Save and close ArcGIS Pro.
3. Reopen the project.
4. Run `Close Reopen Persistence Check`.
5. Confirm it finds the expected `UICommand` and `GameSession` row counts.

## Tables and Probe Fields

### `UICommand`

Durable command log. Fields include:

- `command_id`
- `created_utc`
- `scenario_mode`
- `command_name`
- `target_layer`
- `target_cell_ids`
- `selected_oid_count`
- `status`
- `attempt_count`
- `started_utc`
- `finished_utc`
- `game_id`
- `error_message`
- `payload_json`
- `message`

Status values currently used:

- `created`
- `cancelled`
- `error`
- `applying`
- `applied`
- `abandoned`

### `GameSession`

Session control table for GUI new/load validation.

Fields include:

- `game_id`
- `created_utc`
- `loaded_utc`
- `scenario_mode`
- `seed`
- `status`
- `active`
- `message`
- `payload_json`

### Probe fields on Game Layer

Created only by specific validation actions:

- `ui_preview_state`
- `last_command_id`
- `ui_lock_probe`

These are not final gameplay fields.

## Recommended Manual Smoke Sequence

Use an existing board layer from the original feasibility spike or a small polygon layer with selected features.

1. Add `toolbox/arcpy_game_gui_spike.pyt` to ArcGIS Pro.
2. Run `Ping GUI Environment`.
3. Select one or more board cells and run `Open Command Dialog`.
4. Run `Validate Scenario Inputs` for all scenario modes.
5. Run `Live Preview Update`; click preview buttons and inspect map redraw timing.
6. Run `New Game / Load Game GUI`; create a session, then load it.
7. Run both crash simulation actions; then run `Recover Pending Commands`.
8. Run `Apply Last Command Idempotency` on selected board cells.
9. Run `Dry Run Containment Mechanics`.
10. Run `Dry Run Bufferlands Mechanics` with a positive radius and, if available, an Assets/RiskSources support layer.
11. Run `Test Lock / Edit State` with the attribute table open.
12. Save, close, reopen, and run `Close Reopen Persistence Check`.
13. Run `Describe Last UI Command` after any action to inspect the newest command row.

## Interpretation

The key architecture decision is live update behavior:

- If map redraws reliably while the modal remains open, the GUI can act like a light control panel.
- If redraw only appears after dialog close, treat the GUI as a command chooser and keep the final game loop as short GP executions.
- If crashes leave durable `created` or `applying` rows recoverable, command-table recovery is viable for the final controller.
- If Bufferlands dry-runs are slow or flaky, keep Bufferlands powers as demo/stretch actions instead of core win/loss mechanics.
