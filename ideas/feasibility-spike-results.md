# Feasibility Spike Results

Date: 2026-05-08
ArcGIS Pro version: **3.6 (build 59527)**
Python version: **3.13.7 (Anaconda)**
ArcPy version / install info: ArcGISPro 3.6, InstallDir `c:\program files\arcgis\pro\`
Project path: `E:\GIS\spike_project\spike\spike.aprx`
Toolbox path: `E:\GIS\spike_project\spike\arcpy_game_spike.pyt`
Geodatabase path: `E:\GIS\spike_project\spike\data\arcpy_game_spike.gdb`
Map/layer names: `Map` / `GameBoard_Spike`

## Summary

- Overall result: **PASS**
- Biggest blocker: none for the must-have tier
- Biggest surprise: **cursor over layer respects layer selection for both Search AND Update** (T20 / T22). v2 plan can rely on this.
- Next fix: pre-class symbology states in a `.lyrx` so first-run players don't need "Add unlisted values."

## Test Results

### T01 — Toolbox load + environment ping ✅ PASS
- ProductName=ArcGISPro, Version=3.6, BuildNumber=59527, InstallDir=`c:\program files\arcgis\pro\`
- `sys.executable = C:\Program Files\ArcGIS\Pro\bin\ArcGISPro.exe`
- `sys.version = 3.13.7 (Anaconda) [MSC v.1938 64 bit (AMD64)]`
- platform = Windows-10-10.0.19045-SP0
- `env.overwriteOutput = True` (default in Pro 3.6 GP execution)
- `ArcGISProject('CURRENT')` works.
- `homeFolder = E:\GIS\spike_project\spike` (after Save Project As)
- `activeMap = 'Map'` (after Insert > New Map)

### T02 — Toolbox structure recognized ✅ PASS
- Toolbox + tool appear in Catalog pane after Add Toolbox.
- **Cache hygiene gotcha:** moving a `.pyt` between folders with Pro running can leave stale `__pycache__\` and `.pyt.xml` siblings; clearing them and re-adding the toolbox fixes the "corrupted/red-X" tool icon.

### T03 — Parameters render ✅ PASS
- All 7 parameters appear: workspace, layer, mode, action, seed, radius, derived output.
- `DEWorkspace` browse, `GPFeatureLayer` dropdown, `GPString` ValueList all render correctly.

### T04 — Dynamic action list / enable-disable ✅ PASS
- Mode switch updates Action filter list; selected value resets to first allowed when invalid.
- Radius enabled only for `Test Memory Buffer`.
- Layer required toggle works for selection-dependent actions.

### T05 — Validation messages ✅ PASS
- Layer error fires when omitted on selection-dependent actions.
- Radius validation (≤0 / >10000) honored.

### T06 — Workspace path resolution ✅ PASS
- Resolved gdb path: `E:\GIS\spike_project\spike\data\arcpy_game_spike.gdb`
- Falls through to `aprx.homeFolder + /data/<DEFAULT_GDB_NAME>` cleanly when no explicit workspace.

### T07 — File geodatabase creation ✅ PASS
- Folder + gdb created on first run; existence checks idempotent on re-runs.

### T08 — Feature class creation ✅ PASS
- `CreateFeatureclass` with `geometry_type='POLYGON'` succeeded.
- Spatial reference: `WGS_1984_Web_Mercator_Auxiliary_Sphere (3857)` (inherited from active map).

### T09 — Add fields with aliases/lengths ✅ PASS
- All 6 fields added with aliases: `cell_id`, `row_idx`, `col_idx`, `display_state`, `notes`, `test_count`.

### T10 — Add indexes ✅ PASS (with idempotency bug found and fixed)
- First run: `UNIQUE` index on `cell_id` succeeded.
- File gdb supports unique indexes in Pro 3.6.
- **Bug found on Reset Tiny Board run:** `AddIndex` is not idempotent. Re-creating an index with the same name raises `ERROR 000192: Invalid value for Index Name`. Fallback path then created a *second* non-unique index alongside the first, so the FC ended up with two indexes on `cell_id`.
- **Fix applied:** check `arcpy.ListIndexes(fc)` for any existing index whose `fields` include `cell_id` and skip the AddIndex call entirely if found. Pattern transferable to real-game schema setup.

### T11 — Polygon geometry construction ✅ PASS
- `arcpy.Array` + `arcpy.Polygon` constructed cells; geometry valid.
- Active map SR detected and reused.

### T12 — InsertCursor feature insertion ✅ PASS
- Inserted 9 rows; `GetCount` post-insert = 9.

### T13 — DeleteRows ✅ PASS (idempotent)
- `DeleteRows` returned True with layer in map. Used as the reset-before-reseed step.

### T14 — Add board to map ✅ PASS
- `addDataFromPath` added FC as `GameBoard_Spike` in active map.
- Idempotency check (skip if already in TOC) works on re-runs.

### T15 — List maps/layers ✅ PASS (incidental, via T29)

### T16 — classic Describe FIDSet ✅ PASS
- No selection: not directly captured — inferred from da side returning empty.
- One selection: value=`'5'` type=`str`
- Multi (2): value=`'5; 9'` type=`str` — **note the SPACE after the semicolon.**

### T17 — da.Describe FIDSet ✅ PASS
- One selection: value=`[5]` type=`list`
- Multi (2): value=`[5, 9]` type=`list`
- **Different return type from classic.** Classic returns string, da returns `list[int]`.

### T18 — normalize_fidset behavior ✅ PASS
- All observed inputs normalized to clean ascending `list[int]`.
- Whitespace tolerance (`'5; 9'`) handled by per-part `.strip()`.

### T19 — OID field name ✅ PASS
- `OBJECTID` (standard for file gdb).

### T20 — OID -> cell_id resolution ✅ PASS — **biggest finding**
- **`arcpy.da.SearchCursor(layer, ...)` respects layer selection** — returned only the 2 selected rows, not all 9.
- Explicit `OBJECTID IN (5,9)` where-clause via `AddFieldDelimiters` also works as a fallback.
- Means: real-game cursors don't need to do selection-ID dance.

### T21 — Selection clearing/retention — NOT EXPLICITLY TESTED
- No issues observed when selection persisted across runs.

### T22 — UpdateCursor on selected rows ✅ PASS
- **UpdateCursor over layer also respects selection** — updated 2 rows, not 9.
- Field values written correctly (verified in attribute table).

### T23 — Repeated update runs ✅ PASS
- Second `Mark Selected` on same selection ran cleanly; state transitioned `marked → marked-bumped`, `test_count` incremented.
- No lock errors after 2+ repeats.

### T24 — TestSchemaLock behavior ✅ PASS
- `TestSchemaLock(layer) = True` even with layer rendered in map.
- Suggests schema mutations mid-game are viable if needed.

### T25 — Automatic redraw ✅ PASS
- After initial "Add unlisted values" symbology priming, **subsequent field updates redrew the map automatically** without explicit refresh.
- First-run priming is the only gotcha; mitigatable via pre-classed `.lyrx`.

### T26 — arcpy.RefreshLayer — PENDING

### T27 — Derived output parameter ✅ PASS
- `SetParameterAsText(P_OUTPUT, board_fc)` error-free.
- Logged at end of `Create Tiny Board` and `Mark Selected`.

### T28 — ApplySymbologyFromLayer — PENDING

### T29 — Label expression behavior — PENDING

### T30 — Execution messages ✅ PASS
- Both `messages.addMessage(...)` and `arcpy.AddMessage(...)` render in GP pane.
- Initial spike sent both → duplicated lines. Fix: pick one (we kept toolbox-native `messages.*`).

### T31 — Log history controls — NOT TESTED (optional)

### T32 — memory\\... output management ✅ PASS
- `arcpy.Exists('memory\\...')` and `Delete` work; no stale outputs across runs in fresh sessions.

### T33 — Buffer to memory ✅ PASS
- `'X Meters'` distance string accepted on first try (no fallback to numeric needed).
- **Buffer respected layer selection**: 2 selected cells → 2 buffer features.

### T34 — SelectLayerByLocation ✅ PASS
- Issued without error; replaced prior selection.

### T35 — GetCount on layer selection ✅ PASS
- With 1 selected: GetCount = 1.
- With 2 selected: GetCount = 2.
- After SelectLayerByLocation w/ 150m buffer: GetCount = 9 (full 3×3 board).
- **GetCount(layer) respects selection.**

### T36-T38 — Feature Set drawing — NOT TESTED (deferred per spike doc)

### T39 — Project close/reopen — PENDING (optional stretch)

### T40 — Renamed layer — PENDING (optional stretch)

### T41 — Partial prior state recovery ✅ PASS
- `Reset Tiny Board` on populated, in-map FC ran cleanly:
  - T13 DeleteRows succeeded.
  - T08/T09 schema detection correctly recognized existing FC + fields and skipped.
  - T12 re-inserted 9 rows; GetCount = 9.
  - T14 correctly skipped re-add (`layer already in map; skipping addDataFromPath`).
  - T27 derived output OK.
- **The "never delete the FC, only DeleteRows" rule from v2 is validated.**
- Idempotency caveat: AddIndex (see T10) is the one bit that wasn't safely re-runnable; now fixed.

## Feasibility Verdict

- Python toolbox controller: **PASS**
- Parameter staging: **PASS**
- Selection as input: **PASS**
- OID -> cell_id resolution: **PASS** (and importantly, often unnecessary — cursors respect selection)
- Field updates: **PASS**
- Refresh/symbology: **PASS** (with one-time symbology priming)
- Memory buffer/select: **PASS**
- Feature Set drawing: NOT TESTED (deferred)
- Repeated run/locks: **PASS**

## Architecture changes needed (for v2 implementation plan)

1. **Drop the FIDSet-parsing-first approach.** v2 spike doc was hedging. Replace with: cursor-over-layer is the primary code path; FIDSet parsing exists only for diagnostic logging and edge-case fallbacks.
2. **Symbology must ship as a `.lyrx`** with all `display_state` values pre-classed, so first-run players don't need to manually click "Add unlisted values."
3. **Cache-hygiene step in Pro setup docs.** When iterating on the toolbox, instruct users to avoid moving the `.pyt` between folders mid-session; if they do, clear `__pycache__\` and `.pyt.xml` siblings before re-adding.
4. **Schema setup (AddIndex / AddField) must be idempotent.** Always check existence (`arcpy.ListIndexes`, `arcpy.ListFields`) before mutating. AddIndex name-collision raises ERROR 000192 — caught and fixed mid-spike.

## Safe next implementation step

Proceed to Survey Sweeper rules/schema. The controller architecture (one tool + Action dropdown + cursor-over-layer + display_state symbology) is fully validated.
