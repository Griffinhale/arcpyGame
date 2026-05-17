# ArcPy / ArcGIS Pro Geoprocessing UI + Environment Constraints

Date: 2026-05-09

Research notes for **arcpyGame**: a class project that uses ArcGIS Pro + ArcPy geoprocessing tools as a strange game engine.

The key design question is: what can the Python geoprocessing UI and runtime actually support?

## Executive summary

The safest design is a **turn-based board game controlled by one Python toolbox / script tool**, not a custom game UI.

Recommended architecture:

- A small board layer: grid, parcels, tracts, hexes, or curated polygons.
- Feature classes and small tables hold all game state.
- Player input happens through:
  - selecting features on the map,
  - editing/placing points/lines/polygons,
  - choosing values in a GP tool parameter form,
  - running a `Game Controller` tool.
- One tool resolves the action, updates feature attributes/geometries, writes messages, and refreshes the layer.
- Symbology/labels render the game state.

Avoid:

- real-time animation,
- custom card UI,
- drag/drop game interfaces,
- always-running loops,
- RPG inventory systems,
- large dynamic simulations,
- per-turn Spatial Analyst / Network Analyst work unless precomputed or optional.

## 1. The GP pane is a form, not a custom game UI

ArcGIS Pro geoprocessing tools expose parameters in the Geoprocessing pane. The UI controls are determined mostly by parameter datatypes and supported parameter control options.

Important constraints:

- You cannot freely build arbitrary UI widgets inside a Python toolbox.
- The GP pane supports a limited set of controls.
- Some controls can be influenced with `controlCLSID`, but still within Esri-supported patterns.
- A game controller should be designed as a parameter form: dropdowns, checkboxes, layer inputs, value tables, feature sets, and messages.

Useful supported patterns:

- `GPString` with `ValueList` filter for an `Action` dropdown.
- `GPFeatureLayer` for board/unit/threat layers.
- `Field` parameters dependent on a layer parameter.
- `GPFeatureRecordSetLayer` / Feature Set for map-click input or drawn temporary features.
- Derived output parameters for tools that mutate an input layer in place.

Game implication:

- Think “controller form,” not “game panel.”
- Use an `Action` dropdown like:
  - `New Game`
  - `Reveal Selected`
  - `Treat Selected`
  - `Place Barrier`
  - `Resolve Turn`
  - `Show Score`

Sources:

- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/parameter-controls.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/defining-parameters-in-a-python-toolbox.htm

## 2. Dynamic parameters are possible, but structurally limited

Python toolboxes can customize parameter behavior with:

- `getParameterInfo`
- `updateParameters`
- `updateMessages`
- `execute`

You can dynamically:

- enable/disable parameters,
- change filters,
- populate value lists,
- set default values,
- raise validation errors/warnings.

But you generally cannot dynamically change structural parameter properties after definition, including:

- datatype,
- direction,
- name,
- display name,
- `multiValue`,
- dependencies,
- parameter type,
- control type.

Game implication:

- Define the whole controller shape up front.
- You can hide/disable irrelevant fields per action, but not truly add/remove UI controls dynamically.
- Keep the action set small and stable.
- Do not do heavy geoprocessing inside `updateParameters`; validation can run repeatedly while the user edits the form.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/customizing-tool-behavior-in-a-python-toolbox.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/programming-a-toolvalidator-class.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/understanding-validation-in-script-tools.htm

## 3. Feature selection is a viable input method

ArcGIS layers support selections. A GP tool can receive a `GPFeatureLayer`, and cursors/tools can operate on selected features.

`Describe(layer).FIDSet` exposes selected feature IDs:

- Classic `arcpy.Describe`: semicolon-delimited selected feature IDs.
- `arcpy.da.Describe`: list of selected feature IDs.
- If no selection exists, `FIDSet` can be `None`.
- If a selection exists but contains zero records, it can be an empty list.

Game implication:

- “Select a cell/unit/target on the map, then run the controller tool” is a good interaction pattern.
- Validate selection count:
  - zero selected = error or warning,
  - multiple selected = either multi-target action or validation error,
  - exactly one selected = normal single-target action.
- This is good for:
  - Minesweeper reveal/flag,
  - Containment treatment target,
  - Census Conquest attack/claim target,
  - Bufferlands unit/action target.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/tool-reference/data-management/an-overview-of-the-layers-and-table-views-toolset.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/functions/layer-properties.htm

## 4. Feature Set parameters can support map-click placement

`GPFeatureRecordSetLayer` / Feature Set parameters let users create features interactively as GP parameter input. The schema/symbology can be initialized from a feature class or layer file.

Game implication:

- Useful for:
  - placing a tower,
  - placing a treatment point,
  - drawing a barrier/firebreak,
  - placing a guess point,
  - drawing/selecting a route candidate.
- Still not live event handling. It is parameter editing followed by a Run action.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/defining-parameters-in-a-python-toolbox.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/parameter-controls.htm

## 5. Messages are useful turn feedback, not persistent UI

Python toolbox tools can emit messages, warnings, and errors.

Validation messages:

- `setErrorMessage`
- `setWarningMessage`
- `clearMessage`
- `hasError`
- `hasWarning`

Execution messages:

- `messages.addMessage`
- `messages.addWarningMessage`
- `messages.addErrorMessage`
- `messages.addIDMessage`
- `messages.addGPMessages`

Game implication:

- Use messages for immediate feedback:
  - “Turn 4 resolved.”
  - “Threat spread to 3 new parcels.”
  - “Invalid move: target is not adjacent.”
  - “You saved 71% of habitat.”
- Do not rely on messages as durable game state.
- Store durable state in fields/tables and show it with symbology/labels/popups.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/writing-messages-in-a-python-toolbox.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/customizing-tool-behavior-in-a-python-toolbox.htm

## 6. Symbology can be automated, but preconfigured layers are safer

Python toolbox output parameters can specify a `.lyrx` file with the `symbology` property. `SetParameterSymbology` can also assign output symbology.

But for an in-place game board, the smoother pattern is:

- preconfigure layer symbology based on state fields,
- update fields during turns,
- call refresh where necessary.

Game implication:

- Add fields like:
  - `state`
  - `threat_level`
  - `revealed`
  - `owner`
  - `protected`
  - `hp`
- Configure symbol classes once in the project/template.
- Let field updates drive the visual board.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/setting-output-symbology-in-scripts.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/defining-parameters-in-a-python-toolbox.htm

## 7. ArcPy runtime: inside Pro vs standalone

ArcGIS Pro uses Python 3 via conda environments. ArcPy must run in an ArcGIS Pro Python environment.

Relevant execution contexts:

- Inside ArcGIS Pro:
  - Python window,
  - notebooks,
  - script tools,
  - Python toolboxes.
- Outside ArcGIS Pro:
  - command prompt,
  - IDE,
  - scheduled task,
  - batch file,
  - standalone script using Pro’s Python environment.

`arcpy.mp.ArcGISProject("CURRENT")` only works inside ArcGIS Pro.

Game implication:

- The game should be a Python toolbox/script tool run inside ArcGIS Pro if it needs the current map/project.
- Standalone tests can run against file geodatabases, but map UI interactions need Pro.
- Package with a pre-authored `.aprx`, `.ppkx`, or template rather than trying to author everything from scratch at runtime.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/arcpy/get-started/installing-python-for-arcgis-pro.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/mapping/arcgisproject.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/mapping/arcgisproject-class.htm

## 8. Tool run modes affect “game loop” feel

ArcGIS Pro geoprocessing can run on either:

- **Geoprocessing Thread**: background thread; user can still interact with Pro/map.
- **Foreground Thread**: blocks interaction with the app.

But tools run from ModelBuilder, ArcGIS Notebooks, and the Python window run foreground. Some cases force foreground, including pending edits or undo support.

Game implication:

- A “live Python window loop” is a poor game controller.
- Prefer short GP tool executions from the Geoprocessing pane.
- Design each turn to finish quickly and return control to the map.
- Avoid pending edit states while resolving turns if possible.

Source:

- https://pro.arcgis.com/en/pro-app/latest/help/analysis/geoprocessing/basics/tool-run-modes.htm

## 9. Refreshing map layers is possible, but not a render loop

`arcpy.RefreshLayer(layer_name)` refreshes map views containing specified layers. It is useful when updates through cursors/table changes do not automatically redraw.

Game implication:

- After cursor updates, call `arcpy.RefreshLayer("GameBoard")` or relevant layer names.
- Expect coarse turn-based visual updates, not animation.
- This supports “Run Turn → map updates,” not 60fps or continuous movement.

Source:

- https://pro.arcgis.com/en/pro-app/latest/arcpy/functions/refreshlayer.htm

## 10. Edit sessions, schema locks, and cursors matter

`arcpy.da.Editor` manages edit sessions and edit operations. Some datasets require edit sessions, especially topology/network/versioned/class-extension datasets.

Important constraints:

- Schema-changing tools require schema locks.
- Update/insert cursors acquire exclusive locks.
- Cursors should be short-lived.
- Reusing cursors across edit operations can cause unexpected behavior.
- Use `with arcpy.da.UpdateCursor(...)` blocks and release locks promptly.
- Use `arcpy.TestSchemaLock(dataset)` before schema-altering operations.

Game implication:

- Do not add/drop fields during normal turns.
- Create/validate schema during `New Game` / `Initialize` only.
- During play, update existing attributes/geometries only.
- Keep cursor operations short and deterministic.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/arcpy/data-access/editor.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/functions/testschemalock.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/get-started/data-access-using-cursors.htm

## 11. Memory workspace is good for temporary turn outputs

ArcGIS Pro supports memory workspaces:

- `memory\...`: current recommended memory workspace.
- `in_memory\...`: older legacy workspace.

Benefits:

- Faster intermediate outputs than disk.
- Good for per-turn buffers/intersects/selections on small datasets.

Limitations:

- Large memory datasets can exhaust RAM.
- No feature datasets, relationship classes, attribute rules, topologies, utility networks, trace networks, or network datasets.
- Limited schema modification support.
- Some tools do not support memory inputs/outputs.

Game implication:

- Use `memory\turn_buffer`, `memory\spread_candidates`, etc. for intermediate overlays.
- Delete/overwrite intermediates each turn.
- Persist only the board state and logs.
- Do not use memory workspace for Network Analyst datasets or topology-heavy structures.

Source:

- https://pro.arcgis.com/en/pro-app/latest/help/analysis/geoprocessing/basics/the-in-memory-workspace.htm

## 12. Logging/history can create noise in repeated gameplay

ArcGIS Pro records geoprocessing history. Scripts can also write geoprocessing history/log XML by default.

Relevant controls:

- `arcpy.SetLogHistory(False)`
- `arcpy.SetLogMetadata(False)`

Game implication:

- Repeated turns can spam project history/logs.
- For a game loop, consider disabling log history during normal play while keeping custom `ActionLog` table entries.
- During debugging, leave logs on.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/help/analysis/geoprocessing/basics/geoprocessing-history.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/functions/setloghistory.htm

## 13. Licensing constraints affect idea selection

Spatial Analyst:

- Many raster tools require Spatial Analyst or sometimes Image Analyst.
- Hydrology, cost distance, density, zonal, raster overlay, and other advanced raster tools are extension-gated.

Network Analyst:

- Creating/building/solving network datasets generally requires Network Analyst for local network datasets.
- Solving against services may behave differently.

Extension handling:

- Use `arcpy.CheckOutExtension("Spatial")` and `arcpy.CheckOutExtension("Network")` when appropriate.
- `CheckOutExtension` matters mainly for Concurrent Use licensing.
- Use `CheckInExtension` after use.

Game implication by concept:

- **Map Minesweeper:** safest; no extensions needed.
- **Containment Commander:** safe if vector adjacency/buffers; risky if raster spread/cost surfaces every turn.
- **Census Conquest:** safe; mostly vector and attributes.
- **Bufferlands:** safe if buffer/intersect on small datasets; avoid real-time pathing.
- **Urban Planner Puzzle:** safe if vector overlays/buffers; optional raster suitability can be precomputed.
- **RescueOps:** risky if true Network Analyst routing is required; safer with precomputed candidate routes.
- **Watershed Dungeon:** risky if live hydrology/raster tools are required; safer with precomputed watershed/stream graph.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/spatial-analyst-toolbox-license.htm
- https://pro.arcgis.com/en/pro-app/latest/tool-reference/network-analyst/network-analyst-toolbox-license.htm
- https://pro.arcgis.com/en/pro-app/latest/arcpy/functions/checkoutextension.htm

## 14. Performance constraints favor tiny boards and precomputation

Repeated per-turn geoprocessing has overhead. Raster/hydrology/cost/network operations can be expensive.

Spatial Analyst notes:

- Many Spatial Analyst tools support parallel processing.
- Some tools use about 50% of cores by default.
- Parallelism often helps large rasters, but smaller rasters can lose time to overhead.

Game implication:

- Keep MVP board small: 20–75 features.
- Precompute:
  - adjacency table,
  - route candidates,
  - static suitability scores,
  - downstream/upstream graph,
  - neighborhood lists,
  - hazard bias fields.
- Use attributes and cursors for core rules when possible.
- Use geoprocessing visibly but not wastefully; the game should not require heavy overlay pipelines every click.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/parallel-processing-with-spatial-analyst.htm
- https://pro.arcgis.com/en/pro-app/latest/tool-reference/environment-settings/parallel-processing-factor.htm

## 15. Packaging / distribution constraints

Python toolboxes are `.pyt` files and can be used like other geoprocessing toolboxes.

Project packages can include:

- maps,
- data,
- toolboxes,
- layouts,
- geoprocessing history,
- styles,
- connections where appropriate.

Game implication:

- Package the class project as a `.ppkx` or `.aptx` with:
  - preconfigured map,
  - board/data geodatabase,
  - toolbox,
  - symbology layers,
  - documentation,
  - sample scenario.
- Avoid requiring the grader/user to manually build data, fields, symbology, or Python environments.

Sources:

- https://pro.arcgis.com/en/pro-app/latest/arcpy/geoprocessing_and_python/a-quick-tour-of-python-toolboxes.htm
- https://pro.arcgis.com/en/pro-app/latest/help/sharing/overview/project-package.htm
- https://pro.arcgis.com/en/pro-app/latest/tool-reference/data-management/package-project.htm

## Recommended controller-tool shape

Suggested Python toolbox parameters:

- `Game Layer` — `GPFeatureLayer`, required.
- `Action` — `GPString` with `ValueList`:
  - `New Game`
  - `Reveal / Scout`
  - `Treat / Clear`
  - `Place Barrier`
  - `Resolve Turn`
  - `Show Score`
  - `Reset`
- `Target Layer` — optional `GPFeatureLayer` if actions target a separate layer.
- `Placement Feature` — optional `GPFeatureRecordSetLayer` for draw/place interactions.
- `Intensity / Amount` — optional numeric value.
- State field parameters, optional or hidden after schema standardization:
  - `owner_field`
  - `state_field`
  - `threat_field`
  - `revealed_field`
  - `turn_field`
- Derived output layer depending on the game layer.

Validation responsibilities:

- Enable/disable action-specific parameters.
- Enforce selected-feature count.
- Ensure required schema exists.
- Check current turn/player/state.
- Warn if an action is legal but bad.
- Error if action is impossible.

Execution responsibilities:

- Disable noisy logs if desired.
- Read current game state.
- Apply action deterministically.
- Use `memory\...` for turn intermediates.
- Update fields/geometries.
- Write an `ActionLog` row.
- Add GP messages summarizing the turn.
- Set derived output.
- Refresh relevant layer(s).

## Design implications for current shortlisted concepts

### Map Minesweeper / Survey Sweeper

Best fit for GP constraints.

Why:

- Selection input works naturally.
- State is simple fields: `hidden`, `revealed`, `flagged`, `hazard`, `neighbor_count`.
- No licensing risk.
- Most logic can be attributes + adjacency.

Recommended first prototype.

### Containment Commander

Strong fit if vector-based.

Why:

- Turn resolution is natural.
- Buffers/intersects are visible and meaningful.
- Limited actions and spread ticks map well to GP execution.

Constraint:

- Use adjacency and small buffers, not raster cost distance every turn.
- Precompute susceptibility and neighbors.

Recommended main game.

### Bufferlands: Spatial Tactics

High upside, UI risk.

Why:

- GP actions as powers are a great conceptual match.

Constraint:

- Do not implement custom card UI.
- Use an action table or dropdown.
- Keep action count tiny.

Recommended as polish/wow layer after core loop.

### Census / District Conquest

Solid fit.

Why:

- Mostly vector attributes, joins, adjacency, dissolve.
- Strong class relevance.

Constraint:

- Needs tension and opponent/events to feel game-like.
- Avoid political/data-cleaning complexity unless using synthetic or curated census-like data.

### RescueOps / Evacuation

Conditional fit.

Constraint:

- True routing is risky without Network Analyst.
- Use precomputed candidate routes or simple graph fields.

### Watershed Dungeon

Stretch fit.

Constraint:

- Hydrology/raster processing is extension-gated and can be heavy.
- Use precomputed vector basin/stream graph if attempted.

## Bottom line

The research reinforces the Delphi shortlist:

1. **Prototype Map Minesweeper** to prove the GP UI/game-state loop.
2. **Build Containment Commander** as the main game.
3. **Add Bufferlands-style geoprocessing powers** for wow factor.
4. Keep **Census Conquest** as the safe classroom/pedagogy alternate.
5. Treat **RescueOps** and **Watershed Dungeon** as stretch concepts unless dependencies are solved.

The viable design is not a custom ArcGIS game UI. It is a clever abuse of standard geoprocessing forms, selections, feature layers, fields, tables, symbology, and turn-based map updates.
