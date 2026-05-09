"""ArcPy Game — Feasibility Spike Toolbox.

Run this in ArcGIS Pro to exercise tests T01-T41 from
`ideas/feasibility-spike-syntax-feature-inventory.md`.

The toolbox exposes a single tool (`Game Controller Spike`) with an
`Action` dropdown. Each action runs a cluster of related T-tests and
emits GP messages tagged with the T-number, so the run-log template in
`ideas/feasibility-spike-results.md` can be filled in directly from the
ArcGIS Pro Geoprocessing pane without guesswork.

The spike intentionally keeps everything in one file: no sibling
imports, no external modules, no licensed extensions. If something
fails, the failure is on this file — not the import system.
"""

import os
import platform
import random
import sys
import traceback

import arcpy


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOOLBOX_LABEL = "ArcPy Game Spike"
TOOLBOX_ALIAS = "arcpy_game_spike"

DEFAULT_GDB_NAME = "arcpy_game_spike.gdb"
BOARD_FC_NAME = "GameBoard_Spike"
BOARD_ROWS = 3
BOARD_COLS = 3
CELL_SIZE = 100.0  # map units (meters in Web Mercator)

# Param indices — keep in sync with getParameterInfo().
P_WORKSPACE = 0
P_LAYER = 1
P_MODE = 2
P_ACTION = 3
P_SEED = 4
P_RADIUS = 5
P_OUTPUT = 6

ACTIONS_SURVEY = [
    "Ping Environment",
    "Create Tiny Board",
    "Describe Parameters",
    "Describe Selection",
    "Mark Selected",
    "Test Refresh",
    "Test Symbology Hook",
    "Test Memory Buffer",
    "Reset Tiny Board",
]

ACTIONS_CONTAINMENT = [
    "Ping Environment",
    "Describe Parameters",
    "Describe Selection",
    "Mark Selected",
    "Test Memory Buffer",
]

# Field schema for the spike board — mirrors T09.
BOARD_FIELDS = [
    # (name, type, alias, length_or_None)
    ("cell_id",       "TEXT", "Cell ID",           32),
    ("row_idx",       "LONG", "Row Index",         None),
    ("col_idx",       "LONG", "Column Index",      None),
    ("display_state", "TEXT", "Map Display State", 32),
    ("notes",         "TEXT", "Notes",             255),
    ("test_count",    "LONG", "Test Count",        None),
]


# ---------------------------------------------------------------------------
# Helpers (module level — pure functions where possible)
# ---------------------------------------------------------------------------

def _log(messages, tag, text):
    """Emit a tagged GP message via the toolbox-native API.

    T30 confirmed (Pro 3.6) that messages.addMessage and arcpy.AddMessage
    both render in the GP pane. We use the toolbox-native style only;
    sending both produced duplicate lines.
    """
    line = "[{tag}] {text}".format(tag=tag, text=text)
    try:
        messages.addMessage(line)
    except Exception:
        arcpy.AddMessage(line)


def _log_warn(messages, tag, text):
    line = "[{tag}] WARN: {text}".format(tag=tag, text=text)
    try:
        messages.addWarningMessage(line)
    except Exception:
        arcpy.AddWarning(line)


def _log_err(messages, tag, text):
    line = "[{tag}] ERROR: {text}".format(tag=tag, text=text)
    try:
        messages.addErrorMessage(line)
    except Exception:
        arcpy.AddError(line)


def _safe(messages, tag, fn, *args, **kwargs):
    """Run `fn(*args, **kwargs)`, catching and logging any exception.

    Returns (ok: bool, value_or_None). Lets a single test cluster keep
    running through partial failures so the spike still emits maximum
    evidence per session.
    """
    try:
        return True, fn(*args, **kwargs)
    except Exception as exc:
        _log_warn(messages, tag, "{cls}: {exc}".format(
            cls=type(exc).__name__, exc=exc))
        _log_warn(messages, tag, traceback.format_exc().strip().splitlines()[-1])
        return False, None


def square_polygon(x0, y0, size, spatial_ref):
    """Build a closed square polygon. Used by Create Tiny Board (T11)."""
    arr = arcpy.Array([
        arcpy.Point(x0,        y0),
        arcpy.Point(x0 + size, y0),
        arcpy.Point(x0 + size, y0 + size),
        arcpy.Point(x0,        y0 + size),
        arcpy.Point(x0,        y0),
    ])
    return arcpy.Polygon(arr, spatial_ref)


def add_field_if_missing(fc, name, field_type, alias=None, length=None):
    """Idempotent AddField. Skips if a field with this name (case-insensitive) exists.

    Returns True if a field was added, False if skipped.
    """
    existing = {f.name.lower() for f in arcpy.ListFields(fc)}
    if name.lower() in existing:
        return False
    kwargs = {}
    if alias:
        kwargs["field_alias"] = alias
    if length is not None and field_type.upper() == "TEXT":
        kwargs["field_length"] = length
    arcpy.management.AddField(fc, name, field_type, **kwargs)
    return True


def resolve_workspace(workspace_param_value, messages):
    """Decide which gdb path to use. T06.

    Priority:
    1. Explicit workspace parameter, if provided.
    2. `<aprx.homeFolder>/data/<DEFAULT_GDB_NAME>` if CURRENT works.
    3. Scratch workspace fallback.
    """
    if workspace_param_value:
        return str(workspace_param_value)

    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        home = aprx.homeFolder
        if home:
            return os.path.join(home, "data", DEFAULT_GDB_NAME)
    except Exception as exc:
        _log_warn(messages, "T06", "ArcGISProject('CURRENT') failed: {exc}".format(exc=exc))

    scratch = arcpy.env.scratchWorkspace or arcpy.env.scratchFolder
    if scratch:
        return os.path.join(scratch, DEFAULT_GDB_NAME)
    return os.path.join(os.path.expanduser("~"), DEFAULT_GDB_NAME)


def ensure_gdb(gdb_path, messages):
    """Create the gdb if it does not exist. T07."""
    folder = os.path.dirname(gdb_path)
    name = os.path.basename(gdb_path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
        _log(messages, "T07", "created folder: {folder}".format(folder=folder))
    if not arcpy.Exists(gdb_path):
        arcpy.management.CreateFileGDB(folder, name)
        _log(messages, "T07", "created gdb: {gdb}".format(gdb=gdb_path))
    else:
        _log(messages, "T07", "gdb exists: {gdb}".format(gdb=gdb_path))
    return gdb_path


def get_active_map_sr(messages):
    """Return the active map's SpatialReference, or fall back to Web Mercator."""
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap
        if active_map is not None:
            sr = active_map.spatialReference
            if sr is not None and sr.factoryCode:
                _log(messages, "T11", "using active map SR: {name} ({code})".format(
                    name=sr.name, code=sr.factoryCode))
                return sr
    except Exception as exc:
        _log_warn(messages, "T11", "could not read active map SR: {exc}".format(exc=exc))
    _log(messages, "T11", "falling back to Web Mercator (3857)")
    return arcpy.SpatialReference(3857)


def normalize_fidset(fidset):
    """Normalize FIDSet variants into a deduplicated, ascending ``list[int]``.

    Handles every form observed across classic Describe and da.Describe:
      - ``None`` / ``""`` -> ``[]``
      - ``"123"`` -> ``[123]``
      - ``"123;456;789"`` (semicolon-delimited) -> ``[123, 456, 789]``
      - ``"123,456"`` (rare comma form) -> ``[123, 456]``
      - ``[1, 2, 3]`` / tuples / sets -> sorted unique
      - ``123`` (bare int) -> ``[123]``

    Policy: warn-and-skip. A single malformed entry does NOT raise; it is
    silently dropped. The spike still gets useful output even if Pro hands
    us something unexpected.
    """
    if fidset is None:
        return []
    if isinstance(fidset, str):
        text = fidset.strip()
        if not text:
            return []
        parts = text.replace(",", ";").split(";")
        out = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            try:
                out.append(int(part))
            except ValueError:
                continue
        return sorted(set(out))
    if isinstance(fidset, (list, tuple, set, frozenset)):
        out = []
        for x in fidset:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return sorted(set(out))
    try:
        return [int(fidset)]
    except (TypeError, ValueError):
        return []


def apply_mark_selected(row, oid):
    """Mutate one cursor row for the Mark Selected action.

    Cursor schema:
        [oid_field, "cell_id", "display_state", "notes", "test_count"]

    Behavior:
      - ``test_count`` always increments (None -> 1).
      - ``display_state`` transitions:
          "hidden"        -> "marked"
          "marked"        -> "marked-bumped"
          anything else   -> unchanged
      - ``notes`` records previous state and OID, useful for T22 evidence.
    """
    _, cell_id, display_state, _notes, test_count = row
    prev_state = display_state or "hidden"
    next_count = (test_count or 0) + 1

    transitions = {"hidden": "marked", "marked": "marked-bumped"}
    next_state = transitions.get(prev_state, prev_state)

    next_notes = "marked oid={oid} cell={cell} prev={prev} count={n}".format(
        oid=oid, cell=cell_id, prev=prev_state, n=next_count,
    )
    row[2] = next_state
    row[3] = next_notes
    row[4] = next_count
    return row


# ---------------------------------------------------------------------------
# Toolbox
# ---------------------------------------------------------------------------

class Toolbox(object):
    def __init__(self):
        self.label = TOOLBOX_LABEL
        self.alias = TOOLBOX_ALIAS
        self.tools = [GameControllerSpike]


# ---------------------------------------------------------------------------
# Tool: Game Controller Spike
# ---------------------------------------------------------------------------

class GameControllerSpike(object):
    """Single-tool dispatcher. Action dropdown selects which T-cluster runs."""

    def __init__(self):
        self.label = "Game Controller Spike"
        self.description = (
            "Feasibility spike for ArcPy game controller. "
            "Runs T01-T41 from feasibility-spike-syntax-feature-inventory.md."
        )
        self.canRunInBackground = False

    # ---- Parameters (T03) ----
    def getParameterInfo(self):
        p_workspace = arcpy.Parameter(
            displayName="Game Workspace (optional)",
            name="game_workspace",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input",
        )

        p_layer = arcpy.Parameter(
            displayName="Game Layer",
            name="game_layer",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
        )

        p_mode = arcpy.Parameter(
            displayName="Scenario Mode",
            name="scenario_mode",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        p_mode.filter.type = "ValueList"
        p_mode.filter.list = ["Survey Sweeper", "Containment Commander"]
        p_mode.value = "Survey Sweeper"

        p_action = arcpy.Parameter(
            displayName="Action",
            name="action",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p_action.filter.type = "ValueList"
        p_action.filter.list = list(ACTIONS_SURVEY)
        p_action.value = "Ping Environment"

        p_seed = arcpy.Parameter(
            displayName="Random Seed",
            name="random_seed",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input",
        )
        p_seed.value = 2026

        p_radius = arcpy.Parameter(
            displayName="Amount / Radius",
            name="amount_radius",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_radius.value = 150.0

        p_output = arcpy.Parameter(
            displayName="Output Game Layer",
            name="output_game_layer",
            datatype="GPFeatureLayer",
            parameterType="Derived",
            direction="Output",
        )

        return [p_workspace, p_layer, p_mode, p_action, p_seed, p_radius, p_output]

    # ---- Dynamic filtering (T04) ----
    def updateParameters(self, parameters):
        mode = parameters[P_MODE].valueAsText
        action_param = parameters[P_ACTION]

        if mode == "Containment Commander":
            allowed = list(ACTIONS_CONTAINMENT)
        else:
            allowed = list(ACTIONS_SURVEY)

        action_param.filter.list = allowed
        if action_param.value not in allowed:
            action_param.value = allowed[0]

        action = action_param.valueAsText
        # Radius only matters for the buffer test.
        parameters[P_RADIUS].enabled = action in ("Test Memory Buffer",)
        # Seed only matters for board creation/reset.
        parameters[P_SEED].enabled = action in ("Create Tiny Board", "Reset Tiny Board")
        # Layer required for selection-based actions.
        layer_required = action in (
            "Describe Selection", "Mark Selected", "Test Refresh",
            "Test Symbology Hook", "Test Memory Buffer", "Reset Tiny Board",
        )
        parameters[P_LAYER].parameterType = "Required" if layer_required else "Optional"
        return

    # ---- Validation messages (T05) ----
    def updateMessages(self, parameters):
        action = parameters[P_ACTION].valueAsText
        layer_param = parameters[P_LAYER]
        radius_param = parameters[P_RADIUS]

        layer_required = action in (
            "Describe Selection", "Mark Selected", "Test Refresh",
            "Test Symbology Hook", "Test Memory Buffer", "Reset Tiny Board",
        )
        if layer_required and not layer_param.value:
            layer_param.setErrorMessage(
                "Choose a GameBoard feature layer for action '{action}'.".format(action=action)
            )
        else:
            layer_param.clearMessage()

        if action == "Test Memory Buffer" and radius_param.value is not None:
            try:
                radius = float(radius_param.value)
            except (TypeError, ValueError):
                radius = None
            if radius is not None:
                if radius <= 0:
                    radius_param.setErrorMessage("Radius must be greater than 0.")
                elif radius > 10000:
                    radius_param.setWarningMessage("Large radius may select many cells.")
                else:
                    radius_param.clearMessage()
        else:
            radius_param.clearMessage()
        return

    # ---- Dispatch ----
    def execute(self, parameters, messages):
        action = parameters[P_ACTION].valueAsText or "Ping Environment"
        _log(messages, "DISPATCH", "action = {action!r}".format(action=action))

        handlers = {
            "Ping Environment":     self._action_ping_environment,
            "Create Tiny Board":    self._action_create_tiny_board,
            "Describe Parameters":  self._action_describe_parameters,
            "Describe Selection":   self._action_describe_selection,
            "Mark Selected":        self._action_mark_selected,
            "Test Refresh":         self._action_test_refresh,
            "Test Symbology Hook":  self._action_test_symbology_hook,
            "Test Memory Buffer":   self._action_test_memory_buffer,
            "Reset Tiny Board":     self._action_reset_tiny_board,
        }
        handler = handlers.get(action)
        if handler is None:
            _log_err(messages, "DISPATCH", "unknown action: {action!r}".format(action=action))
            return

        handler(parameters, messages)
        _log(messages, "DISPATCH", "action {action!r} complete.".format(action=action))

    # ----------------------------------------------------------------- #
    # Action handlers — each one runs a cluster of T-tests and logs evidence.
    # ----------------------------------------------------------------- #

    # ---- T01 ----
    def _action_ping_environment(self, parameters, messages):
        _log(messages, "T01", "sys.executable = {x}".format(x=sys.executable))
        _log(messages, "T01", "sys.version = {x}".format(x=sys.version.replace("\n", " ")))
        _log(messages, "T01", "platform = {x}".format(x=platform.platform()))

        ok, install = _safe(messages, "T01", arcpy.GetInstallInfo)
        if ok and install:
            for k in ("ProductName", "Version", "BuildNumber", "InstallDir"):
                _log(messages, "T01", "GetInstallInfo[{k}] = {v}".format(k=k, v=install.get(k)))

        _log(messages, "T01", "env.workspace = {x!r}".format(x=arcpy.env.workspace))
        _log(messages, "T01", "env.scratchWorkspace = {x!r}".format(x=arcpy.env.scratchWorkspace))
        _log(messages, "T01", "env.overwriteOutput = {x!r}".format(x=arcpy.env.overwriteOutput))

        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            _log(messages, "T01", "ArcGISProject('CURRENT') OK -> filePath={p!r}".format(p=aprx.filePath))
            _log(messages, "T01", "homeFolder = {p!r}".format(p=aprx.homeFolder))
            am = aprx.activeMap
            _log(messages, "T01", "activeMap = {m!r}".format(m=getattr(am, "name", None)))
        except Exception as exc:
            _log_warn(messages, "T01", "ArcGISProject('CURRENT') failed: {exc}".format(exc=exc))

    # ---- T03, T05 ----
    def _action_describe_parameters(self, parameters, messages):
        for i, p in enumerate(parameters):
            _log(messages, "T03", "param[{i}] name={n!r} type={t!r} value={v!r} text={tx!r}".format(
                i=i, n=p.name, t=p.datatype, v=p.value, tx=p.valueAsText,
            ))

    # ---- T06–T15 ----
    def _action_create_tiny_board(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        _log(messages, "T06", "resolved gdb = {p!r}".format(p=gdb_path))

        ok, _ = _safe(messages, "T07", ensure_gdb, gdb_path, messages)
        if not ok:
            return

        sr = get_active_map_sr(messages)
        board_fc = os.path.join(gdb_path, BOARD_FC_NAME)

        # T08
        if not arcpy.Exists(board_fc):
            _safe(messages, "T08", arcpy.management.CreateFeatureclass,
                  out_path=gdb_path,
                  out_name=BOARD_FC_NAME,
                  geometry_type="POLYGON",
                  spatial_reference=sr)
            _log(messages, "T08", "created feature class: {p}".format(p=board_fc))
        else:
            _log(messages, "T08", "feature class exists: {p}".format(p=board_fc))

        # T09
        added = []
        for name, ftype, alias, length in BOARD_FIELDS:
            ok, was_added = _safe(messages, "T09",
                                  add_field_if_missing, board_fc, name, ftype, alias, length)
            if ok and was_added:
                added.append(name)
        if added:
            _log(messages, "T09", "added fields: {fs}".format(fs=", ".join(added)))
        else:
            _log(messages, "T09", "all fields already present")

        # T10 — idempotent: skip if any index already exists on cell_id.
        try:
            existing_idx = arcpy.ListIndexes(board_fc) or []
            already_indexed = any(
                any(f.name.lower() == "cell_id" for f in idx.fields)
                for idx in existing_idx
            )
        except Exception:
            already_indexed = False

        if already_indexed:
            _log(messages, "T10", "index on cell_id already present, skipping AddIndex")
        else:
            ok, _ = _safe(messages, "T10",
                          arcpy.management.AddIndex, board_fc, "cell_id",
                          "idx_gameboard_spike_cell_id", "UNIQUE")
            if not ok:
                _safe(messages, "T10",
                      arcpy.management.AddIndex, board_fc, "cell_id",
                      "idx_gameboard_spike_cell_id_nonunique")

        # T13: clear existing rows so re-runs are idempotent.
        ok, _ = _safe(messages, "T13", arcpy.management.DeleteRows, board_fc)
        _log(messages, "T13", "DeleteRows result: {ok}".format(ok=ok))

        # T11/T12: insert grid.
        seed_val = parameters[P_SEED].value
        if seed_val is not None:
            random.seed(int(seed_val))

        insert_fields = ["SHAPE@", "cell_id", "row_idx", "col_idx",
                         "display_state", "notes", "test_count"]
        try:
            with arcpy.da.InsertCursor(board_fc, insert_fields) as cur:
                for r in range(BOARD_ROWS):
                    for c in range(BOARD_COLS):
                        cell_id = "R{r}C{c}".format(r=r, c=c)
                        geom = square_polygon(c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, sr)
                        cur.insertRow([
                            geom, cell_id, r, c,
                            "hidden", "created by spike", 0,
                        ])
            _log(messages, "T12", "inserted {n} rows".format(n=BOARD_ROWS * BOARD_COLS))
        except Exception as exc:
            _log_err(messages, "T12", "InsertCursor failed: {exc}".format(exc=exc))
            return

        count = int(arcpy.management.GetCount(board_fc)[0])
        _log(messages, "T12", "GetCount post-insert = {n}".format(n=count))

        # T14: try to add to active map.
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            active_map = aprx.activeMap
            if active_map is not None:
                existing_names = {lyr.name for lyr in active_map.listLayers()}
                if BOARD_FC_NAME in existing_names:
                    _log(messages, "T14", "layer already in map; skipping addDataFromPath")
                else:
                    layer_obj = active_map.addDataFromPath(board_fc)
                    _log(messages, "T14", "added to map as {n!r}".format(n=layer_obj.name))
            else:
                _log_warn(messages, "T14", "no active map")
        except Exception as exc:
            _log_warn(messages, "T14", "addDataFromPath failed: {exc}".format(exc=exc))

        # T27: derived output.
        try:
            arcpy.SetParameterAsText(P_OUTPUT, board_fc)
            _log(messages, "T27", "SetParameterAsText({i}, {p}) OK".format(i=P_OUTPUT, p=board_fc))
        except Exception as exc:
            _log_warn(messages, "T27", "SetParameterAsText failed: {exc}".format(exc=exc))

    # ---- T16–T21, T35 ----
    def _action_describe_selection(self, parameters, messages):
        layer = parameters[P_LAYER].value
        if not layer:
            _log_err(messages, "T16", "no Game Layer parameter — cannot describe selection")
            return

        # T16: classic Describe FIDSet.
        try:
            desc = arcpy.Describe(layer)
            classic_fid = getattr(desc, "FIDSet", None)
            _log(messages, "T16", "classic FIDSet = {v!r} type={t}".format(
                v=classic_fid, t=type(classic_fid).__name__))
            oid_field = getattr(desc, "OIDFieldName", None)
            _log(messages, "T19", "OIDFieldName (Describe) = {f!r}".format(f=oid_field))
        except Exception as exc:
            _log_warn(messages, "T16", "classic Describe failed: {exc}".format(exc=exc))
            classic_fid = None
            oid_field = None

        # T17: da.Describe FIDSet.
        try:
            da_desc = arcpy.da.Describe(layer)
            da_fid = da_desc.get("FIDSet")
            _log(messages, "T17", "da FIDSet = {v!r} type={t}".format(
                v=da_fid, t=type(da_fid).__name__))
            if not oid_field:
                oid_field = da_desc.get("OIDFieldName")
                _log(messages, "T19", "OIDFieldName (da) = {f!r}".format(f=oid_field))
        except Exception as exc:
            _log_warn(messages, "T17", "da.Describe failed: {exc}".format(exc=exc))
            da_fid = None

        # T18: normalize both forms; prefer da result if it's non-empty.
        selected_oids = []
        for tag, raw in (("classic", classic_fid), ("da", da_fid)):
            ok, normalized = _safe(messages, "T18", normalize_fidset, raw)
            if ok:
                _log(messages, "T18", "{tag}: normalized -> {n!r}".format(tag=tag, n=normalized))
                if normalized and not selected_oids:
                    selected_oids = normalized
            else:
                _log_warn(messages, "T18", "{tag}: normalization failed".format(tag=tag))
        _log(messages, "T18", "selected_oids (chosen) = {v!r}".format(v=selected_oids))

        # T35: GetCount on layer (does it respect selection?).
        ok, count = _safe(messages, "T35", arcpy.management.GetCount, layer)
        if ok:
            _log(messages, "T35", "GetCount(layer)[0] = {n}".format(n=int(count[0])))

        # T20: cursor over layer (does it respect selection?).
        if oid_field:
            try:
                rows = []
                fields = [oid_field, "cell_id"] if "cell_id" in {f.name for f in arcpy.ListFields(layer)} else [oid_field]
                with arcpy.da.SearchCursor(layer, fields) as cur:
                    for row in cur:
                        rows.append(row)
                _log(messages, "T20", "SearchCursor(layer) returned {n} rows".format(n=len(rows)))
                for row in rows[:10]:
                    _log(messages, "T20", "  row = {r!r}".format(r=row))
                if len(rows) > 10:
                    _log(messages, "T20", "  ... ({n} more)".format(n=len(rows) - 10))
            except Exception as exc:
                _log_warn(messages, "T20", "SearchCursor failed: {exc}".format(exc=exc))

        # T20 (option B): explicit IN clause via AddFieldDelimiters.
        if oid_field and selected_oids:
            try:
                desc2 = arcpy.Describe(layer)
                source = getattr(desc2, "catalogPath", None) or layer
                where = "{f} IN ({ids})".format(
                    f=arcpy.AddFieldDelimiters(source, oid_field),
                    ids=",".join(str(i) for i in selected_oids),
                )
                _log(messages, "T20", "explicit where = {w}".format(w=where))
                with arcpy.da.SearchCursor(source, [oid_field, "cell_id"], where_clause=where) as cur:
                    explicit_rows = list(cur)
                _log(messages, "T20", "explicit IN cursor returned {n} rows".format(n=len(explicit_rows)))
                for row in explicit_rows[:10]:
                    _log(messages, "T20", "  explicit row = {r!r}".format(r=row))
            except Exception as exc:
                _log_warn(messages, "T20", "explicit-IN cursor failed: {exc}".format(exc=exc))
        else:
            _log(messages, "T20", "no selection — skipping explicit-IN test")

    # ---- T22–T24, T25 ----
    def _action_mark_selected(self, parameters, messages):
        layer = parameters[P_LAYER].value
        if not layer:
            _log_err(messages, "T22", "no Game Layer")
            return

        try:
            oid_field = arcpy.Describe(layer).OIDFieldName
        except Exception as exc:
            _log_err(messages, "T22", "Describe failed: {exc}".format(exc=exc))
            return

        # T24: schema lock peek.
        try:
            can_lock = arcpy.TestSchemaLock(layer)
            _log(messages, "T24", "TestSchemaLock(layer) = {v}".format(v=can_lock))
        except Exception as exc:
            _log_warn(messages, "T24", "TestSchemaLock failed: {exc}".format(exc=exc))

        # T22: UpdateCursor over layer — relies on layer selection respect.
        fields = [oid_field, "cell_id", "display_state", "notes", "test_count"]
        updated = 0
        try:
            with arcpy.da.UpdateCursor(layer, fields) as cur:
                for row in cur:
                    new_row = apply_mark_selected(list(row), row[0])
                    cur.updateRow(new_row)
                    updated += 1
            _log(messages, "T22", "UpdateCursor updated {n} rows (cursor over layer)".format(n=updated))
        except Exception as exc:
            _log_err(messages, "T22", "UpdateCursor failed: {exc}".format(exc=exc))
            return

        # T25: did the map redraw? We can't observe rendering from Python; emit a hint.
        _log(messages, "T25",
             "field updates issued. Inspect map: did symbology change without manual refresh?")

        # T27: derived output for downstream chain.
        try:
            arcpy.SetParameterAsText(P_OUTPUT, layer if isinstance(layer, str) else layer.name)
        except Exception as exc:
            _log_warn(messages, "T27", "SetParameterAsText failed: {exc}".format(exc=exc))

    # ---- T26, T27 ----
    def _action_test_refresh(self, parameters, messages):
        layer = parameters[P_LAYER].value
        if not layer:
            _log_err(messages, "T26", "no Game Layer")
            return

        layer_name = layer if isinstance(layer, str) else getattr(layer, "name", None)
        _log(messages, "T26", "calling RefreshLayer with name = {n!r}".format(n=layer_name))

        # T26: RefreshLayer — may not exist in Pro; .RefreshActiveView is also gone.
        try:
            arcpy.RefreshLayer(layer_name)
            _log(messages, "T26", "arcpy.RefreshLayer returned without error")
        except AttributeError:
            _log_warn(messages, "T26", "arcpy.RefreshLayer does not exist in this Pro version")
        except Exception as exc:
            _log_warn(messages, "T26", "RefreshLayer failed: {exc}".format(exc=exc))

        # T27: derived output again.
        try:
            arcpy.SetParameterAsText(P_OUTPUT, layer_name)
            _log(messages, "T27", "SetParameterAsText(P_OUTPUT, layer_name) OK")
        except Exception as exc:
            _log_warn(messages, "T27", "SetParameterAsText failed: {exc}".format(exc=exc))

    # ---- T28, T29 ----
    def _action_test_symbology_hook(self, parameters, messages):
        layer = parameters[P_LAYER].value
        if not layer:
            _log_err(messages, "T28", "no Game Layer")
            return

        # We don't ship a .lyrx — just probe whether the call surface exists.
        _log(messages, "T28",
             "skipping ApplySymbologyFromLayer (no .lyrx in spike); call surface check only")
        has_apply = hasattr(arcpy.management, "ApplySymbologyFromLayer")
        _log(messages, "T28", "arcpy.management.ApplySymbologyFromLayer present = {v}".format(v=has_apply))

        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            active_map = aprx.activeMap
            if active_map is None:
                _log_warn(messages, "T29", "no active map")
                return
            for lyr in active_map.listLayers():
                if not lyr.supports("DATASOURCE"):
                    continue
                ds = lyr.dataSource
                if BOARD_FC_NAME.lower() not in str(ds).lower():
                    continue
                _log(messages, "T29", "found board layer: name={n!r} ds={d!r}".format(
                    n=lyr.name, d=ds))
                if lyr.supports("SHOWLABELS"):
                    _log(messages, "T29", "showLabels (current) = {v}".format(v=lyr.showLabels))
                else:
                    _log(messages, "T29", "layer does not support SHOWLABELS")
        except Exception as exc:
            _log_warn(messages, "T29", "label inspection failed: {exc}".format(exc=exc))

    # ---- T32–T35 ----
    def _action_test_memory_buffer(self, parameters, messages):
        layer = parameters[P_LAYER].value
        if not layer:
            _log_err(messages, "T33", "no Game Layer")
            return
        radius = parameters[P_RADIUS].value
        if radius is None or float(radius) <= 0:
            _log_err(messages, "T33", "Radius must be > 0")
            return

        mem_fc = r"memory\arcpy_game_spike_buffer"

        # T32
        try:
            if arcpy.Exists(mem_fc):
                arcpy.management.Delete(mem_fc)
                _log(messages, "T32", "deleted stale memory output")
            else:
                _log(messages, "T32", "no stale memory output")
        except Exception as exc:
            _log_warn(messages, "T32", "Exists/Delete failed: {exc}".format(exc=exc))

        # T33: try a labeled-distance string first, then numeric fallback.
        ok = False
        try:
            arcpy.analysis.Buffer(layer, mem_fc, "{r} Meters".format(r=radius))
            ok = True
            _log(messages, "T33", "Buffer with 'X Meters' succeeded")
        except Exception as exc:
            _log_warn(messages, "T33", "Buffer with 'X Meters' failed: {exc}".format(exc=exc))
            try:
                arcpy.analysis.Buffer(layer, mem_fc, float(radius))
                ok = True
                _log(messages, "T33", "Buffer with numeric distance succeeded")
            except Exception as exc2:
                _log_err(messages, "T33", "Buffer with numeric also failed: {exc}".format(exc=exc2))

        if not ok:
            return

        try:
            n = int(arcpy.management.GetCount(mem_fc)[0])
            _log(messages, "T33", "buffer feature count = {n}".format(n=n))
        except Exception as exc:
            _log_warn(messages, "T33", "GetCount on buffer failed: {exc}".format(exc=exc))

        # T34: SelectLayerByLocation.
        try:
            arcpy.management.SelectLayerByLocation(
                in_layer=layer,
                overlap_type="INTERSECT",
                select_features=mem_fc,
                selection_type="NEW_SELECTION",
            )
            _log(messages, "T34", "SelectLayerByLocation issued")
        except Exception as exc:
            _log_err(messages, "T34", "SelectLayerByLocation failed: {exc}".format(exc=exc))
            return

        # T35: GetCount post-select.
        try:
            n_sel = int(arcpy.management.GetCount(layer)[0])
            _log(messages, "T35", "GetCount(layer) after select = {n}".format(n=n_sel))
        except Exception as exc:
            _log_warn(messages, "T35", "post-select GetCount failed: {exc}".format(exc=exc))

    # ---- T13, T41 ----
    def _action_reset_tiny_board(self, parameters, messages):
        layer = parameters[P_LAYER].value
        if not layer:
            _log_err(messages, "T13", "no Game Layer")
            return

        ok, _ = _safe(messages, "T13", arcpy.management.DeleteRows, layer)
        if not ok:
            _log_warn(messages, "T13", "DeleteRows failed; trying TruncateTable")
            _safe(messages, "T13", arcpy.management.TruncateTable, layer)

        # Re-run the create flow to re-seed.
        self._action_create_tiny_board(parameters, messages)
