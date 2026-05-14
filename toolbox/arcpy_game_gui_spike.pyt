"""ArcPy Game GUI launch spike.

This toolbox proves a narrow UI handoff:

    ArcGIS Pro GP pane -> Python-launched Tkinter modal -> UICommand table

The spike intentionally does not run game rules or mutate board fields. It
records the user's chosen GUI command and selected layer context so a later
controller can consume durable command rows.
"""

from __future__ import annotations

import datetime as _datetime
import json
import os
import platform
import sys
import traceback
import uuid

import arcpy


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOOLBOX_LABEL = "ArcPy Game GUI Spike"
TOOLBOX_ALIAS = "arcpy_game_gui_spike"

# Match the existing feasibility spike default so the UICommand table lands
# beside GameBoard_Spike unless the user chooses another workspace.
DEFAULT_GDB_NAME = "arcpy_game_spike.gdb"
UI_COMMAND_TABLE = "UICommand"
GAME_SESSION_TABLE = "GameSession"

UI_PREVIEW_FIELD = "ui_preview_state"
LAST_COMMAND_FIELD = "last_command_id"
LOCK_PROBE_FIELD = "ui_lock_probe"

# Param indices. Keep in sync with getParameterInfo().
P_WORKSPACE = 0
P_LAYER = 1
P_SUPPORT_LAYER = 2
P_MODE = 3
P_ACTION = 4
P_RADIUS = 5
P_PLACEMENT = 6
P_OUTPUT = 7

ACTIONS = [
    "Ping GUI Environment",
    "Open Command Dialog",
    "Validate Scenario Inputs",
    "Open Novelty Control Panel",
    "Live Preview Update",
    "New Game / Load Game GUI",
    "Simulate Crash After Command Insert",
    "Simulate Crash During Apply",
    "Recover Pending Commands",
    "Apply Last Command Idempotency",
    "Dry Run Containment Mechanics",
    "Dry Run Bufferlands Mechanics",
    "Test Lock / Edit State",
    "Close Reopen Persistence Check",
    "Describe Last UI Command",
]

SCENARIO_MODES = [
    "Survey Sweeper",
    "Containment Commander",
    "Bufferlands Stretch",
    "Novelty Reopen",
]

SURVEY_COMMANDS = [
    "Reveal / Scout",
    "Flag / Mark",
    "Show Score",
]

CONTAINMENT_COMMANDS = [
    "Scout",
    "Treat / Clear",
    "Place Barrier",
    "Resolve Turn",
    "Show Score",
]

BUFFERLANDS_COMMANDS = [
    "Buffer Defense",
    "Spatial Join Harvest / Score",
    "Suppress Hotspot",
    "Show Score",
]

NOVELTY_REOPEN_COMMANDS = [
    "Play Buffer Card",
    "Play Spatial Join Card",
    "Place Guess Point",
    "Annex Adjacent District",
    "Show Dashboard",
]

TARGETED_COMMANDS = {
    "Reveal / Scout",
    "Flag / Mark",
    "Scout",
    "Treat / Clear",
    "Place Barrier",
    "Buffer Defense",
    "Suppress Hotspot",
    "Play Buffer Card",
    "Annex Adjacent District",
}

RADIUS_COMMANDS = {
    "Buffer Defense",
    "Suppress Hotspot",
    "Play Buffer Card",
}

SUPPORT_LAYER_COMMANDS = {
    "Spatial Join Harvest / Score",
    "Play Spatial Join Card",
}

BOARD_LAYER_COMMANDS = {
    "Resolve Turn",
    "Spatial Join Harvest / Score",
    "Play Spatial Join Card",
}

PLACEMENT_COMMANDS = {
    "Place Guess Point",
}

OPTIONAL_ASSET_FIELDS = {
    "asset_value",
    "critical_asset",
}

UI_COMMAND_FIELDS = [
    # name, type, alias, text length
    ("command_id", "TEXT", "Command ID", 64),
    ("created_utc", "DATE", "Created UTC", None),
    ("scenario_mode", "TEXT", "Scenario Mode", 64),
    ("command_name", "TEXT", "Command Name", 64),
    ("target_layer", "TEXT", "Target Layer", 255),
    ("target_cell_ids", "TEXT", "Target Cell IDs", 2048),
    ("selected_oid_count", "LONG", "Selected OID Count", None),
    ("status", "TEXT", "Status", 32),
    ("attempt_count", "LONG", "Attempt Count", None),
    ("started_utc", "DATE", "Started UTC", None),
    ("finished_utc", "DATE", "Finished UTC", None),
    ("game_id", "TEXT", "Game ID", 64),
    ("error_message", "TEXT", "Error Message", 1024),
    ("payload_json", "TEXT", "Payload JSON", 4000),
    ("message", "TEXT", "Message", 1024),
]

GAME_SESSION_FIELDS = [
    ("game_id", "TEXT", "Game ID", 64),
    ("created_utc", "DATE", "Created UTC", None),
    ("loaded_utc", "DATE", "Loaded UTC", None),
    ("scenario_mode", "TEXT", "Scenario Mode", 64),
    ("seed", "LONG", "Random Seed", None),
    ("status", "TEXT", "Status", 32),
    ("active", "SHORT", "Active", None),
    ("message", "TEXT", "Message", 1024),
    ("payload_json", "TEXT", "Payload JSON", 4000),
]


# ---------------------------------------------------------------------------
# Logging and low-level helpers
# ---------------------------------------------------------------------------

def _log(messages, tag, text):
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


def _clip(value, max_len):
    if value is None:
        return ""
    text = str(value)
    if max_len is None or len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[:max_len - 3] + "..."


def _value_text(value):
    if value is None:
        return ""
    return str(value)


def _now_utc():
    return _datetime.datetime.utcnow()


def _coerce_workspace_to_gdb(path):
    text = _value_text(path).strip()
    if not text:
        return ""
    if text.lower().endswith(".gdb"):
        return text
    return os.path.join(text, DEFAULT_GDB_NAME)


def resolve_workspace(workspace_param_value, messages):
    """Resolve a file geodatabase path for the UICommand table."""
    explicit = _coerce_workspace_to_gdb(workspace_param_value)
    if explicit:
        return explicit

    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        home = aprx.homeFolder
        if home:
            return os.path.join(home, "data", DEFAULT_GDB_NAME)
    except Exception as exc:
        _log_warn(messages, "WORKSPACE", "ArcGISProject('CURRENT') failed: {0}".format(exc))

    scratch = arcpy.env.scratchWorkspace or arcpy.env.scratchFolder
    if scratch:
        return _coerce_workspace_to_gdb(scratch)
    return os.path.join(os.path.expanduser("~"), DEFAULT_GDB_NAME)


def ensure_gdb(gdb_path, messages):
    folder = os.path.dirname(gdb_path)
    name = os.path.basename(gdb_path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
        _log(messages, "GDB", "created folder: {0}".format(folder))
    if not arcpy.Exists(gdb_path):
        arcpy.management.CreateFileGDB(folder or os.getcwd(), name)
        _log(messages, "GDB", "created gdb: {0}".format(gdb_path))
    else:
        _log(messages, "GDB", "gdb exists: {0}".format(gdb_path))
    return gdb_path


def add_field_if_missing(table, name, field_type, alias=None, length=None):
    existing = {field.name.lower() for field in arcpy.ListFields(table)}
    if name.lower() in existing:
        return False
    kwargs = {}
    if alias:
        kwargs["field_alias"] = alias
    if length is not None and field_type.upper() == "TEXT":
        kwargs["field_length"] = length
    arcpy.management.AddField(table, name, field_type, **kwargs)
    return True


def ensure_ui_command_table(gdb_path, messages):
    ensure_gdb(gdb_path, messages)
    table_path = os.path.join(gdb_path, UI_COMMAND_TABLE)
    if not arcpy.Exists(table_path):
        arcpy.management.CreateTable(gdb_path, UI_COMMAND_TABLE)
        _log(messages, "SCHEMA", "created table: {0}".format(table_path))
    else:
        _log(messages, "SCHEMA", "table exists: {0}".format(table_path))

    added = []
    for name, field_type, alias, length in UI_COMMAND_FIELDS:
        if add_field_if_missing(table_path, name, field_type, alias, length):
            added.append(name)
    if added:
        _log(messages, "SCHEMA", "added fields: {0}".format(", ".join(added)))
    else:
        _log(messages, "SCHEMA", "all UICommand fields already present")
    return table_path


def ensure_game_session_table(gdb_path, messages):
    ensure_gdb(gdb_path, messages)
    table_path = os.path.join(gdb_path, GAME_SESSION_TABLE)
    if not arcpy.Exists(table_path):
        arcpy.management.CreateTable(gdb_path, GAME_SESSION_TABLE)
        _log(messages, "SCHEMA", "created table: {0}".format(table_path))
    else:
        _log(messages, "SCHEMA", "table exists: {0}".format(table_path))

    added = []
    for name, field_type, alias, length in GAME_SESSION_FIELDS:
        if add_field_if_missing(table_path, name, field_type, alias, length):
            added.append(name)
    if added:
        _log(messages, "SCHEMA", "added GameSession fields: {0}".format(", ".join(added)))
    else:
        _log(messages, "SCHEMA", "all GameSession fields already present")
    return table_path


def ensure_layer_text_field(layer, field_name, alias, length, messages):
    if not layer:
        return False
    try:
        existing = {field.name.lower() for field in arcpy.ListFields(layer)}
        if field_name.lower() in existing:
            return False
        arcpy.management.AddField(layer, field_name, "TEXT", field_alias=alias, field_length=length)
        _log(messages, "SCHEMA", "added layer field: {0}".format(field_name))
        return True
    except Exception as exc:
        _log_warn(messages, "SCHEMA", "could not add layer field {0}: {1}".format(field_name, exc))
        raise


def ensure_layer_short_field(layer, field_name, alias, messages):
    if not layer:
        return False
    try:
        existing = {field.name.lower() for field in arcpy.ListFields(layer)}
        if field_name.lower() in existing:
            return False
        arcpy.management.AddField(layer, field_name, "SHORT", field_alias=alias)
        _log(messages, "SCHEMA", "added layer field: {0}".format(field_name))
        return True
    except Exception as exc:
        _log_warn(messages, "SCHEMA", "could not add layer field {0}: {1}".format(field_name, exc))
        raise


def normalize_fidset(fidset):
    """Normalize Describe(...).FIDSet variants into sorted unique OIDs."""
    if fidset is None:
        return []
    if isinstance(fidset, str):
        text = fidset.strip()
        if not text:
            return []
        out = []
        for part in text.replace(",", ";").split(";"):
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
        for value in fidset:
            try:
                out.append(int(value))
            except (TypeError, ValueError):
                continue
        return sorted(set(out))
    try:
        return [int(fidset)]
    except (TypeError, ValueError):
        return []


def _layer_display_name(layer, layer_value_text):
    if layer is None:
        return ""
    name = getattr(layer, "name", None)
    if name:
        return str(name)
    if layer_value_text:
        return str(layer_value_text)
    return str(layer)


def commands_for_mode(scenario_mode):
    if scenario_mode == "Containment Commander":
        return list(CONTAINMENT_COMMANDS)
    if scenario_mode == "Bufferlands Stretch":
        return list(BUFFERLANDS_COMMANDS)
    if scenario_mode == "Novelty Reopen":
        return list(NOVELTY_REOPEN_COMMANDS)
    return list(SURVEY_COMMANDS)


def collect_layer_summary(layer, layer_value_text, messages, tag):
    """Return enough support-layer context to validate planned phase features."""
    context = {
        "layer_name": _layer_display_name(layer, layer_value_text),
        "provided": bool(layer),
        "count": None,
        "shape_type": "",
        "fields": [],
        "field_names_lower": [],
    }
    if not layer:
        _log(messages, tag, "no layer supplied")
        return context

    try:
        desc = arcpy.Describe(layer)
        context["shape_type"] = getattr(desc, "shapeType", "") or ""
    except Exception as exc:
        _log_warn(messages, tag, "Describe failed: {0}".format(exc))

    try:
        fields = [field.name for field in arcpy.ListFields(layer)]
        context["fields"] = fields
        context["field_names_lower"] = [name.lower() for name in fields]
    except Exception as exc:
        _log_warn(messages, tag, "ListFields failed: {0}".format(exc))

    try:
        context["count"] = int(arcpy.management.GetCount(layer)[0])
        _log(messages, tag, "GetCount(layer) = {0}".format(context["count"]))
    except Exception as exc:
        _log_warn(messages, tag, "GetCount failed: {0}".format(exc))

    return context


def collect_placement_context(placement_layer, placement_value_text, messages):
    """Return enough drawn-placement context to validate Feature Set feasibility."""
    context = {
        "provided": bool(placement_layer or placement_value_text),
        "value_text": _value_text(placement_value_text),
        "count": None,
        "shape_type": "",
        "fields": [],
    }
    source = placement_layer or placement_value_text
    if not source:
        _log(messages, "PLACEMENT", "no placement feature supplied")
        return context

    try:
        desc = arcpy.Describe(source)
        context["shape_type"] = getattr(desc, "shapeType", "") or ""
    except Exception as exc:
        _log_warn(messages, "PLACEMENT", "Describe failed: {0}".format(exc))

    try:
        context["fields"] = [field.name for field in arcpy.ListFields(source)]
    except Exception as exc:
        _log_warn(messages, "PLACEMENT", "ListFields failed: {0}".format(exc))

    try:
        context["count"] = int(arcpy.management.GetCount(source)[0])
        _log(messages, "PLACEMENT", "GetCount(placement) = {0}".format(context["count"]))
    except Exception as exc:
        _log_warn(messages, "PLACEMENT", "GetCount failed: {0}".format(exc))

    return context


def radius_context(radius_value):
    context = {
        "value": None,
        "provided": radius_value is not None,
        "valid": False,
    }
    if radius_value is None:
        return context
    try:
        value = float(radius_value)
    except (TypeError, ValueError):
        return context
    context["value"] = value
    context["valid"] = value > 0
    return context


def validate_planned_command(command_name, selection_context, support_context, radius_info, placement_context=None):
    """Validate the inputs needed by the future scenario feature, without executing it."""
    errors = []
    warnings = []
    checks = []
    placement_context = placement_context or {}

    selected_count = len(selection_context.get("selected_oids") or [])
    game_layer_name = selection_context.get("target_layer") or ""

    if command_name in TARGETED_COMMANDS:
        checks.append("selected game cells")
        if selected_count <= 0:
            errors.append("select at least one Game Layer cell")

    if command_name in BOARD_LAYER_COMMANDS:
        checks.append("game layer")
        if not game_layer_name:
            errors.append("provide a Game Layer")

    if command_name in RADIUS_COMMANDS:
        checks.append("positive radius")
        if not radius_info.get("valid"):
            errors.append("provide Amount / Radius greater than 0")

    if command_name in SUPPORT_LAYER_COMMANDS:
        checks.append("support layer")
        if not support_context.get("provided"):
            errors.append("provide a Support Layer such as Assets")
        else:
            field_names = set(support_context.get("field_names_lower") or [])
            missing_asset_fields = sorted(OPTIONAL_ASSET_FIELDS - field_names)
            if missing_asset_fields:
                warnings.append(
                    "support layer lacks planned scoring field(s): {0}".format(
                        ", ".join(missing_asset_fields)
                    )
                )

    if command_name in PLACEMENT_COMMANDS:
        checks.append("placement feature")
        if not placement_context.get("provided"):
            errors.append("provide a Placement Feature or drawn Feature Set")
        elif placement_context.get("count") in (None, 0):
            errors.append("draw or provide at least one placement feature")

    if command_name == "Place Barrier" and selected_count > 2:
        warnings.append("planned first Containment version expects up to 2 barrier cells")

    if command_name == "Suppress Hotspot":
        warnings.append("planned as optional stretch; this spike only records command readiness")

    if command_name in NOVELTY_REOPEN_COMMANDS:
        warnings.append("novelty reopen command records readiness only; no final game rule is applied")

    ready = not errors
    return {
        "command_name": command_name,
        "ready": ready,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def collect_selection_context(layer, layer_value_text, messages):
    """Read selected OIDs and cell IDs without treating an unselected layer as selected."""
    context = {
        "target_layer": _layer_display_name(layer, layer_value_text),
        "oid_field": "",
        "selected_oids": [],
        "target_cell_ids": [],
        "selected_rows_read": 0,
        "cell_id_field_present": False,
        "selection_source": "none",
    }
    if not layer:
        _log(messages, "SELECTION", "no Game Layer parameter supplied")
        return context

    oid_field = ""
    catalog_path = None
    selected_oids = []

    try:
        da_desc = arcpy.da.Describe(layer)
        oid_field = da_desc.get("OIDFieldName") or ""
        catalog_path = da_desc.get("catalogPath")
        selected_oids = normalize_fidset(da_desc.get("FIDSet"))
        if selected_oids:
            context["selection_source"] = "da.Describe.FIDSet"
        _log(messages, "SELECTION", "da.Describe FIDSet -> {0!r}".format(selected_oids))
    except Exception as exc:
        _log_warn(messages, "SELECTION", "da.Describe failed: {0}".format(exc))

    if not oid_field or not selected_oids:
        try:
            desc = arcpy.Describe(layer)
            oid_field = oid_field or getattr(desc, "OIDFieldName", "")
            catalog_path = catalog_path or getattr(desc, "catalogPath", None)
            classic_oids = normalize_fidset(getattr(desc, "FIDSet", None))
            if classic_oids and not selected_oids:
                selected_oids = classic_oids
                context["selection_source"] = "Describe.FIDSet"
            _log(messages, "SELECTION", "classic Describe FIDSet -> {0!r}".format(classic_oids))
        except Exception as exc:
            _log_warn(messages, "SELECTION", "Describe failed: {0}".format(exc))

    context["oid_field"] = oid_field
    context["selected_oids"] = list(selected_oids)
    if not selected_oids:
        _log(messages, "SELECTION", "no selected OIDs found; cursor read skipped")
        return context
    if not oid_field:
        _log_warn(messages, "SELECTION", "selection exists, but OID field could not be resolved")
        return context

    try:
        field_lookup = {field.name.lower(): field.name for field in arcpy.ListFields(layer)}
    except Exception as exc:
        _log_warn(messages, "SELECTION", "ListFields failed: {0}".format(exc))
        field_lookup = {}

    cell_id_field = field_lookup.get("cell_id")
    has_cell_id = cell_id_field is not None
    context["cell_id_field_present"] = has_cell_id
    fields = [oid_field]
    if has_cell_id:
        fields.append(cell_id_field)

    rows = []
    try:
        with arcpy.da.SearchCursor(layer, fields) as cursor:
            for row in cursor:
                rows.append(row)
        _log(messages, "SELECTION", "SearchCursor(layer) read {0} selected row(s)".format(len(rows)))
    except Exception as exc:
        _log_warn(messages, "SELECTION", "SearchCursor(layer) failed: {0}".format(exc))
        rows = []

    if not rows and catalog_path:
        try:
            where = "{0} IN ({1})".format(
                arcpy.AddFieldDelimiters(catalog_path, oid_field),
                ",".join(str(oid) for oid in selected_oids),
            )
            with arcpy.da.SearchCursor(catalog_path, fields, where_clause=where) as cursor:
                rows = list(cursor)
            _log(messages, "SELECTION", "fallback OID IN cursor read {0} row(s)".format(len(rows)))
        except Exception as exc:
            _log_warn(messages, "SELECTION", "fallback OID IN cursor failed: {0}".format(exc))

    selected_oid_set = set(selected_oids)
    cursor_oids = []
    cell_ids = []
    for row in rows:
        try:
            oid = int(row[0])
        except (TypeError, ValueError):
            continue
        if selected_oid_set and oid not in selected_oid_set:
            continue
        cursor_oids.append(oid)
        if has_cell_id and len(row) > 1 and row[1]:
            cell_ids.append(str(row[1]))

    if cursor_oids:
        context["selected_oids"] = sorted(set(cursor_oids))
    context["target_cell_ids"] = sorted(set(cell_ids))
    context["selected_rows_read"] = len(rows)
    return context


def open_tk_command_dialog(context, scenario_mode, support_context, radius_info):
    """Open a modal Tkinter command chooser and return a small result dict."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as exc:
        raise RuntimeError("tkinter is not available in this ArcGIS Pro Python environment: {0}".format(exc))

    selected_cells = context.get("target_cell_ids") or []
    selected_oids = context.get("selected_oids") or []
    layer_name = context.get("target_layer") or "(none)"
    support_layer_name = support_context.get("layer_name") or "(none)"
    radius_value = radius_info.get("value")
    if radius_value is None:
        radius_text = "(not set)"
    else:
        radius_text = str(radius_value)
    if selected_cells:
        selection_text = ", ".join(selected_cells[:12])
        if len(selected_cells) > 12:
            selection_text += " ... ({0} total)".format(len(selected_cells))
    elif selected_oids:
        selection_text = "{0} selected OID(s), no cell_id field".format(len(selected_oids))
    else:
        selection_text = "No selected targets"

    result = {
        "command_name": "Cancel",
        "status": "cancelled",
    }

    root = tk.Tk()
    root.title("ArcPy Game Command")
    root.resizable(False, False)

    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    pad = {"padx": 12, "pady": 6}
    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(1, weight=1)

    title = ttk.Label(frame, text="Choose Game Command", font=("Segoe UI", 12, "bold"))
    title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    labels = [
        ("Scenario", scenario_mode or ""),
        ("Layer", layer_name),
        ("Selection", selection_text),
        ("Support Layer", support_layer_name),
        ("Amount / Radius", radius_text),
    ]
    for row_idx, (name, value) in enumerate(labels, start=1):
        ttk.Label(frame, text=name + ":").grid(row=row_idx, column=0, sticky="nw", **pad)
        ttk.Label(frame, text=value, wraplength=420).grid(row=row_idx, column=1, sticky="w", **pad)

    if not selected_oids:
        note = "Selected-cell features will record an error row until cells are selected on the map."
        ttk.Label(frame, text=note, wraplength=480, foreground="#8a5a00").grid(
            row=6, column=0, columnspan=2, sticky="w", padx=12, pady=(6, 10)
        )

    button_frame = ttk.Frame(frame)
    button_frame.grid(row=7, column=0, columnspan=2, sticky="e", pady=(10, 0))

    def choose(command_name, status="created"):
        result["command_name"] = command_name
        result["status"] = status
        try:
            root.grab_release()
        except Exception:
            pass
        root.destroy()

    for command in commands_for_mode(scenario_mode):
        ttk.Button(
            button_frame,
            text=command,
            command=lambda value=command: choose(value, "created"),
        ).pack(side="left", padx=(0, 6))
    ttk.Button(
        button_frame,
        text="Cancel",
        command=lambda: choose("Cancel", "cancelled"),
    ).pack(side="left")

    root.protocol("WM_DELETE_WINDOW", lambda: choose("Cancel", "cancelled"))
    root.update_idletasks()

    width = root.winfo_width()
    height = root.winfo_height()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width - width) / 2)
    y = int((screen_height - height) / 3)
    root.geometry("+{0}+{1}".format(max(x, 0), max(y, 0)))

    root.lift()
    root.focus_force()
    root.grab_set()
    root.wait_window()
    return result


def open_novelty_control_panel(context, support_context, placement_context, radius_info):
    """Open a compact control panel for the GUI-era concept reopen."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as exc:
        raise RuntimeError("tkinter is not available in this ArcGIS Pro Python environment: {0}".format(exc))

    selected_cells = context.get("target_cell_ids") or []
    selected_oids = context.get("selected_oids") or []
    support_name = support_context.get("layer_name") or "(none)"
    placement_count = placement_context.get("count")
    radius_value = radius_info.get("value")
    radius_text = "(not set)" if radius_value is None else str(radius_value)
    if selected_cells:
        selected_text = "{0} cell(s): {1}".format(len(selected_cells), ", ".join(selected_cells[:8]))
    elif selected_oids:
        selected_text = "{0} selected OID(s)".format(len(selected_oids))
    else:
        selected_text = "No selected targets"
    if placement_count is None:
        placement_text = "not supplied" if not placement_context.get("provided") else "supplied, count unknown"
    else:
        placement_text = "{0} feature(s), {1}".format(placement_count, placement_context.get("shape_type") or "unknown shape")

    result = {
        "command_name": "Cancel",
        "status": "cancelled",
    }

    root = tk.Tk()
    root.title("ArcPy Game Novelty Reopen")
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(frame, text="Novelty Reopen Control Panel", font=("Segoe UI", 12, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
    )

    metrics = [
        ("Targets", selected_text),
        ("Support layer", support_name),
        ("Placement", placement_text),
        ("Amount / Radius", radius_text),
        ("Dashboard", "AP=2, turn=spike, cooldowns=placeholder"),
    ]
    for row_idx, (name, value) in enumerate(metrics, start=1):
        ttk.Label(frame, text=name + ":").grid(row=row_idx, column=0, sticky="nw", padx=8, pady=4)
        ttk.Label(frame, text=value, wraplength=520).grid(row=row_idx, column=1, columnspan=2, sticky="w", padx=8, pady=4)

    ttk.Separator(frame).grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 8))
    ttk.Label(frame, text="Reopened concept action").grid(row=7, column=0, sticky="w", padx=8)
    ttk.Label(frame, text="Concept").grid(row=7, column=1, sticky="w", padx=8)
    ttk.Label(frame, text="Required context").grid(row=7, column=2, sticky="w", padx=8)

    def choose(command_name, status="created"):
        result["command_name"] = command_name
        result["status"] = status
        try:
            root.grab_release()
        except Exception:
            pass
        root.destroy()

    rows = [
        ("Play Buffer Card", "Spatial Tactics / Bufferlands", "selected target + positive radius"),
        ("Play Spatial Join Card", "Spatial Tactics scoring", "game layer + support layer"),
        ("Place Guess Point", "GeoGuessr / placement flow", "drawn Placement Feature"),
        ("Annex Adjacent District", "Census tactics", "selected target"),
        ("Show Dashboard", "GUI viability", "none"),
    ]
    for offset, (command_name, concept, requirements) in enumerate(rows, start=8):
        ttk.Button(
            frame,
            text=command_name,
            command=lambda value=command_name: choose(value, "created"),
        ).grid(row=offset, column=0, sticky="ew", padx=8, pady=3)
        ttk.Label(frame, text=concept, wraplength=180).grid(row=offset, column=1, sticky="w", padx=8, pady=3)
        ttk.Label(frame, text=requirements, wraplength=220).grid(row=offset, column=2, sticky="w", padx=8, pady=3)

    buttons = ttk.Frame(frame)
    buttons.grid(row=13, column=0, columnspan=3, sticky="e", pady=(12, 0))

    ttk.Button(buttons, text="Cancel", command=lambda: choose("Cancel", "cancelled")).pack(side="left")
    root.protocol("WM_DELETE_WINDOW", lambda: choose("Cancel", "cancelled"))
    root.update_idletasks()
    root.grab_set()
    root.wait_window()
    return result


def insert_ui_command(table_path, command):
    fields = [
        "command_id",
        "created_utc",
        "scenario_mode",
        "command_name",
        "target_layer",
        "target_cell_ids",
        "selected_oid_count",
        "status",
        "attempt_count",
        "started_utc",
        "finished_utc",
        "game_id",
        "error_message",
        "payload_json",
        "message",
    ]
    row = [
        command["command_id"],
        command["created_utc"],
        _clip(command.get("scenario_mode"), 64),
        _clip(command.get("command_name"), 64),
        _clip(command.get("target_layer"), 255),
        _clip(",".join(command.get("target_cell_ids") or []), 2048),
        int(command.get("selected_oid_count") or 0),
        _clip(command.get("status"), 32),
        int(command.get("attempt_count") or 0),
        command.get("started_utc"),
        command.get("finished_utc"),
        _clip(command.get("game_id"), 64),
        _clip(command.get("error_message"), 1024),
        _clip(command.get("payload_json"), 4000),
        _clip(command.get("message"), 1024),
    ]
    with arcpy.da.InsertCursor(table_path, fields) as cursor:
        cursor.insertRow(row)


def update_ui_command_status(
    table_path,
    command_id,
    status,
    message=None,
    error_message=None,
    game_id=None,
    started_utc=None,
    finished_utc=None,
    increment_attempt=False,
):
    fields = [
        "command_id",
        "status",
        "message",
        "error_message",
        "game_id",
        "started_utc",
        "finished_utc",
        "attempt_count",
    ]
    updated = 0
    with arcpy.da.UpdateCursor(table_path, fields) as cursor:
        for row in cursor:
            if row[0] != command_id:
                continue
            row[1] = _clip(status, 32)
            if message is not None:
                row[2] = _clip(message, 1024)
            if error_message is not None:
                row[3] = _clip(error_message, 1024)
            if game_id is not None:
                row[4] = _clip(game_id, 64)
            if started_utc is not None:
                row[5] = started_utc
            if finished_utc is not None:
                row[6] = finished_utc
            if increment_attempt:
                row[7] = (row[7] or 0) + 1
            cursor.updateRow(row)
            updated += 1
    return updated


def build_command_payload(
    gdb_path,
    scenario_mode,
    context,
    support_context,
    radius_info,
    dialog_result,
    validation=None,
    placement_context=None,
):
    command_name = dialog_result.get("command_name") or "Cancel"
    status = dialog_result.get("status") or "cancelled"
    selected_oids = context.get("selected_oids") or []
    target_cell_ids = context.get("target_cell_ids") or []

    if status == "cancelled":
        message = "GUI dialog cancelled; no gameplay command requested."
    else:
        if validation is None:
            validation = validate_planned_command(command_name, context, support_context, radius_info, placement_context)
        if validation.get("errors"):
            status = "error"
            message = "{0} blocked: {1}.".format(
                command_name,
                "; ".join(validation["errors"]),
            )
        else:
            if target_cell_ids:
                target_text = ",".join(target_cell_ids)
            elif selected_oids:
                target_text = "{0} OID(s)".format(len(selected_oids))
            else:
                target_text = "current scenario state"
            if validation.get("warnings"):
                message = "Recorded GUI command {0!r} for {1}; warning: {2}.".format(
                    command_name,
                    target_text,
                    "; ".join(validation["warnings"]),
                )
            else:
                message = "Recorded GUI command {0!r} for {1}.".format(command_name, target_text)

    created_utc = _now_utc()
    command_id = str(uuid.uuid4())
    payload = {
        "schema_version": 1,
        "command_id": command_id,
        "created_utc": created_utc.isoformat(timespec="seconds") + "Z",
        "workspace": gdb_path,
        "scenario_mode": scenario_mode,
        "source": "tkinter_modal",
        "command_name": command_name,
        "status": status,
        "target_layer": context.get("target_layer") or "",
        "target_cell_ids": target_cell_ids,
        "selected_oids": selected_oids,
        "selected_oid_count": len(selected_oids),
        "support_layer": support_context,
        "radius": radius_info,
        "placement_feature": placement_context or {},
        "feature_validation": validation or {},
        "selected_rows_read": context.get("selected_rows_read") or 0,
        "cell_id_field_present": bool(context.get("cell_id_field_present")),
        "selection_source": context.get("selection_source") or "none",
        "message": message,
    }
    return {
        "command_id": command_id,
        "created_utc": created_utc,
        "scenario_mode": scenario_mode,
        "command_name": command_name,
        "target_layer": context.get("target_layer") or "",
        "target_cell_ids": target_cell_ids,
        "selected_oid_count": len(selected_oids),
        "status": status,
        "payload_json": json.dumps(payload, sort_keys=True),
        "message": message,
        "attempt_count": 0,
        "started_utc": None,
        "finished_utc": None,
        "game_id": "",
        "error_message": "",
    }


def read_last_ui_command(table_path):
    desc = arcpy.Describe(table_path)
    oid_field = getattr(desc, "OIDFieldName", None)
    if not oid_field:
        raise RuntimeError("Could not resolve OID field for {0}".format(table_path))

    fields = [
        oid_field,
        "command_id",
        "created_utc",
        "scenario_mode",
        "command_name",
        "target_layer",
        "target_cell_ids",
        "selected_oid_count",
        "status",
        "attempt_count",
        "game_id",
        "error_message",
        "message",
    ]
    last = None
    with arcpy.da.SearchCursor(table_path, fields) as cursor:
        for row in cursor:
            if last is None or row[0] > last[0]:
                last = row
    if last is None:
        return None

    return dict(zip(fields, last))


def insert_game_session(table_path, scenario_mode, seed, message):
    game_id = str(uuid.uuid4())
    now = _now_utc()
    payload = {
        "schema_version": 1,
        "game_id": game_id,
        "created_utc": now.isoformat(timespec="seconds") + "Z",
        "scenario_mode": scenario_mode,
        "seed": seed,
        "source": "tkinter_modal",
    }
    fields = [
        "game_id",
        "created_utc",
        "loaded_utc",
        "scenario_mode",
        "seed",
        "status",
        "active",
        "message",
        "payload_json",
    ]
    row = [
        game_id,
        now,
        now,
        _clip(scenario_mode, 64),
        int(seed),
        "active",
        1,
        _clip(message, 1024),
        _clip(json.dumps(payload, sort_keys=True), 4000),
    ]
    with arcpy.da.InsertCursor(table_path, fields) as cursor:
        cursor.insertRow(row)
    return game_id


def read_latest_game_session(table_path):
    desc = arcpy.Describe(table_path)
    oid_field = getattr(desc, "OIDFieldName", None)
    if not oid_field:
        raise RuntimeError("Could not resolve OID field for {0}".format(table_path))
    fields = [
        oid_field,
        "game_id",
        "created_utc",
        "loaded_utc",
        "scenario_mode",
        "seed",
        "status",
        "active",
        "message",
    ]
    latest = None
    with arcpy.da.SearchCursor(table_path, fields) as cursor:
        for row in cursor:
            if latest is None or row[0] > latest[0]:
                latest = row
    if latest is None:
        return None
    return dict(zip(fields, latest))


def mark_game_session_loaded(table_path, game_id, message):
    fields = ["game_id", "loaded_utc", "active", "message", "status"]
    updated = 0
    now = _now_utc()
    with arcpy.da.UpdateCursor(table_path, fields) as cursor:
        for row in cursor:
            row[2] = 1 if row[0] == game_id else 0
            if row[0] == game_id:
                row[1] = now
                row[3] = _clip(message, 1024)
                row[4] = "active"
                updated += 1
            cursor.updateRow(row)
    return updated


def insert_validation_command(table_path, gdb_path, scenario_mode, command_name, status, message, payload):
    created_utc = _now_utc()
    command_id = str(uuid.uuid4())
    full_payload = {
        "schema_version": 1,
        "command_id": command_id,
        "created_utc": created_utc.isoformat(timespec="seconds") + "Z",
        "workspace": gdb_path,
        "scenario_mode": scenario_mode,
        "source": "validation_action",
        "command_name": command_name,
        "status": status,
        "message": message,
        "details": payload,
    }
    command = {
        "command_id": command_id,
        "created_utc": created_utc,
        "scenario_mode": scenario_mode,
        "command_name": command_name,
        "target_layer": payload.get("target_layer", ""),
        "target_cell_ids": payload.get("target_cell_ids", []),
        "selected_oid_count": payload.get("selected_oid_count", 0),
        "status": status,
        "attempt_count": payload.get("attempt_count", 0),
        "started_utc": payload.get("started_utc"),
        "finished_utc": payload.get("finished_utc"),
        "game_id": payload.get("game_id", ""),
        "error_message": payload.get("error_message", ""),
        "payload_json": json.dumps(full_payload, sort_keys=True),
        "message": message,
    }
    insert_ui_command(table_path, command)
    return command


def update_selected_layer_field(layer, field_name, value, messages, tag):
    if not layer:
        return 0
    updated = 0
    try:
        with arcpy.da.UpdateCursor(layer, [field_name]) as cursor:
            for row in cursor:
                row[0] = value
                cursor.updateRow(row)
                updated += 1
        _log(messages, tag, "updated {0} selected row(s) field {1}".format(updated, field_name))
    except Exception as exc:
        _log_warn(messages, tag, "UpdateCursor failed for {0}: {1}".format(field_name, exc))
        raise
    return updated


def refresh_layer(layer, layer_value_text, messages, tag):
    layer_name = _layer_display_name(layer, layer_value_text)
    if not layer_name:
        _log_warn(messages, tag, "no layer name available for RefreshLayer")
        return False
    try:
        arcpy.RefreshLayer(layer_name)
        _log(messages, tag, "RefreshLayer({0!r}) returned without error".format(layer_name))
        return True
    except AttributeError:
        _log_warn(messages, tag, "arcpy.RefreshLayer is unavailable in this Pro version")
    except Exception as exc:
        _log_warn(messages, tag, "RefreshLayer failed: {0}".format(exc))
    return False


def open_session_dialog(existing_session, scenario_mode):
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as exc:
        raise RuntimeError("tkinter is not available in this ArcGIS Pro Python environment: {0}".format(exc))

    result = {"choice": "Cancel", "status": "cancelled"}
    root = tk.Tk()
    root.title("ArcPy Game Session")
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(frame, text="Game Session", font=("Segoe UI", 12, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
    )
    latest = "(none)"
    if existing_session:
        latest = "{0} / {1}".format(existing_session.get("game_id"), existing_session.get("scenario_mode"))
    ttk.Label(frame, text="Scenario:").grid(row=1, column=0, sticky="w", padx=12, pady=6)
    ttk.Label(frame, text=scenario_mode).grid(row=1, column=1, sticky="w", padx=12, pady=6)
    ttk.Label(frame, text="Latest:").grid(row=2, column=0, sticky="w", padx=12, pady=6)
    ttk.Label(frame, text=latest, wraplength=420).grid(row=2, column=1, sticky="w", padx=12, pady=6)

    buttons = ttk.Frame(frame)
    buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))

    def choose(value, status="created"):
        result["choice"] = value
        result["status"] = status
        try:
            root.grab_release()
        except Exception:
            pass
        root.destroy()

    ttk.Button(buttons, text="New Game", command=lambda: choose("New Game From GUI")).pack(side="left", padx=(0, 6))
    ttk.Button(buttons, text="Load Latest", command=lambda: choose("Load Game From GUI")).pack(side="left", padx=(0, 6))
    ttk.Button(buttons, text="Cancel", command=lambda: choose("Cancel", "cancelled")).pack(side="left")
    root.protocol("WM_DELETE_WINDOW", lambda: choose("Cancel", "cancelled"))
    root.update_idletasks()
    root.grab_set()
    root.wait_window()
    return result


def open_live_preview_dialog(layer, layer_text, context, messages):
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as exc:
        raise RuntimeError("tkinter is not available in this ArcGIS Pro Python environment: {0}".format(exc))

    steps = []
    result = {"status": "cancelled", "steps": steps}
    root = tk.Tk()
    root.title("ArcPy Game Live Preview")
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(frame, text="Live Preview Update", font=("Segoe UI", 12, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
    )
    selected = context.get("target_cell_ids") or context.get("selected_oids") or []
    ttk.Label(frame, text="Selected targets: {0}".format(len(selected))).grid(
        row=1, column=0, columnspan=3, sticky="w", padx=12, pady=6
    )
    status_var = tk.StringVar(value="Click a preview button, then inspect the map before closing.")
    ttk.Label(frame, textvariable=status_var, wraplength=520).grid(
        row=2, column=0, columnspan=3, sticky="w", padx=12, pady=6
    )

    def preview(value):
        try:
            updated = update_selected_layer_field(layer, UI_PREVIEW_FIELD, value, messages, "LIVE")
            refreshed = refresh_layer(layer, layer_text, messages, "LIVE")
            step = {"value": value, "updated": updated, "refresh_called": refreshed}
            steps.append(step)
            result["status"] = "created"
            status_var.set("Preview {0}: updated {1} row(s); refresh_called={2}".format(value, updated, refreshed))
        except Exception as exc:
            step = {"value": value, "error": str(exc)}
            steps.append(step)
            result["status"] = "error"
            status_var.set("Preview failed: {0}".format(exc))

    def close():
        try:
            root.grab_release()
        except Exception:
            pass
        root.destroy()

    ttk.Button(frame, text="Preview A", command=lambda: preview("preview_a")).grid(row=3, column=0, padx=6, pady=12)
    ttk.Button(frame, text="Preview B", command=lambda: preview("preview_b")).grid(row=3, column=1, padx=6, pady=12)
    ttk.Button(frame, text="Close", command=close).grid(row=3, column=2, padx=6, pady=12)
    root.protocol("WM_DELETE_WINDOW", close)
    root.update_idletasks()
    root.grab_set()
    root.wait_window()
    return result


# ---------------------------------------------------------------------------
# Toolbox
# ---------------------------------------------------------------------------

class Toolbox(object):
    def __init__(self):
        self.label = TOOLBOX_LABEL
        self.alias = TOOLBOX_ALIAS
        self.tools = [GUICommandSpike]


class GUICommandSpike(object):
    """Single-tool dispatcher for the Tkinter GUI command spike."""

    def __init__(self):
        self.label = "GUI Command Spike"
        self.description = (
            "Design spike for opening a short-lived Python GUI from the "
            "ArcGIS Pro Geoprocessing pane and recording a UICommand row."
        )
        self.canRunInBackground = False

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

        p_support_layer = arcpy.Parameter(
            displayName="Support Layer (Assets / RiskSources optional)",
            name="support_layer",
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
        p_mode.filter.list = list(SCENARIO_MODES)
        p_mode.value = "Survey Sweeper"

        p_action = arcpy.Parameter(
            displayName="Action",
            name="action",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p_action.filter.type = "ValueList"
        p_action.filter.list = list(ACTIONS)
        p_action.value = "Ping GUI Environment"

        p_radius = arcpy.Parameter(
            displayName="Amount / Radius",
            name="amount_radius",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_radius.value = 150.0

        p_placement = arcpy.Parameter(
            displayName="Placement Feature (optional drawn input)",
            name="placement_feature",
            datatype="GPFeatureRecordSetLayer",
            parameterType="Optional",
            direction="Input",
        )

        p_output = arcpy.Parameter(
            displayName="Output UI Command Table",
            name="output_ui_command_table",
            datatype="GPTableView",
            parameterType="Derived",
            direction="Output",
        )

        return [
            p_workspace,
            p_layer,
            p_support_layer,
            p_mode,
            p_action,
            p_radius,
            p_placement,
            p_output,
        ]

    def updateParameters(self, parameters):
        action_param = parameters[P_ACTION]
        action_param.filter.list = list(ACTIONS)
        if action_param.valueAsText not in ACTIONS:
            action_param.value = ACTIONS[0]

        mode = parameters[P_MODE].valueAsText
        action = action_param.valueAsText
        scenario_validation = action in (
            "Open Command Dialog",
            "Validate Scenario Inputs",
            "Open Novelty Control Panel",
            "Dry Run Bufferlands Mechanics",
        )
        bufferlands_context = action == "Dry Run Bufferlands Mechanics" or (
            scenario_validation and mode == "Bufferlands Stretch"
        )
        novelty_context = action == "Open Novelty Control Panel" or (
            scenario_validation and mode == "Novelty Reopen"
        )
        parameters[P_RADIUS].enabled = bufferlands_context or novelty_context
        parameters[P_SUPPORT_LAYER].enabled = bufferlands_context or novelty_context
        parameters[P_PLACEMENT].enabled = novelty_context
        return

    def updateMessages(self, parameters):
        action = parameters[P_ACTION].valueAsText
        mode = parameters[P_MODE].valueAsText
        layer_param = parameters[P_LAYER]
        support_param = parameters[P_SUPPORT_LAYER]
        radius_param = parameters[P_RADIUS]
        scenario_validation = action in (
            "Open Command Dialog",
            "Validate Scenario Inputs",
            "Open Novelty Control Panel",
            "Live Preview Update",
            "Apply Last Command Idempotency",
            "Dry Run Containment Mechanics",
            "Dry Run Bufferlands Mechanics",
            "Test Lock / Edit State",
        )

        if scenario_validation and not layer_param.value:
            layer_param.setWarningMessage(
                "Layer is optional for Show Score, but selected-cell phase features will be blocked without Game Layer selections."
            )
        else:
            layer_param.clearMessage()

        if action == "Dry Run Bufferlands Mechanics" and not support_param.value:
            support_param.setWarningMessage(
                "Spatial Join Harvest / Score will be blocked without an Assets or RiskSources support layer."
            )
        elif (action == "Open Novelty Control Panel" or mode == "Novelty Reopen") and not support_param.value:
            support_param.setWarningMessage(
                "Spatial Join card readiness will be blocked without a Support Layer."
            )
        else:
            support_param.clearMessage()

        radius_context_needed = action == "Dry Run Bufferlands Mechanics" or action == "Open Novelty Control Panel" or mode == "Novelty Reopen"
        if radius_context_needed and radius_param.value is not None:
            try:
                radius = float(radius_param.value)
            except (TypeError, ValueError):
                radius = None
            if radius is not None and radius <= 0:
                radius_param.setErrorMessage("Amount / Radius must be greater than 0 for buffer/card features.")
            else:
                radius_param.clearMessage()
        else:
            radius_param.clearMessage()
        return

    def execute(self, parameters, messages):
        action = parameters[P_ACTION].valueAsText or "Ping GUI Environment"
        _log(messages, "DISPATCH", "action = {0!r}".format(action))

        handlers = {
            "Ping GUI Environment": self._action_ping_gui_environment,
            "Open Command Dialog": self._action_open_command_dialog,
            "Validate Scenario Inputs": self._action_validate_scenario_inputs,
            "Open Novelty Control Panel": self._action_open_novelty_control_panel,
            "Live Preview Update": self._action_live_preview_update,
            "New Game / Load Game GUI": self._action_new_load_game_gui,
            "Simulate Crash After Command Insert": self._action_simulate_crash_after_command_insert,
            "Simulate Crash During Apply": self._action_simulate_crash_during_apply,
            "Recover Pending Commands": self._action_recover_pending_commands,
            "Apply Last Command Idempotency": self._action_apply_last_command_idempotency,
            "Dry Run Containment Mechanics": self._action_dry_run_containment_mechanics,
            "Dry Run Bufferlands Mechanics": self._action_dry_run_bufferlands_mechanics,
            "Test Lock / Edit State": self._action_test_lock_edit_state,
            "Close Reopen Persistence Check": self._action_close_reopen_persistence_check,
            "Describe Last UI Command": self._action_describe_last_ui_command,
        }
        handler = handlers.get(action)
        if handler is None:
            _log_err(messages, "DISPATCH", "unknown action: {0!r}".format(action))
            return

        try:
            handler(parameters, messages)
        except Exception as exc:
            _log_err(messages, "DISPATCH", "{0}: {1}".format(type(exc).__name__, exc))
            _log_warn(messages, "TRACE", traceback.format_exc().strip().splitlines()[-1])
            raise

        _log(messages, "DISPATCH", "action {0!r} complete.".format(action))

    def _action_ping_gui_environment(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        _log(messages, "PING", "sys.executable = {0}".format(sys.executable))
        _log(messages, "PING", "sys.version = {0}".format(sys.version.replace("\n", " ")))
        _log(messages, "PING", "platform = {0}".format(platform.platform()))
        _log(messages, "PING", "resolved gdb = {0!r}".format(gdb_path))

        try:
            import tkinter as tk
            tcl = tk.Tcl()
            _log(messages, "PING", "tkinter import OK; TkVersion={0}; Tcl={1}".format(
                getattr(tk, "TkVersion", "unknown"),
                tcl.eval("info patchlevel"),
            ))
        except Exception as exc:
            _log_err(messages, "PING", "tkinter unavailable: {0}".format(exc))

        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            active_map = aprx.activeMap
            _log(messages, "PING", "ArcGISProject('CURRENT') OK -> filePath={0!r}".format(aprx.filePath))
            _log(messages, "PING", "homeFolder = {0!r}".format(aprx.homeFolder))
            _log(messages, "PING", "activeMap = {0!r}".format(getattr(active_map, "name", None)))
        except Exception as exc:
            _log_warn(messages, "PING", "ArcGISProject('CURRENT') failed: {0}".format(exc))

    def _action_open_command_dialog(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)

        layer = parameters[P_LAYER].value
        layer_text = parameters[P_LAYER].valueAsText
        support_layer = parameters[P_SUPPORT_LAYER].value
        support_text = parameters[P_SUPPORT_LAYER].valueAsText
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        context = collect_selection_context(layer, layer_text, messages)
        support_context = collect_layer_summary(support_layer, support_text, messages, "SUPPORT")
        radius_info = radius_context(parameters[P_RADIUS].value)
        placement_context = collect_placement_context(
            parameters[P_PLACEMENT].value,
            parameters[P_PLACEMENT].valueAsText,
            messages,
        )

        dialog_result = open_tk_command_dialog(context, scenario_mode, support_context, radius_info)
        command = build_command_payload(
            gdb_path,
            scenario_mode,
            context,
            support_context,
            radius_info,
            dialog_result,
            placement_context=placement_context,
        )
        insert_ui_command(table_path, command)

        if command["status"] == "error":
            _log_warn(messages, "UI", command["message"])
        else:
            _log(messages, "UI", command["message"])
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))

        arcpy.SetParameterAsText(P_OUTPUT, table_path)
        _log(messages, "OUTPUT", "Output UI Command Table = {0}".format(table_path))

    def _action_validate_scenario_inputs(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)

        layer = parameters[P_LAYER].value
        layer_text = parameters[P_LAYER].valueAsText
        support_layer = parameters[P_SUPPORT_LAYER].value
        support_text = parameters[P_SUPPORT_LAYER].valueAsText
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        context = collect_selection_context(layer, layer_text, messages)
        support_context = collect_layer_summary(support_layer, support_text, messages, "SUPPORT")
        radius_info = radius_context(parameters[P_RADIUS].value)
        placement_context = collect_placement_context(
            parameters[P_PLACEMENT].value,
            parameters[P_PLACEMENT].valueAsText,
            messages,
        )

        validations = [
            validate_planned_command(command, context, support_context, radius_info, placement_context)
            for command in commands_for_mode(scenario_mode)
        ]
        ready = [item for item in validations if item["ready"]]
        blocked = [item for item in validations if not item["ready"]]

        for item in validations:
            if item["ready"]:
                if item["warnings"]:
                    _log_warn(messages, "FEATURE", "{0}: ready with warning: {1}".format(
                        item["command_name"], "; ".join(item["warnings"])
                    ))
                else:
                    _log(messages, "FEATURE", "{0}: ready".format(item["command_name"]))
            else:
                _log_warn(messages, "FEATURE", "{0}: blocked: {1}".format(
                    item["command_name"], "; ".join(item["errors"])
                ))

        dialog_result = {
            "command_name": "Validate Scenario Inputs",
            "status": "created",
        }
        validation_summary = {
            "command_name": "Validate Scenario Inputs",
            "ready": not blocked,
            "checks": ["planned phase feature matrix"],
            "errors": [],
            "warnings": [],
            "planned_features": validations,
            "ready_count": len(ready),
            "blocked_count": len(blocked),
        }
        command = build_command_payload(
            gdb_path,
            scenario_mode,
            context,
            support_context,
            radius_info,
            dialog_result,
            validation=validation_summary,
            placement_context=placement_context,
        )
        command["message"] = (
            "Validated {total} planned {mode} feature(s): {ready} ready, {blocked} blocked.".format(
                total=len(validations),
                mode=scenario_mode,
                ready=len(ready),
                blocked=len(blocked),
            )
        )
        payload = json.loads(command["payload_json"])
        payload["message"] = command["message"]
        payload["feature_validation"] = validation_summary
        command["payload_json"] = json.dumps(payload, sort_keys=True)
        insert_ui_command(table_path, command)

        _log(messages, "UI", command["message"])
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, table_path)
        _log(messages, "OUTPUT", "Output UI Command Table = {0}".format(table_path))

    def _action_open_novelty_control_panel(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)

        layer = parameters[P_LAYER].value
        layer_text = parameters[P_LAYER].valueAsText
        support_layer = parameters[P_SUPPORT_LAYER].value
        support_text = parameters[P_SUPPORT_LAYER].valueAsText
        scenario_mode = "Novelty Reopen"
        context = collect_selection_context(layer, layer_text, messages)
        support_context = collect_layer_summary(support_layer, support_text, messages, "SUPPORT")
        radius_info = radius_context(parameters[P_RADIUS].value)
        placement_context = collect_placement_context(
            parameters[P_PLACEMENT].value,
            parameters[P_PLACEMENT].valueAsText,
            messages,
        )

        dialog_result = open_novelty_control_panel(context, support_context, placement_context, radius_info)
        validation = validate_planned_command(
            dialog_result.get("command_name") or "Cancel",
            context,
            support_context,
            radius_info,
            placement_context,
        )
        command = build_command_payload(
            gdb_path,
            scenario_mode,
            context,
            support_context,
            radius_info,
            dialog_result,
            validation=validation,
            placement_context=placement_context,
        )
        payload = json.loads(command["payload_json"])
        payload["concept_reopen"] = {
            "ranking_lens": "most novel game",
            "candidate_family": "Spatial Tactics / GP Card Battler",
            "records_only": True,
            "no_game_rules_applied": True,
        }
        command["payload_json"] = json.dumps(payload, sort_keys=True)
        insert_ui_command(table_path, command)

        if command["status"] == "error":
            _log_warn(messages, "NOVELTY", command["message"])
        else:
            _log(messages, "NOVELTY", command["message"])
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, table_path)
        _log(messages, "OUTPUT", "Output UI Command Table = {0}".format(table_path))

    def _action_live_preview_update(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)
        layer = parameters[P_LAYER].value
        layer_text = parameters[P_LAYER].valueAsText
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        context = collect_selection_context(layer, layer_text, messages)
        if not layer:
            message = "Live Preview Update blocked: provide a Game Layer."
            insert_validation_command(table_path, gdb_path, scenario_mode, "Live Preview Update", "error", message, {})
            _log_warn(messages, "LIVE", message)
            return
        if not context.get("selected_oids"):
            message = "Live Preview Update blocked: select at least one Game Layer cell."
            insert_validation_command(table_path, gdb_path, scenario_mode, "Live Preview Update", "error", message, {})
            _log_warn(messages, "LIVE", message)
            return

        ensure_layer_text_field(layer, UI_PREVIEW_FIELD, "UI Preview State", 64, messages)
        dialog_result = open_live_preview_dialog(layer, layer_text, context, messages)
        status = dialog_result.get("status") or "cancelled"
        steps = dialog_result.get("steps") or []
        if status == "error":
            message = "Live Preview Update encountered an error; see payload for step details."
        elif steps:
            message = "Live Preview Update ran {0} preview step(s) while the GUI was open.".format(len(steps))
        else:
            message = "Live Preview Update dialog closed without changing selected cells."

        payload = {
            "target_layer": context.get("target_layer", ""),
            "target_cell_ids": context.get("target_cell_ids", []),
            "selected_oid_count": len(context.get("selected_oids") or []),
            "steps": steps,
        }
        command = insert_validation_command(
            table_path, gdb_path, scenario_mode, "Live Preview Update", status, message, payload
        )
        _log(messages, "LIVE", message)
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, table_path)

    def _action_new_load_game_gui(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        command_table = ensure_ui_command_table(gdb_path, messages)
        session_table = ensure_game_session_table(gdb_path, messages)
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        latest = read_latest_game_session(session_table)
        dialog_result = open_session_dialog(latest, scenario_mode)
        choice = dialog_result.get("choice") or "Cancel"

        status = dialog_result.get("status") or "cancelled"
        game_id = ""
        payload = {"choice": choice}
        if status == "cancelled" or choice == "Cancel":
            message = "Game session dialog cancelled."
        elif choice == "New Game From GUI":
            message = "New GUI-controlled game session created."
            game_id = insert_game_session(session_table, scenario_mode, 2026, message)
            payload["game_id"] = game_id
        elif choice == "Load Game From GUI":
            if latest is None:
                status = "error"
                message = "Load Game blocked: no GameSession rows exist yet."
            else:
                game_id = latest["game_id"]
                message = "Loaded latest GUI-controlled game session {0}.".format(game_id)
                mark_game_session_loaded(session_table, game_id, message)
                payload["game_id"] = game_id
        else:
            status = "error"
            message = "Unknown session dialog choice: {0}".format(choice)

        command = insert_validation_command(
            command_table, gdb_path, scenario_mode, choice, status, message, payload
        )
        if game_id:
            update_ui_command_status(command_table, command["command_id"], status, game_id=game_id)
        if status == "error":
            _log_warn(messages, "SESSION", message)
        else:
            _log(messages, "SESSION", message)
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, command_table)

    def _action_simulate_crash_after_command_insert(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        message = "Inserted command row, then intentionally raised before apply."
        command = insert_validation_command(
            table_path,
            gdb_path,
            scenario_mode,
            "Crash Test - After Insert",
            "created",
            message,
            {"crash_point": "after_insert"},
        )
        _log_warn(messages, "CRASH", "created command_id = {0}".format(command["command_id"]))
        raise RuntimeError("Intentional crash after command insert for recovery validation.")

    def _action_simulate_crash_during_apply(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        command = insert_validation_command(
            table_path,
            gdb_path,
            scenario_mode,
            "Crash Test - During Apply",
            "created",
            "Inserted command row for during-apply crash simulation.",
            {"crash_point": "before_applying"},
        )
        update_ui_command_status(
            table_path,
            command["command_id"],
            "applying",
            message="Command marked applying, then intentionally raised.",
            started_utc=_now_utc(),
            increment_attempt=True,
        )
        _log_warn(messages, "CRASH", "marked applying command_id = {0}".format(command["command_id"]))
        raise RuntimeError("Intentional crash during apply for recovery validation.")

    def _action_recover_pending_commands(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        fields = [
            "command_id",
            "command_name",
            "status",
            "attempt_count",
            "finished_utc",
            "error_message",
            "message",
        ]
        recovered = []
        with arcpy.da.UpdateCursor(table_path, fields) as cursor:
            for row in cursor:
                if row[2] not in ("created", "applying"):
                    continue
                if row[1] == "Recover Pending Commands":
                    continue
                row[2] = "abandoned"
                row[3] = (row[3] or 0) + 1
                row[4] = _now_utc()
                row[5] = "Recovered pending command after interrupted validation run."
                row[6] = "Marked abandoned by Recover Pending Commands."
                recovered.append(row[0])
                cursor.updateRow(row)

        message = "Recovered {0} pending command(s).".format(len(recovered))
        command = insert_validation_command(
            table_path,
            gdb_path,
            scenario_mode,
            "Recover Pending Commands",
            "applied",
            message,
            {"recovered_command_ids": recovered},
        )
        _log(messages, "RECOVER", message)
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, table_path)

    def _action_apply_last_command_idempotency(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)
        layer = parameters[P_LAYER].value
        layer_text = parameters[P_LAYER].valueAsText
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        context = collect_selection_context(layer, layer_text, messages)
        if not layer or not context.get("selected_oids"):
            message = "Idempotency test blocked: select at least one Game Layer cell."
            insert_validation_command(table_path, gdb_path, scenario_mode, "Apply Last Command Idempotency", "error", message, {})
            _log_warn(messages, "IDEMPOTENT", message)
            return

        ensure_layer_text_field(layer, LAST_COMMAND_FIELD, "Last Command ID", 64, messages)
        command_id = str(uuid.uuid4())

        def apply_once():
            applied = 0
            skipped = 0
            with arcpy.da.UpdateCursor(layer, [LAST_COMMAND_FIELD]) as cursor:
                for row in cursor:
                    if row[0] == command_id:
                        skipped += 1
                        continue
                    row[0] = command_id
                    cursor.updateRow(row)
                    applied += 1
            return applied, skipped

        first_applied, first_skipped = apply_once()
        second_applied, second_skipped = apply_once()
        message = (
            "Idempotency apply used command_id {0}: first applied={1}, second applied={2}.".format(
                command_id, first_applied, second_applied
            )
        )
        payload = {
            "target_layer": context.get("target_layer", ""),
            "target_cell_ids": context.get("target_cell_ids", []),
            "selected_oid_count": len(context.get("selected_oids") or []),
            "idempotency_command_id": command_id,
            "first_applied": first_applied,
            "first_skipped": first_skipped,
            "second_applied": second_applied,
            "second_skipped": second_skipped,
        }
        command = insert_validation_command(
            table_path, gdb_path, scenario_mode, "Apply Last Command Idempotency", "applied", message, payload
        )
        refresh_layer(layer, layer_text, messages, "IDEMPOTENT")
        _log(messages, "IDEMPOTENT", message)
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, table_path)

    def _action_dry_run_containment_mechanics(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)
        layer = parameters[P_LAYER].value
        layer_text = parameters[P_LAYER].valueAsText
        context = collect_selection_context(layer, layer_text, messages)
        support_context = collect_layer_summary(parameters[P_SUPPORT_LAYER].value, parameters[P_SUPPORT_LAYER].valueAsText, messages, "SUPPORT")
        radius_info = radius_context(parameters[P_RADIUS].value)
        scenario_mode = "Containment Commander"
        validations = [
            validate_planned_command(command, context, support_context, radius_info)
            for command in CONTAINMENT_COMMANDS
        ]
        selected_count = len(context.get("selected_oids") or [])
        board_count = None
        if layer:
            try:
                board_count = int(arcpy.management.GetCount(layer)[0])
            except Exception as exc:
                _log_warn(messages, "CONTAINMENT", "GetCount failed: {0}".format(exc))
        ready = [item for item in validations if item["ready"]]
        blocked = [item for item in validations if not item["ready"]]
        message = "Containment dry run: {0} selected, board_count={1}, {2} ready, {3} blocked.".format(
            selected_count, board_count, len(ready), len(blocked)
        )
        payload = {
            "target_layer": context.get("target_layer", ""),
            "target_cell_ids": context.get("target_cell_ids", []),
            "selected_oid_count": selected_count,
            "board_count": board_count,
            "planned_features": validations,
        }
        command = insert_validation_command(
            table_path, gdb_path, scenario_mode, "Dry Run Containment Mechanics", "applied", message, payload
        )
        for item in validations:
            if item["ready"]:
                _log(messages, "CONTAINMENT", "{0}: ready".format(item["command_name"]))
            else:
                _log_warn(messages, "CONTAINMENT", "{0}: blocked: {1}".format(
                    item["command_name"], "; ".join(item["errors"])
                ))
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, table_path)

    def _action_dry_run_bufferlands_mechanics(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)
        layer = parameters[P_LAYER].value
        layer_text = parameters[P_LAYER].valueAsText
        support_layer = parameters[P_SUPPORT_LAYER].value
        support_text = parameters[P_SUPPORT_LAYER].valueAsText
        context = collect_selection_context(layer, layer_text, messages)
        support_context = collect_layer_summary(support_layer, support_text, messages, "SUPPORT")
        radius_info = radius_context(parameters[P_RADIUS].value)
        validations = [
            validate_planned_command(command, context, support_context, radius_info)
            for command in BUFFERLANDS_COMMANDS
        ]
        buffer_count = None
        affected_count = None
        spatial_join_count = None
        errors = []
        mem_buffer = r"memory\arcpy_game_gui_spike_buffer"
        mem_join = r"memory\arcpy_game_gui_spike_spatial_join"

        try:
            for path in (mem_buffer, mem_join):
                if arcpy.Exists(path):
                    arcpy.management.Delete(path)
        except Exception as exc:
            _log_warn(messages, "BUFFERLANDS", "memory cleanup warning: {0}".format(exc))

        if layer and context.get("selected_oids") and radius_info.get("valid"):
            try:
                arcpy.analysis.Buffer(layer, mem_buffer, "{0} Meters".format(radius_info["value"]))
                buffer_count = int(arcpy.management.GetCount(mem_buffer)[0])
                arcpy.management.SelectLayerByLocation(
                    in_layer=layer,
                    overlap_type="INTERSECT",
                    select_features=mem_buffer,
                    selection_type="NEW_SELECTION",
                )
                affected_count = int(arcpy.management.GetCount(layer)[0])
                _log(messages, "BUFFERLANDS", "Buffer Defense dry run affected {0} cell(s)".format(affected_count))
            except Exception as exc:
                errors.append("Buffer Defense dry run failed: {0}".format(exc))
                _log_warn(messages, "BUFFERLANDS", errors[-1])
        else:
            errors.append("Buffer Defense dry run skipped: selected cells and positive radius are required")

        if support_layer and layer:
            try:
                arcpy.analysis.SpatialJoin(
                    target_features=support_layer,
                    join_features=layer,
                    out_feature_class=mem_join,
                    join_operation="JOIN_ONE_TO_ONE",
                    join_type="KEEP_COMMON",
                    match_option="INTERSECT",
                )
                spatial_join_count = int(arcpy.management.GetCount(mem_join)[0])
                _log(messages, "BUFFERLANDS", "Spatial Join Harvest dry run joined {0} feature(s)".format(spatial_join_count))
            except Exception as exc:
                errors.append("Spatial Join Harvest dry run failed: {0}".format(exc))
                _log_warn(messages, "BUFFERLANDS", errors[-1])
        else:
            errors.append("Spatial Join Harvest dry run skipped: Game Layer and Support Layer are required")

        status = "applied" if not errors else "error"
        message = (
            "Bufferlands dry run: buffer_count={0}, affected_count={1}, spatial_join_count={2}, errors={3}.".format(
                buffer_count, affected_count, spatial_join_count, len(errors)
            )
        )
        payload = {
            "target_layer": context.get("target_layer", ""),
            "target_cell_ids": context.get("target_cell_ids", []),
            "selected_oid_count": len(context.get("selected_oids") or []),
            "support_layer": support_context,
            "radius": radius_info,
            "planned_features": validations,
            "buffer_count": buffer_count,
            "affected_count": affected_count,
            "spatial_join_count": spatial_join_count,
            "errors": errors,
        }
        command = insert_validation_command(
            table_path, gdb_path, "Bufferlands Stretch", "Dry Run Bufferlands Mechanics", status, message, payload
        )
        _log(messages, "BUFFERLANDS", message)
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, table_path)

    def _action_test_lock_edit_state(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = ensure_ui_command_table(gdb_path, messages)
        layer = parameters[P_LAYER].value
        layer_text = parameters[P_LAYER].valueAsText
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        context = collect_selection_context(layer, layer_text, messages)
        payload = {
            "target_layer": context.get("target_layer", ""),
            "target_cell_ids": context.get("target_cell_ids", []),
            "selected_oid_count": len(context.get("selected_oids") or []),
        }
        errors = []
        if not layer:
            errors.append("provide a Game Layer")
        else:
            try:
                payload["schema_lock"] = bool(arcpy.TestSchemaLock(layer))
                _log(messages, "LOCK", "TestSchemaLock(layer) = {0}".format(payload["schema_lock"]))
            except Exception as exc:
                errors.append("TestSchemaLock failed: {0}".format(exc))
            if not context.get("selected_oids"):
                errors.append("select at least one Game Layer cell for UpdateCursor lock probe")
            else:
                try:
                    ensure_layer_short_field(layer, LOCK_PROBE_FIELD, "UI Lock Probe", messages)
                    updated = 0
                    with arcpy.da.UpdateCursor(layer, [LOCK_PROBE_FIELD]) as cursor:
                        for row in cursor:
                            row[0] = 1 if not row[0] else row[0]
                            cursor.updateRow(row)
                            updated += 1
                    payload["update_cursor_rows"] = updated
                    _log(messages, "LOCK", "UpdateCursor wrote {0} selected row(s)".format(updated))
                except Exception as exc:
                    errors.append("Update/schema probe failed: {0}".format(exc))

        status = "applied" if not errors else "error"
        message = "Lock/edit-state probe complete with {0} error(s).".format(len(errors))
        payload["errors"] = errors
        command = insert_validation_command(
            table_path, gdb_path, scenario_mode, "Test Lock / Edit State", status, message, payload
        )
        if layer:
            refresh_layer(layer, layer_text, messages, "LOCK")
        _log(messages, "LOCK", message)
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, table_path)

    def _action_close_reopen_persistence_check(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        command_table = ensure_ui_command_table(gdb_path, messages)
        session_table = ensure_game_session_table(gdb_path, messages)
        scenario_mode = parameters[P_MODE].valueAsText or "Survey Sweeper"
        command_count = int(arcpy.management.GetCount(command_table)[0])
        session_count = int(arcpy.management.GetCount(session_table)[0])
        latest_command = read_last_ui_command(command_table)
        latest_session = read_latest_game_session(session_table)
        payload = {
            "workspace": gdb_path,
            "command_count": command_count,
            "session_count": session_count,
            "latest_command_id": latest_command.get("command_id") if latest_command else "",
            "latest_session_id": latest_session.get("game_id") if latest_session else "",
            "current_project_available": False,
        }
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            payload["current_project_available"] = True
            payload["project_path"] = aprx.filePath
            payload["home_folder"] = aprx.homeFolder
        except Exception as exc:
            payload["project_error"] = str(exc)

        message = "Persistence check: {0} UICommand row(s), {1} GameSession row(s).".format(
            command_count, session_count
        )
        command = insert_validation_command(
            command_table,
            gdb_path,
            scenario_mode,
            "Close Reopen Persistence Check",
            "applied",
            message,
            payload,
        )
        _log(messages, "PERSIST", message)
        _log(messages, "UI", "command_id = {0}".format(command["command_id"]))
        arcpy.SetParameterAsText(P_OUTPUT, command_table)

    def _action_describe_last_ui_command(self, parameters, messages):
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        table_path = os.path.join(gdb_path, UI_COMMAND_TABLE)
        if not arcpy.Exists(table_path):
            _log_warn(messages, "DESCRIBE", "UICommand table does not exist: {0}".format(table_path))
            return

        last = read_last_ui_command(table_path)
        if last is None:
            _log_warn(messages, "DESCRIBE", "UICommand table exists but has no rows")
            arcpy.SetParameterAsText(P_OUTPUT, table_path)
            return

        _log(messages, "DESCRIBE", "OBJECTID = {0}".format(last.get("OBJECTID") or last.get("OID@")))
        _log(messages, "DESCRIBE", "command_id = {0}".format(last.get("command_id")))
        _log(messages, "DESCRIBE", "created_utc = {0}".format(last.get("created_utc")))
        _log(messages, "DESCRIBE", "scenario_mode = {0}".format(last.get("scenario_mode")))
        _log(messages, "DESCRIBE", "command_name = {0}".format(last.get("command_name")))
        _log(messages, "DESCRIBE", "target_layer = {0}".format(last.get("target_layer")))
        _log(messages, "DESCRIBE", "target_cell_ids = {0}".format(last.get("target_cell_ids")))
        _log(messages, "DESCRIBE", "selected_oid_count = {0}".format(last.get("selected_oid_count")))
        _log(messages, "DESCRIBE", "status = {0}".format(last.get("status")))
        _log(messages, "DESCRIBE", "attempt_count = {0}".format(last.get("attempt_count")))
        _log(messages, "DESCRIBE", "game_id = {0}".format(last.get("game_id")))
        _log(messages, "DESCRIBE", "error_message = {0}".format(last.get("error_message")))
        _log(messages, "DESCRIBE", "message = {0}".format(last.get("message")))

        arcpy.SetParameterAsText(P_OUTPUT, table_path)
        _log(messages, "OUTPUT", "Output UI Command Table = {0}".format(table_path))
