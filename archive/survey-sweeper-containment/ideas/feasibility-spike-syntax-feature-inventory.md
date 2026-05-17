# ArcGIS Pro Feasibility Spike — Syntax and Feature Inventory

Date: 2026-05-09

Purpose:

- Inventory exactly what Griffin should check in ArcGIS Pro before implementing the full ArcPy game.
- Record which Python toolbox syntax, parameter behaviors, selection behaviors, cursor updates, refresh behaviors, memory workspace operations, and symbology hooks actually work in the target ArcGIS Pro environment.

Related plan:

- `ideas/minesweeper-to-containment-implementation-plan-v2.md`

Recommended output after tonight’s run:

- Create `ideas/feasibility-spike-results.md` with pass/fail notes, screenshots if useful, and exact observed values/errors.

---

## 1. Spike Goal

The spike should answer one question:

> Can ArcGIS Pro act as the game controller loop: choose an action in a Python toolbox, read selected map features, map selection IDs to stable `cell_id`s, update feature fields, redraw symbology, and report useful GP messages?

Minimum pass condition:

1. A `.pyt` toolbox loads in ArcGIS Pro.
2. A tiny `GameBoard` layer exists.
3. A cell can be selected on the map.
4. The tool can read the selection.
5. The tool can resolve selection OID/FID to `cell_id`.
6. The tool can update an attribute field such as `display_state` or `notes`.
7. The map visibly updates or can be forced to update.
8. GP messages show enough details to debug.

---

## 2. Suggested Spike Tool Actions

The spike toolbox can be temporary. Suggested actions:

- `Ping Environment`
- `Create Tiny Board`
- `Describe Parameters`
- `Describe Selection`
- `Mark Selected`
- `Test Refresh`
- `Test Memory Buffer`
- `Test Symbology Hook`
- `Reset Tiny Board`

You do not need all actions for a first pass. The must-have sequence is:

1. `Ping Environment`
2. `Create Tiny Board`
3. Select a board cell manually.
4. `Describe Selection`
5. `Mark Selected`
6. `Test Refresh`

---

## 3. Run Log Template

Copy this into `ideas/feasibility-spike-results.md` after the ArcGIS Pro run.

```markdown
# Feasibility Spike Results

Date:
ArcGIS Pro version:
Python version:
ArcPy version / install info:
Project path:
Toolbox path:
Geodatabase path:
Map/layer names:

## Summary

- Overall result: PASS / PARTIAL / FAIL
- Biggest blocker:
- Biggest surprise:
- Next fix:

## Test Results

### T01 — Toolbox load

- Result:
- Notes:
- Error text:

### T02 — Parameters render

- Result:
- Notes:

### T03 — Create tiny board

- Result:
- Row count:
- Field list:
- Notes:

### T04 — Select cell and read FIDSet

- Result:
- classic Describe FIDSet value/type:
- da Describe FIDSet value/type:
- Notes:

### T05 — Resolve OID to cell_id

- Result:
- OID field name:
- Selected OIDs:
- Resolved cell_ids:

### T06 — Update selected row

- Result:
- Field updated:
- Before:
- After:

### T07 — Refresh / visual update

- Result:
- Did map update automatically:
- Did RefreshLayer help:
- Did derived output help:

### T08 — Symbology

- Result:
- Method tested:
- Notes:

### T09 — Memory workspace buffer

- Result:
- Output path:
- Feature count:
- Notes:

### T10 — Repeated runs / locks

- Result:
- Number of repeated runs:
- Any locks/errors:

## Screenshots / Evidence

- Optional screenshot paths or notes.

## Required plan changes

- Change 1:
- Change 2:
```

---

## 4. Environment and Version Checks

## T01 — ArcGIS / Python environment identity

### What to check

Inside tool execution, log:

- ArcGIS Pro install/version if available.
- Python executable.
- Python version.
- ArcPy import success.
- Current workspace.
- Scratch workspace.
- Whether running inside ArcGIS Pro.
- Whether `arcpy.mp.ArcGISProject('CURRENT')` works.

### Syntax/features to test

```python
import sys
import platform
import arcpy

sys.executable
sys.version
platform.platform()
arcpy.GetInstallInfo()
arcpy.env.workspace
arcpy.env.scratchWorkspace
arcpy.env.overwriteOutput

try:
    aprx = arcpy.mp.ArcGISProject('CURRENT')
    current_project_ok = True
except Exception as exc:
    current_project_ok = False
```

### Record

- `sys.executable`
- ArcGIS product/version
- whether `CURRENT` works
- whether project path can be read

### Pass condition

- `import arcpy` works.
- Tool can print environment info via GP messages.
- `ArcGISProject('CURRENT')` works when run inside Pro.

---

## 5. Python Toolbox Syntax Checks

## T02 — Minimal `.pyt` structure loads

### What to check

ArcGIS Pro recognizes the toolbox and tool class.

### Syntax/features to test

```python
class Toolbox(object):
    def __init__(self):
        self.label = 'ArcPy Game Spike'
        self.alias = 'arcpy_game_spike'
        self.tools = [GameControllerSpike]

class GameControllerSpike(object):
    def __init__(self):
        self.label = 'Game Controller Spike'
        self.description = 'Feasibility spike for ArcPy game controller.'
        self.canRunInBackground = False

    def getParameterInfo(self):
        return []

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        messages.addMessage('Spike executed.')
```

### Record

- Does toolbox appear?
- Does tool appear?
- Does description render?
- Any syntax/import errors?

### Pass condition

- Toolbox loads without traceback.
- Tool can be opened and run.

## T03 — Parameter object creation

### What to check

Parameter datatypes/directions work as expected.

### Syntax/features to test

```python
p_workspace = arcpy.Parameter(
    displayName='Game Workspace',
    name='game_workspace',
    datatype='DEWorkspace',
    parameterType='Optional',
    direction='Input'
)

p_layer = arcpy.Parameter(
    displayName='Game Layer',
    name='game_layer',
    datatype='GPFeatureLayer',
    parameterType='Optional',
    direction='Input'
)

p_mode = arcpy.Parameter(
    displayName='Scenario Mode',
    name='scenario_mode',
    datatype='GPString',
    parameterType='Optional',
    direction='Input'
)
p_mode.filter.type = 'ValueList'
p_mode.filter.list = ['Survey Sweeper', 'Containment Commander']
p_mode.value = 'Survey Sweeper'

p_action = arcpy.Parameter(
    displayName='Action',
    name='action',
    datatype='GPString',
    parameterType='Required',
    direction='Input'
)
p_action.filter.type = 'ValueList'
p_action.filter.list = ['Ping Environment', 'Create Tiny Board', 'Describe Selection', 'Mark Selected']
p_action.value = 'Ping Environment'

p_seed = arcpy.Parameter(
    displayName='Random Seed',
    name='random_seed',
    datatype='GPLong',
    parameterType='Optional',
    direction='Input'
)
p_seed.value = 2026

p_radius = arcpy.Parameter(
    displayName='Amount / Radius',
    name='amount_radius',
    datatype='GPDouble',
    parameterType='Optional',
    direction='Input'
)
p_radius.value = 100.0

p_output = arcpy.Parameter(
    displayName='Output Game Layer',
    name='output_game_layer',
    datatype='GPFeatureLayer',
    parameterType='Derived',
    direction='Output'
)
```

### Record

- Which datatypes work?
- Are default values displayed?
- Does `DEWorkspace` browse correctly?
- Does `GPFeatureLayer` dropdown see map layers?
- Does derived output parameter cause errors?

### Pass condition

- Parameters render without errors.
- `GPFeatureLayer` can accept/select the board layer.
- `GPString` ValueList displays correctly.

## T04 — Dynamic action list / parameter enable-disable

### What to check

Can `updateParameters` change action list based on `Scenario Mode` and enable/disable optional params?

### Syntax/features to test

```python
mode = parameters[2].valueAsText
if mode == 'Survey Sweeper':
    parameters[3].filter.list = [
        'Ping Environment',
        'Create Tiny Board',
        'Describe Selection',
        'Mark Selected',
        'Reset Tiny Board'
    ]
elif mode == 'Containment Commander':
    parameters[3].filter.list = [
        'Ping Environment',
        'Describe Selection',
        'Mark Selected',
        'Test Memory Buffer'
    ]

# Enable radius only for buffer action.
action = parameters[3].valueAsText
parameters[6].enabled = action in ('Test Memory Buffer', 'Buffer Defense')
```

### Record

- Does filter list update live?
- Does the current selected action get cleared if no longer valid?
- Does `enabled=False` gray out the parameter?
- Are there annoying validation loops?

### Pass condition

- We can stage the action dropdown or at least keep it manually small.
- Optional parameters can be disabled for irrelevant actions.

## T05 — Validation messages

### What to check

Can `updateMessages` produce clean errors/warnings without heavy work?

### Syntax/features to test

```python
if action in ('Describe Selection', 'Mark Selected') and not parameters[1].value:
    parameters[1].setErrorMessage('Choose a GameBoard feature layer for this action.')
else:
    parameters[1].clearMessage()

if action == 'Test Memory Buffer' and parameters[6].value is not None:
    radius = float(parameters[6].value)
    if radius <= 0:
        parameters[6].setErrorMessage('Radius must be greater than 0.')
    elif radius > 10000:
        parameters[6].setWarningMessage('Large radius may affect too many cells.')
```

### Record

- Do messages appear in the pane?
- Are errors blocking Run as expected?
- Do warnings allow Run?

### Pass condition

- Can provide player-facing validation errors like “Select one or more board cells.”

---

## 6. Workspace / Geodatabase / Feature Class Checks

## T06 — Workspace path behavior

### What to check

How paths resolve from inside a `.pyt` in Pro.

### Syntax/features to test

```python
workspace_text = parameters[0].valueAsText
if workspace_text:
    workspace = workspace_text
else:
    # fallback: project home folder if CURRENT works
    aprx = arcpy.mp.ArcGISProject('CURRENT')
    home = aprx.homeFolder
    workspace = os.path.join(home, 'data', 'arcpy_game.gdb')
```

### Record

- What is `aprx.homeFolder`?
- Can relative paths work?
- Does the project have a home folder?
- Is workspace writable?

### Pass condition

- Tool can determine a usable file geodatabase path.

## T07 — File geodatabase creation

### What to check

Can the tool create `data/arcpy_game.gdb` or a spike gdb?

### Syntax/features to test

```python
folder = os.path.dirname(gdb_path)
gdb_name = os.path.basename(gdb_path)

if not os.path.isdir(folder):
    os.makedirs(folder)

if not arcpy.Exists(gdb_path):
    arcpy.management.CreateFileGDB(folder, gdb_name)
```

### Record

- GDB path.
- Create success/failure.
- Any permissions/path issues.

### Pass condition

- File geodatabase can be created or existing one reused.

## T08 — Feature class creation

### What to check

Can a polygon feature class be created with required fields?

### Syntax/features to test

```python
board_fc = os.path.join(gdb_path, 'GameBoard_Spike')
spatial_ref = arcpy.SpatialReference(3857)  # or project/map SR if available

if not arcpy.Exists(board_fc):
    arcpy.management.CreateFeatureclass(
        out_path=gdb_path,
        out_name='GameBoard_Spike',
        geometry_type='POLYGON',
        spatial_reference=spatial_ref
    )
```

### Record

- Spatial reference used.
- Feature class path.
- Whether geometry type is correct.

### Pass condition

- Polygon feature class exists in gdb.

## T09 — Add fields with lengths and aliases

### What to check

Field creation syntax and alias behavior.

### Syntax/features to test

```python
fields = [f.name for f in arcpy.ListFields(board_fc)]

def add_field_if_missing(name, field_type, alias=None, length=None):
    existing = [f.name.lower() for f in arcpy.ListFields(board_fc)]
    if name.lower() in existing:
        return
    kwargs = {}
    if alias:
        kwargs['field_alias'] = alias
    if length and field_type.upper() == 'TEXT':
        kwargs['field_length'] = length
    arcpy.management.AddField(board_fc, name, field_type, **kwargs)

add_field_if_missing('cell_id', 'TEXT', 'Cell ID', 32)
add_field_if_missing('row_idx', 'LONG', 'Row Index')
add_field_if_missing('col_idx', 'LONG', 'Column Index')
add_field_if_missing('display_state', 'TEXT', 'Map Display State', 32)
add_field_if_missing('notes', 'TEXT', 'Notes', 255)
add_field_if_missing('test_count', 'LONG', 'Test Count')
```

### Record

- Are aliases visible in Pro table?
- Are text lengths correct?
- Any reserved word issues?

### Pass condition

- Required fields can be created and viewed.

## T10 — Add indexes

### What to check

Index creation syntax and duplicate-index behavior.

### Syntax/features to test

```python
try:
    arcpy.management.AddIndex(board_fc, 'cell_id', 'idx_gameboard_cell_id', unique='UNIQUE')
except Exception as exc:
    # Record if unique indexes not supported / duplicate exists / syntax differs.
    pass
```

Also test non-unique if unique fails:

```python
arcpy.management.AddIndex(board_fc, 'display_state', 'idx_gameboard_display_state')
```

### Record

- Does `unique='UNIQUE'` work in this environment?
- What error occurs if index exists?
- Does Pro list indexes?

### Pass condition

- At least non-unique index creation works.
- Duplicate index failure is harmless/detectable.

---

## 7. Geometry / Board Creation Checks

## T11 — Polygon geometry construction

### What to check

Can tool create square cells directly with `arcpy.Array` / `arcpy.Polygon`?

### Syntax/features to test

```python
def square_polygon(x0, y0, size, spatial_ref):
    arr = arcpy.Array([
        arcpy.Point(x0, y0),
        arcpy.Point(x0 + size, y0),
        arcpy.Point(x0 + size, y0 + size),
        arcpy.Point(x0, y0 + size),
        arcpy.Point(x0, y0),
    ])
    return arcpy.Polygon(arr, spatial_ref)
```

### Record

- Does geometry insert correctly?
- Are polygons valid/visible?
- Is coordinate system sane in map?

### Pass condition

- Tiny board polygons appear on map.

## T12 — InsertCursor feature insertion

### What to check

Can rows be inserted with geometry + fields?

### Syntax/features to test

```python
fields = ['SHAPE@', 'cell_id', 'row_idx', 'col_idx', 'display_state', 'notes', 'test_count']
with arcpy.da.InsertCursor(board_fc, fields) as cur:
    for r in range(3):
        for c in range(3):
            cell_id = f'R{r}C{c}'
            geom = square_polygon(c * 100, r * 100, 100, spatial_ref)
            cur.insertRow([geom, cell_id, r, c, 'hidden', 'created by spike', 0])
```

### Record

- Row count after insert.
- Any geometry/token issues.
- Field order issues.

### Pass condition

- 9 rows inserted.

## T13 — DeleteRows vs TruncateTable

### What to check

Which row-clearing method works when layer/table is in map.

### Syntax/features to test

```python
# Conservative reset:
arcpy.management.DeleteRows(board_fc)

# Optional check:
arcpy.management.TruncateTable(board_fc)
```

### Record

- Does `DeleteRows` work while layer is in map?
- Does `TruncateTable` fail due locks?
- Which is safer?

### Pass condition

- At least one row-clearing method works reliably.

---

## 8. Layer / Map Integration Checks

## T14 — Add created board to map

### What to check

Can tool add feature class to current map, or should the user add manually?

### Syntax/features to test

```python
aprx = arcpy.mp.ArcGISProject('CURRENT')
active_map = aprx.activeMap
layer_obj = active_map.addDataFromPath(board_fc)
```

### Record

- Does `activeMap` exist?
- Does `addDataFromPath` add the board?
- What layer name appears?
- Does repeated add create duplicate layers?

### Pass condition

- Board can be displayed in current map.

## T15 — List maps/layers and find GameBoard

### What to check

How to locate layer by name and path.

### Syntax/features to test

```python
aprx = arcpy.mp.ArcGISProject('CURRENT')
for m in aprx.listMaps():
    for lyr in m.listLayers():
        if lyr.supports('DATASOURCE'):
            ds = lyr.dataSource
        else:
            ds = None
```

### Record

- Layer name.
- Data source.
- Does `supports('DATASOURCE')` work?
- Does renamed layer still point to same data?

### Pass condition

- Can identify the board layer robustly or rely on `GPFeatureLayer` parameter.

---

## 9. Selection / FIDSet Checks

## T16 — Classic Describe FIDSet

### What to check

What `arcpy.Describe(layer).FIDSet` returns for no selection, one selection, multiple selections.

### Syntax/features to test

```python
desc = arcpy.Describe(game_layer)
fidset = getattr(desc, 'FIDSet', None)
messages.addMessage(f'classic FIDSet={repr(fidset)}, type={type(fidset)}')
```

### Test cases

- no selection,
- exactly one selected cell,
- multiple selected cells,
- selection cleared,
- layer has definition query if easy to test.

### Record

- Value/type for each case.
- Semicolon string vs other type.
- Empty selection representation.

### Pass condition

- We can reliably detect no/one/many selection.

## T17 — `arcpy.da.Describe` FIDSet

### What to check

Whether `arcpy.da.Describe(layer)['FIDSet']` differs.

### Syntax/features to test

```python
da_desc = arcpy.da.Describe(game_layer)
fidset = da_desc.get('FIDSet')
messages.addMessage(f'da FIDSet={repr(fidset)}, type={type(fidset)}')
```

### Record

- Value/type for no/one/many selection.
- Does key exist?
- Does it return list of ints?

### Pass condition

- At least one Describe approach gives parseable selected IDs.

## T18 — Normalize FIDSet helper design

### What to check

How to parse all observed FIDSet forms.

### Candidate logic

```python
def normalize_fidset(fidset):
    if fidset is None:
        return []
    if isinstance(fidset, str):
        text = fidset.strip()
        if not text:
            return []
        return [int(part) for part in text.split(';') if part.strip()]
    if isinstance(fidset, (list, tuple, set)):
        return [int(x) for x in fidset]
    return [int(fidset)]
```

### Record

- Does this parse every observed case?
- Any IDs are strings or floats?

### Pass condition

- Helper returns `list[int]` for no/one/many selection.

## T19 — OID field name

### What to check

How to get the ObjectID field name for queries/cursors.

### Syntax/features to test

```python
desc = arcpy.Describe(game_layer)
oid_field = desc.OIDFieldName

# or from feature class
fc_desc = arcpy.Describe(board_fc)
oid_field_fc = fc_desc.OIDFieldName
```

### Record

- OID field name, likely `OBJECTID`.
- Any differences between layer and feature class.

### Pass condition

- OID field is known and queryable.

## T20 — Resolve selected OIDs to stable `cell_id`

### What to check

Can selected OIDs be mapped to `cell_id` with a cursor?

### Syntax/features to test

Option A: rely on layer selection with `SearchCursor` over layer:

```python
with arcpy.da.SearchCursor(game_layer, [oid_field, 'cell_id']) as cur:
    rows = list(cur)
```

Option B: explicit where clause on data source:

```python
oids = normalize_fidset(fidset)
where = f"{arcpy.AddFieldDelimiters(board_fc, oid_field)} IN ({','.join(map(str, oids))})"
with arcpy.da.SearchCursor(board_fc, [oid_field, 'cell_id'], where_clause=where) as cur:
    rows = list(cur)
```

### Record

- Does cursor over `game_layer` respect the layer selection?
- Does explicit OID `IN (...)` work?
- Does `AddFieldDelimiters` produce useful syntax in file gdb?

### Pass condition

- Selected OIDs reliably resolve to stable `cell_id`s.

## T21 — Selection clearing / retention

### What to check

Should actions clear selection after running?

### Syntax/features to test

```python
arcpy.management.SelectLayerByAttribute(game_layer, 'CLEAR_SELECTION')
```

### Record

- Does clearing selection work on the `GPFeatureLayer` parameter?
- Does clearing selection improve or hurt operator flow?
- Does map reflect cleared selection?

### Pass condition

- We understand how to clear selection and can choose policy deliberately.

---

## 10. Cursor Update and Lock Checks

## T22 — UpdateCursor on selected rows

### What to check

Can selected cells be updated safely?

### Syntax/features to test

```python
fields = [oid_field, 'cell_id', 'display_state', 'notes', 'test_count']
with arcpy.da.UpdateCursor(game_layer, fields) as cur:
    for oid, cell_id, display_state, notes, test_count in cur:
        # If cursor respects layer selection, this only touches selected rows.
        cur.updateRow([oid, cell_id, 'marked', f'marked oid={oid}', (test_count or 0) + 1])
```

Alternative explicit where clause against feature class if layer cursor ignores selection:

```python
with arcpy.da.UpdateCursor(board_fc, fields, where_clause=where) as cur:
    ...
```

### Record

- Does cursor over layer respect selection?
- Are fields updated?
- Any schema/row locks?
- Does table view show changes immediately?

### Pass condition

- Selected row update works reliably.

## T23 — Repeated update runs

### What to check

Locks and cursor cleanup after repeated actions.

### Procedure

- Select one cell.
- Run `Mark Selected` 5–10 times.
- Select different cells.
- Run again.
- Close attribute table if lock errors appear.

### Record

- Any `schema lock` or `cannot acquire lock` errors?
- Does `with` cursor release locks?
- Does open attribute table matter?

### Pass condition

- Repeated simple actions do not accumulate locks.

## T24 — TestSchemaLock behavior

### What to check

Can we detect schema lock before schema mutation?

### Syntax/features to test

```python
can_lock = arcpy.TestSchemaLock(board_fc)
messages.addMessage(f'TestSchemaLock({board_fc}) -> {can_lock}')
```

### Record

- Result when layer is in map.
- Result when attribute table is open.
- Result after cursor update.

### Pass condition

- `TestSchemaLock` returns useful boolean for setup/migration decisions.

---

## 11. Refresh and Symbology Checks

## T25 — Automatic redraw after field update

### What to check

Does map symbology update automatically after cursor field update?

### Procedure

1. Configure temporary unique value symbology on `display_state` if possible.
2. Select a cell.
3. Run `Mark Selected`, changing `display_state` from `hidden` to `marked`.
4. Observe map.

### Record

- Did map redraw automatically?
- Did table update automatically?
- Was a pan/zoom needed?

### Pass condition

- Visual update is immediate enough or can be fixed with refresh.

## T26 — `arcpy.RefreshLayer`

### What to check

Does `RefreshLayer` work, and what argument should be passed?

### Syntax/features to test

```python
arcpy.RefreshLayer('GameBoard_Spike')
# Also try actual layer name from parameter if different.
arcpy.RefreshLayer(layer_name)
```

### Record

- Does `RefreshLayer` exist in Pro version?
- Does it accept layer name string?
- Does it need exact map layer name?
- Does it error if name is missing?
- Does it actually force redraw?

### Pass condition

- We know whether/how to call refresh.

## T27 — Derived output parameter

### What to check

Does setting derived output help refresh/chain result?

### Syntax/features to test

```python
arcpy.SetParameterAsText(output_param_index, game_layer)
# or if layer object/path required:
# arcpy.SetParameter(output_param_index, game_layer)
```

Also test parameter dependency/symbology if using output param property:

```python
p_output.parameterDependencies = [p_layer.name]
p_output.schema.clone = True
```

### Record

- Does `SetParameterAsText` work for `GPFeatureLayer`?
- Does `SetParameter` work better?
- Any error using layer object vs text path?
- Does output appear in GP history?

### Pass condition

- Derived output does not break tool and ideally helps map update.

## T28 — Apply symbology from layer

### What to check

Can symbology be applied at runtime if needed?

### Syntax/features to test

```python
arcpy.management.ApplySymbologyFromLayer(game_layer, lyrx_path)
```

Optional output symbology property in parameter definition:

```python
p_output.symbology = lyrx_path
```

Optional:

```python
arcpy.SetParameterSymbology(output_param_index, lyrx_path)
```

### Record

- Does `.lyrx` path resolve?
- Does runtime symbology apply?
- Does it persist?
- Does it require layer vs feature class?

### Pass condition

- Preferred: preconfigured symbology works.
- Fallback: runtime apply is possible if needed.

## T29 — Label expression behavior

### What to check

Can labels be preconfigured to show clue counts or state?

### Procedure

Manual for spike:

- Configure label on `cell_id` or `display_state`.
- Update field.
- Observe whether labels refresh.

Optional ArcPy layer inspection:

```python
if lyr.supports('SHOWLABELS'):
    lyr.showLabels = True
```

### Record

- Do labels refresh after field update?
- Does Arcade/Python expression matter?

### Pass condition

- Labels are usable or deferred to manual `.lyrx` setup.

---

## 12. GP Messages and Logging Checks

## T30 — Execution messages

### What to check

Message APIs in Python toolbox execution.

### Syntax/features to test

```python
messages.addMessage('normal message')
messages.addWarningMessage('warning message')
messages.addErrorMessage('error message')
```

Also:

```python
arcpy.AddMessage('arcpy.AddMessage message')
arcpy.AddWarning('arcpy.AddWarning message')
arcpy.AddError('arcpy.AddError message')
```

### Record

- Which messages appear in GP pane?
- Do both `messages` and `arcpy.AddMessage` work?
- Preferred style?

### Pass condition

- Clear turn feedback can be emitted.

## T31 — Log history controls

### What to check

Can noisy GP history be disabled safely?

### Syntax/features to test

```python
arcpy.SetLogHistory(False)
arcpy.SetLogMetadata(False)
```

### Record

- Do these functions exist?
- Any permission/version issue?
- Does disabling history matter?

### Pass condition

- Optional. Useful but not required.

---

## 13. Memory Workspace / GP Operation Checks

## T32 — `memory\\...` output creation/deletion

### What to check

Can memory outputs be created, detected, deleted?

### Syntax/features to test

```python
mem_fc = r'memory\arcpy_game_spike_buffer'
if arcpy.Exists(mem_fc):
    arcpy.management.Delete(mem_fc)
```

### Record

- Does `arcpy.Exists('memory\\...')` work?
- Does `Delete` work?
- Are stale memory outputs a problem?

### Pass condition

- Memory outputs can be managed predictably.

## T33 — Buffer selected or board features into memory

### What to check

Can core vector GP tools write to memory in this environment?

### Syntax/features to test

```python
arcpy.analysis.Buffer(game_layer, r'memory\arcpy_game_spike_buffer', f'{radius} Meters')
```

If coordinate system units are not meters or radius string fails, test numeric or map units:

```python
arcpy.analysis.Buffer(game_layer, r'memory\arcpy_game_spike_buffer', radius)
```

### Record

- Which distance syntax works?
- Does input layer selection limit buffer to selected features?
- Feature count of buffer output.

### Pass condition

- `Buffer` works on small selected features or known inputs.

## T34 — SelectLayerByLocation using memory buffer

### What to check

Can `SelectLayerByLocation` select board cells intersecting memory output?

### Syntax/features to test

```python
arcpy.management.SelectLayerByLocation(
    in_layer=game_layer,
    overlap_type='INTERSECT',
    select_features=r'memory\arcpy_game_spike_buffer',
    selection_type='NEW_SELECTION'
)
```

### Record

- Selection count after operation.
- Does it replace prior selection?
- Does selection visually update?

### Pass condition

- Buffer Defense implementation path is feasible.

## T35 — GetCount on layer selection

### What to check

Does `GetCount` reflect selected rows or full layer?

### Syntax/features to test

```python
count = int(arcpy.management.GetCount(game_layer)[0])
```

### Record

- Count with no selection.
- Count with manual selection.
- Count after SelectLayerByLocation.

### Pass condition

- We understand whether `GetCount(layer)` respects selection.

---

## 14. Feature Set / Drawn Geometry Checks — Optional Stretch

Do not block Survey Sweeper or selected-cell Containment on these. Check only if time remains.

## T36 — `GPFeatureRecordSetLayer` parameter renders

### What to check

Can a Feature Set parameter be defined and edited in the GP pane?

### Syntax/features to test

```python
p_place = arcpy.Parameter(
    displayName='Placement Feature',
    name='placement_feature',
    datatype='GPFeatureRecordSetLayer',
    parameterType='Optional',
    direction='Input'
)
```

### Record

- Does GP pane show interactive drawing control?
- Does it require a template/schema?
- Does geometry type default make sense?

### Pass condition

- Optional. Good if it works, but selected-cell flow remains primary.

## T37 — Feature Set schema/template

### What to check

How to set geometry type/symbology for Feature Set.

Potential approaches:

- Use a template feature class.
- Use a `.lyrx` file.
- Use parameter value assignment from existing layer.

### Record

- What setup is required?
- Is it too clunky for tonight?

### Pass condition

- We can decide whether to defer Feature Set drawing.

## T38 — Reading Feature Set input

### What to check

If a feature is drawn, what does the tool receive?

### Syntax/features to inspect

```python
placement = parameters[7].valueAsText
messages.addMessage(f'placement valueAsText={placement!r}')

# If valid path/layer:
arcpy.management.GetCount(placement)
```

### Record

- Value type/path.
- Feature count.
- Geometry type.
- Whether it can feed Buffer/SelectLayerByLocation.

### Pass condition

- Optional. If weird, defer to later.

---

## 15. Project/Packaging/Recovery Checks

## T39 — Project close/reopen behavior

### What to check

Does board/tool state survive reopening Pro?

### Procedure

1. Create tiny board.
2. Add to map.
3. Save project.
4. Close/reopen.
5. Run `Describe Selection` or `Mark Selected` again.

### Record

- Layer path intact?
- Toolbox path intact?
- Symbology intact?
- Selection cleared as expected?

### Pass condition

- Project can be reopened without manual repair.

## T40 — Layer renamed by user

### What to check

Does tool still work if layer display name changes?

### Procedure

1. Rename map layer from `GameBoard_Spike` to `My Board`.
2. Pass it as `Game Layer` parameter.
3. Run `Describe Selection`.
4. Run `Mark Selected`.

### Record

- Does `GPFeatureLayer` parameter still work by object/path?
- Does `RefreshLayer` fail if using hardcoded name?
- Should refresh use parameter layer name instead?

### Pass condition

- Core actions work when layer is provided explicitly.
- Hardcoded layer names are avoided or limited.

## T41 — Partial prior state recovery

### What to check

What happens if board exists with old rows/fields?

### Procedure

- Run `Create Tiny Board`.
- Run it again.
- Delete some rows manually and run again.
- Leave layer in map and run reset.

### Record

- Does reset clear/reseed correctly?
- Any stale selection issue?
- Any duplicate cell IDs?

### Pass condition

- Reset behavior is predictable.

---

## 16. Decision Matrix After Spike

Use this to decide implementation direction.

## If `.pyt` fails to load

Do not implement game yet.

Next steps:

- fix syntax/import paths,
- simplify toolbox to one file,
- avoid sibling imports until proven,
- test with no external modules.

## If parameters work but dynamic filters are flaky

Plan change:

- keep action dropdown manually small per implementation phase,
- avoid clever dynamic filtering,
- use validation messages to reject unavailable actions.

## If `FIDSet` works cleanly

Plan confirmed:

- selection-based Survey Sweeper and Containment are viable.

## If `FIDSet` is unreliable but cursors respect layer selection

Plan change:

- resolve selected rows by cursor over layer instead of parsing FIDSet directly,
- still map to `cell_id`.

## If selection handling is unreliable overall

Fallback options:

- use `cell_id` text parameter for first prototype,
- use selected layer only in final polish,
- use `Feature Set` or edit table workflow later.

## If cursor updates work but map does not refresh

Plan change:

- keep fields/logs as truth,
- require manual refresh or layer refresh step in demo,
- test derived output and `RefreshLayer`,
- preconfigure symbology carefully.

## If schema locks are common

Plan change:

- never delete feature classes once in map,
- use `DeleteRows`,
- separate `Initialize Workspace` from `New Game`,
- document closing attribute tables before reset if necessary.

## If `memory\\...` Buffer works

Plan confirmed:

- Buffer Defense is a viable first Stage 3 power.

## If `GPFeatureRecordSetLayer` is clunky

Plan confirmed:

- defer Feature Set drawing,
- implement selected-cell Buffer Defense or use existing point/line layer first.

---

## 17. Must-Capture Evidence Checklist

During tonight’s run, capture these exact observations:

- ArcGIS Pro version.
- Python executable path.
- Toolbox load success/failure.
- Parameter list screenshot or notes.
- `arcpy.Describe(layer).FIDSet` values for:
  - no selection,
  - one selection,
  - multiple selections.
- `arcpy.da.Describe(layer).get('FIDSet')` values for same cases.
- OID field name.
- Whether cursor over `GPFeatureLayer` respects selection.
- Whether explicit OID where clause works.
- Whether update cursor changes selected row.
- Whether map redraws automatically.
- Whether `arcpy.RefreshLayer(...)` helps.
- Whether derived output parameter causes any visible effect.
- Whether `.lyrx` or temporary symbology updates work.
- Whether memory Buffer succeeds.
- Whether SelectLayerByLocation using memory buffer succeeds.
- Any schema lock errors.
- Behavior after repeated runs.
- Behavior after closing/reopening project if time allows.

---

## 18. Recommended Pass/Fail Summary Format

After the spike, summarize like this:

```markdown
## Feasibility Verdict

- Python toolbox controller: PASS / PARTIAL / FAIL
- Parameter staging: PASS / PARTIAL / FAIL
- Selection as input: PASS / PARTIAL / FAIL
- OID -> cell_id resolution: PASS / PARTIAL / FAIL
- Field updates: PASS / PARTIAL / FAIL
- Refresh/symbology: PASS / PARTIAL / FAIL
- Memory buffer/select: PASS / PARTIAL / FAIL
- Feature Set drawing: PASS / PARTIAL / FAIL / NOT TESTED
- Repeated run/locks: PASS / PARTIAL / FAIL

## Architecture changes needed

1.
2.
3.

## Safe next implementation step

- Proceed to Survey Sweeper rules/schema, or
- Fix spike issue first: ...
```

---

## 19. Final Tonight Checklist

Before opening ArcGIS Pro:

- [ ] Put the spike `.pyt` somewhere simple, e.g. project `toolbox/`.
- [ ] Open an `.aprx` with a blank map.
- [ ] Add the toolbox.
- [ ] Run `Ping Environment`.
- [ ] Run `Create Tiny Board`.
- [ ] Add board to map if tool did not auto-add it.
- [ ] Configure quick unique-value symbology on `display_state` if needed.
- [ ] Select one cell.
- [ ] Run `Describe Selection`.
- [ ] Run `Mark Selected`.
- [ ] Observe map/table/message/log behavior.
- [ ] Select multiple cells and repeat.
- [ ] Clear selection and repeat.
- [ ] Run memory buffer test if time remains.
- [ ] Save notes into `ideas/feasibility-spike-results.md`.

The spike is successful even if it finds failures. The goal is to learn the real ArcGIS Pro behavior before the game architecture hardens.
