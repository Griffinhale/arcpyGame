"""ArcGIS geodatabase schema creation for the Permit Office prototype."""

from __future__ import annotations

import os

import arcpy

from .messages import _log, _warn

TOOLBOX_LABEL = "Permit Office Prototype"
TOOLBOX_ALIAS = "permit_office"

DEFAULT_GDB_NAME = "permit_office.gdb"
DISTRICTS = "PermitDistricts"
POINTS = "PermitPoints"
LINES = "PermitLines"
ZONES = "PermitZones"
DOCKET = "PermitDocket"
GAME_STATE = "PermitGameState"
PROJECTS = "PermitProjects"
COMMANDS = "PermitUICommand"
ACTION_LOG = "PermitActionLog"

P_WORKSPACE = 0
P_DISTRICTS = 1
P_ACTION = 2
P_SEED = 3
P_OUTPUT = 4

ACTIONS = [
    "Ping Environment",
    "New Game",
    "Open Dashboard",
    "Generate Docket",
    "Show Scorecard",
]

DISTRICT_FIELDS = [
    ("cell_id", "TEXT", "District ID", 32),
    ("district_name", "TEXT", "District Name", 96),
    ("population", "LONG", "Population", None),
    ("prosperity", "LONG", "Prosperity", None),
    ("unrest", "LONG", "Unrest", None),
    ("culture", "LONG", "Culture", None),
    ("risk", "LONG", "Health / Risk", None),
    ("services", "LONG", "Services", None),
    ("district_type", "TEXT", "Hidden District Type", 32),
    ("land_use", "TEXT", "Land Use", 32),
    ("zoning_overlay", "TEXT", "Zoning Overlay", 32),
    ("display_state", "TEXT", "Display State", 32),
    ("service_gap_json", "TEXT", "Service Gaps", 1024),
    ("adjacent_cell_ids", "TEXT", "Adjacent District IDs", 512),
    ("network_access_json", "TEXT", "Network Access", 1024),
    ("hazard_json", "TEXT", "Hazards", 1024),
    ("housing_capacity", "LONG", "Housing Capacity", None),
    ("affordability", "LONG", "Affordability", None),
    ("vacancy_rate", "SHORT", "Vacancy Rate", None),
    ("displacement_json", "TEXT", "Displacement", 1024),
    ("population_mix_json", "TEXT", "Population Mix", 1024),
    ("dissatisfaction_json", "TEXT", "Dissatisfaction", 1024),
    ("incident_state", "TEXT", "Civic Incident State", 32),
    ("incident_group", "TEXT", "Civic Incident Group", 32),
    ("public_profile", "TEXT", "Public Profile", 512),
    ("last_report", "TEXT", "Last Report", 512),
]

SUPPORT_FIELDS = [
    ("feature_id", "TEXT", "Feature ID", 64),
    ("item_id", "TEXT", "Docket Item ID", 96),
    ("template_id", "TEXT", "Template ID", 64),
    ("project_id", "TEXT", "Project ID", 96),
    ("chain_step_id", "TEXT", "Project Step ID", 64),
    ("feature_name", "TEXT", "Feature Name", 128),
    ("feature_type", "TEXT", "Feature Type", 32),
    ("archetype_id", "TEXT", "Archetype ID", 64),
    ("family", "TEXT", "Feature Family", 32),
    ("service_type", "TEXT", "Service Type", 32),
    ("network_type", "TEXT", "Network Type", 32),
    ("coverage_radius_m", "DOUBLE", "Coverage Radius Meters", None),
    ("capacity", "LONG", "Capacity", None),
    ("land_use", "TEXT", "Land Use", 32),
    ("incident_type", "TEXT", "Incident Type", 32),
    ("owner_group", "TEXT", "Owner Group", 64),
    ("intensity", "LONG", "Intensity", None),
    ("metadata_json", "TEXT", "Metadata JSON", 2048),
    ("hazard_summary", "TEXT", "Hazard Summary", 512),
    ("mitigation_summary", "TEXT", "Mitigation Summary", 512),
    ("status", "TEXT", "Status", 32),
    ("turn_created", "LONG", "Turn Created", None),
    ("expires_turn", "LONG", "Expires Turn", None),
    ("target_cell_ids", "TEXT", "Target District IDs", 512),
    ("display_state", "TEXT", "Display State", 32),
    ("report", "TEXT", "Report", 1024),
    ("condition", "LONG", "Condition", None),
    ("maintenance_due_turn", "LONG", "Maintenance Due Turn", None),
    ("last_maintained_turn", "LONG", "Last Maintained Turn", None),
    ("state_json", "TEXT", "Feature State JSON", 4000),
]

DOCKET_FIELDS = [
    ("item_id", "TEXT", "Docket Item ID", 96),
    ("turn", "LONG", "Turn", None),
    ("template_id", "TEXT", "Template ID", 64),
    ("title", "TEXT", "Title", 128),
    ("geometry_type", "TEXT", "Geometry Type", 16),
    ("status", "TEXT", "Status", 32),
    ("inspected", "SHORT", "Inspected", None),
    ("target_cell_ids", "TEXT", "Target District IDs", 512),
    ("preview_text", "TEXT", "Preview Text", 2048),
    ("risk_band", "TEXT", "Risk Band", 32),
    ("carryover", "TEXT", "Carryover Rule", 64),
    ("stakeholder", "TEXT", "Stakeholder", 64),
    ("origin_item_id", "TEXT", "Origin Item ID", 96),
    ("target_rule", "TEXT", "Target Rule", 512),
    ("project_id", "TEXT", "Project ID", 96),
    ("chain_step_id", "TEXT", "Project Step ID", 64),
    ("scenario_tags", "TEXT", "Scenario Tags", 256),
    ("priority", "LONG", "Priority", None),
    ("due_turn", "LONG", "Due Turn", None),
    ("subject_feature_id", "TEXT", "Subject Feature ID", 64),
    ("case_json", "TEXT", "Case JSON", 4000),
]

STATE_FIELDS = [
    ("key", "TEXT", "Key", 64),
    ("value_text", "TEXT", "Value Text", 2048),
    ("value_num", "DOUBLE", "Value Number", None),
]

PROJECT_FIELDS = [
    ("project_id", "TEXT", "Project ID", 96),
    ("chain_template_id", "TEXT", "Chain Template ID", 96),
    ("current_step_id", "TEXT", "Current Step ID", 64),
    ("status", "TEXT", "Status", 32),
    ("turn_started", "LONG", "Turn Started", None),
    ("due_turn", "LONG", "Due Turn", None),
    ("stakeholder", "TEXT", "Stakeholder", 64),
    ("target_cell_ids", "TEXT", "Target District IDs", 512),
    ("payload_json", "TEXT", "Payload JSON", 4000),
    ("last_report", "TEXT", "Last Report", 1024),
]

COMMAND_FIELDS = [
    ("command_id", "TEXT", "Command ID", 64),
    ("created_utc", "DATE", "Created UTC", None),
    ("finished_utc", "DATE", "Finished UTC", None),
    ("action", "TEXT", "Action", 64),
    ("item_id", "TEXT", "Docket Item ID", 96),
    ("status", "TEXT", "Status", 32),
    ("attempt_count", "LONG", "Attempt Count", None),
    ("target_cell_ids", "TEXT", "Target District IDs", 512),
    ("payload_json", "TEXT", "Payload JSON", 4000),
    ("message", "TEXT", "Message", 1024),
    ("error_message", "TEXT", "Error Message", 1024),
]

ACTION_LOG_FIELDS = [
    ("created_utc", "DATE", "Created UTC", None),
    ("turn", "LONG", "Turn", None),
    ("action", "TEXT", "Action", 64),
    ("item_id", "TEXT", "Docket Item ID", 96),
    ("target_cell_ids", "TEXT", "Target District IDs", 512),
    ("result", "TEXT", "Result", 2048),
    ("city_delta", "TEXT", "City Delta", 512),
]


def resolve_workspace(value, messages):
    """Resolve the geodatabase path from user input, project home, or scratch."""

    if value:
        text = str(value)
        if text.lower().endswith(".gdb"):
            return text
        return os.path.join(text, DEFAULT_GDB_NAME)
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        if aprx.homeFolder:
            return os.path.join(aprx.homeFolder, "data", DEFAULT_GDB_NAME)
    except Exception as exc:
        _warn(messages, "WORKSPACE", f"ArcGISProject('CURRENT') failed: {exc}")
    scratch = arcpy.env.scratchWorkspace or arcpy.env.scratchFolder or os.getcwd()
    if str(scratch).lower().endswith(".gdb"):
        return str(scratch)
    return os.path.join(str(scratch), DEFAULT_GDB_NAME)


def ensure_gdb(gdb_path, messages):
    """Create the target file geodatabase when it does not already exist."""

    folder = os.path.dirname(gdb_path)
    name = os.path.basename(gdb_path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    if not arcpy.Exists(gdb_path):
        arcpy.management.CreateFileGDB(folder or os.getcwd(), name)
        _log(messages, "SCHEMA", f"created gdb: {gdb_path}")
    return gdb_path


def add_field_if_missing(table, name, field_type, alias=None, length=None):
    """Add one ArcGIS field if the table does not already contain it."""

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


def ensure_table(gdb_path, name, fields, messages):
    """Create or update a non-spatial table with the configured fields."""

    path = os.path.join(gdb_path, name)
    if not arcpy.Exists(path):
        arcpy.management.CreateTable(gdb_path, name)
        _log(messages, "SCHEMA", f"created table: {name}")
    for field in fields:
        add_field_if_missing(path, *field)
    return path


def ensure_feature_class(gdb_path, name, geometry_type, fields, spatial_ref, messages):
    """Create or update a feature class with the configured fields."""

    path = os.path.join(gdb_path, name)
    if not arcpy.Exists(path):
        arcpy.management.CreateFeatureclass(gdb_path, name, geometry_type, spatial_reference=spatial_ref)
        _log(messages, "SCHEMA", f"created feature class: {name}")
    for field in fields:
        add_field_if_missing(path, *field)
    return path


def active_spatial_reference(messages):
    """Use the active ArcGIS map spatial reference, falling back to Web Mercator."""

    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap
        if active_map and active_map.spatialReference:
            return active_map.spatialReference
    except Exception as exc:
        _warn(messages, "MAP", f"active map SR unavailable: {exc}")
    return arcpy.SpatialReference(3857)


def ensure_schema(gdb_path, messages):
    """Ensure all active feature classes and tables exist in the game geodatabase."""

    ensure_gdb(gdb_path, messages)
    sr = active_spatial_reference(messages)
    paths = {
        "districts": ensure_feature_class(gdb_path, DISTRICTS, "POLYGON", DISTRICT_FIELDS, sr, messages),
        "points": ensure_feature_class(gdb_path, POINTS, "POINT", SUPPORT_FIELDS, sr, messages),
        "lines": ensure_feature_class(gdb_path, LINES, "POLYLINE", SUPPORT_FIELDS, sr, messages),
        "zones": ensure_feature_class(gdb_path, ZONES, "POLYGON", SUPPORT_FIELDS, sr, messages),
        "docket": ensure_table(gdb_path, DOCKET, DOCKET_FIELDS, messages),
        "state": ensure_table(gdb_path, GAME_STATE, STATE_FIELDS, messages),
        "projects": ensure_table(gdb_path, PROJECTS, PROJECT_FIELDS, messages),
        "commands": ensure_table(gdb_path, COMMANDS, COMMAND_FIELDS, messages),
        "action_log": ensure_table(gdb_path, ACTION_LOG, ACTION_LOG_FIELDS, messages),
    }
    return paths


def clear_game_rows(paths):
    """Delete gameplay rows while preserving the existing geodatabase schema."""

    for key in ("districts", "points", "lines", "zones", "docket", "state", "projects", "commands", "action_log"):
        if arcpy.Exists(paths[key]):
            arcpy.management.DeleteRows(paths[key])
