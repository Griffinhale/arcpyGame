"""Permit Office prototype toolbox.

This is the first playable validation slice for the permit-office city sim:
generated districts, a three-item docket, proposed support geometries, a
Tkinter dashboard, immediate command apply, map refresh, and effect reports.
"""

from __future__ import annotations

import datetime as _datetime
import importlib.util
import json
import os
import sys
import traceback
import uuid

import arcpy


TOOLBOX_LABEL = "Permit Office Prototype"
TOOLBOX_ALIAS = "permit_office"

DEFAULT_GDB_NAME = "permit_office.gdb"
DISTRICTS = "PermitDistricts"
POINTS = "PermitPoints"
LINES = "PermitLines"
ZONES = "PermitZones"
DOCKET = "PermitDocket"
GAME_STATE = "PermitGameState"
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
    ("feature_name", "TEXT", "Feature Name", 128),
    ("feature_type", "TEXT", "Feature Type", 32),
    ("archetype_id", "TEXT", "Archetype ID", 64),
    ("family", "TEXT", "Feature Family", 32),
    ("service_type", "TEXT", "Service Type", 32),
    ("coverage_radius_m", "DOUBLE", "Coverage Radius Meters", None),
    ("capacity", "LONG", "Capacity", None),
    ("land_use", "TEXT", "Land Use", 32),
    ("incident_type", "TEXT", "Incident Type", 32),
    ("owner_group", "TEXT", "Owner Group", 64),
    ("intensity", "LONG", "Intensity", None),
    ("metadata_json", "TEXT", "Metadata JSON", 2048),
    ("status", "TEXT", "Status", 32),
    ("turn_created", "LONG", "Turn Created", None),
    ("expires_turn", "LONG", "Expires Turn", None),
    ("target_cell_ids", "TEXT", "Target District IDs", 512),
    ("display_state", "TEXT", "Display State", 32),
    ("report", "TEXT", "Report", 1024),
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
]

STATE_FIELDS = [
    ("key", "TEXT", "Key", 64),
    ("value_text", "TEXT", "Value Text", 2048),
    ("value_num", "DOUBLE", "Value Number", None),
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


def _load_rules():
    here = os.path.dirname(__file__)
    path = os.path.join(here, "arcpy_permit_office_rules.py")
    spec = importlib.util.spec_from_file_location("arcpy_permit_office_rules", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rules = _load_rules()


def _log(messages, tag, text):
    line = f"[{tag}] {text}"
    try:
        messages.addMessage(line)
    except Exception:
        arcpy.AddMessage(line)


def _warn(messages, tag, text):
    line = f"[{tag}] WARN: {text}"
    try:
        messages.addWarningMessage(line)
    except Exception:
        arcpy.AddWarning(line)


def _err(messages, tag, text):
    line = f"[{tag}] ERROR: {text}"
    try:
        messages.addErrorMessage(line)
    except Exception:
        arcpy.AddError(line)


def now_utc():
    return _datetime.datetime.utcnow()


def resolve_workspace(value, messages):
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
    folder = os.path.dirname(gdb_path)
    name = os.path.basename(gdb_path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    if not arcpy.Exists(gdb_path):
        arcpy.management.CreateFileGDB(folder or os.getcwd(), name)
        _log(messages, "SCHEMA", f"created gdb: {gdb_path}")
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


def ensure_table(gdb_path, name, fields, messages):
    path = os.path.join(gdb_path, name)
    if not arcpy.Exists(path):
        arcpy.management.CreateTable(gdb_path, name)
        _log(messages, "SCHEMA", f"created table: {name}")
    for field in fields:
        add_field_if_missing(path, *field)
    return path


def ensure_feature_class(gdb_path, name, geometry_type, fields, spatial_ref, messages):
    path = os.path.join(gdb_path, name)
    if not arcpy.Exists(path):
        arcpy.management.CreateFeatureclass(gdb_path, name, geometry_type, spatial_reference=spatial_ref)
        _log(messages, "SCHEMA", f"created feature class: {name}")
    for field in fields:
        add_field_if_missing(path, *field)
    return path


def active_spatial_reference(messages):
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap
        if active_map and active_map.spatialReference:
            return active_map.spatialReference
    except Exception as exc:
        _warn(messages, "MAP", f"active map SR unavailable: {exc}")
    return arcpy.SpatialReference(3857)


def ensure_schema(gdb_path, messages):
    ensure_gdb(gdb_path, messages)
    sr = active_spatial_reference(messages)
    paths = {
        "districts": ensure_feature_class(gdb_path, DISTRICTS, "POLYGON", DISTRICT_FIELDS, sr, messages),
        "points": ensure_feature_class(gdb_path, POINTS, "POINT", SUPPORT_FIELDS, sr, messages),
        "lines": ensure_feature_class(gdb_path, LINES, "POLYLINE", SUPPORT_FIELDS, sr, messages),
        "zones": ensure_feature_class(gdb_path, ZONES, "POLYGON", SUPPORT_FIELDS, sr, messages),
        "docket": ensure_table(gdb_path, DOCKET, DOCKET_FIELDS, messages),
        "state": ensure_table(gdb_path, GAME_STATE, STATE_FIELDS, messages),
        "commands": ensure_table(gdb_path, COMMANDS, COMMAND_FIELDS, messages),
        "action_log": ensure_table(gdb_path, ACTION_LOG, ACTION_LOG_FIELDS, messages),
    }
    return paths


def clear_game_rows(paths):
    for key in ("districts", "points", "lines", "zones", "docket", "state", "commands", "action_log"):
        if arcpy.Exists(paths[key]):
            arcpy.management.DeleteRows(paths[key])


def square_polygon(x0, y0, size, sr):
    arr = arcpy.Array([
        arcpy.Point(x0, y0),
        arcpy.Point(x0 + size, y0),
        arcpy.Point(x0 + size, y0 + size),
        arcpy.Point(x0, y0 + size),
        arcpy.Point(x0, y0),
    ])
    return arcpy.Polygon(arr, sr)


def create_district_board(paths, seed, messages):
    sr = arcpy.Describe(paths["districts"]).spatialReference
    profiles = rules.generate_district_profiles(rows=5, cols=5, seed=seed)
    fields = [
        "SHAPE@",
        "cell_id",
        "district_name",
        "population",
        "prosperity",
        "unrest",
        "culture",
        "risk",
        "services",
        "district_type",
        "land_use",
        "zoning_overlay",
        "display_state",
        "service_gap_json",
        "population_mix_json",
        "dissatisfaction_json",
        "incident_state",
        "incident_group",
        "public_profile",
        "last_report",
    ]
    with arcpy.da.InsertCursor(paths["districts"], fields) as cursor:
        for profile in profiles:
            row = int(profile.cell_id[1:3])
            col = int(profile.cell_id[3:5])
            geom = square_polygon(col * 100.0, row * 100.0, 96.0, sr)
            cursor.insertRow([
                geom,
                profile.cell_id,
                profile.name,
                profile.population,
                profile.prosperity,
                profile.unrest,
                profile.culture,
                profile.risk,
                profile.services,
                profile.district_type,
                profile.land_use,
                profile.zoning_overlay,
                profile.display_state,
                encode_service_gap(profile.service_gap),
                encode_group_bands(profile.population_mix, maximum=3),
                encode_group_bands(profile.dissatisfaction, maximum=4),
                profile.incident_state,
                profile.incident_group,
                profile.public_profile,
                "New district profile generated.",
            ])
    _log(messages, "NEW", f"inserted {len(profiles)} districts")


def write_state(paths, state):
    values = {
        "turn": (str(state.turn), state.turn),
        "max_turns": (str(state.max_turns), state.max_turns),
        "ap": (str(state.ap), state.ap),
        "max_ap": (str(state.max_ap), state.max_ap),
        "money": (str(state.money), state.money),
        "audit_stage": (str(state.audit_stage), state.audit_stage),
        "status": (state.status, None),
        "last_report": (state.last_report, None),
        "prosperity": (str(state.prosperity), state.prosperity),
        "unrest": (str(state.unrest), state.unrest),
        "culture": (str(state.culture), state.culture),
        "risk": (str(state.risk), state.risk),
        "stakeholder_heat": (json.dumps(state.stakeholder_heat, sort_keys=True), None),
    }
    arcpy.management.DeleteRows(paths["state"])
    with arcpy.da.InsertCursor(paths["state"], ["key", "value_text", "value_num"]) as cursor:
        for key, (text, num) in values.items():
            cursor.insertRow([key, text, num])


def read_state(paths):
    values = {}
    with arcpy.da.SearchCursor(paths["state"], ["key", "value_text", "value_num"]) as cursor:
        for key, text, num in cursor:
            values[key] = (text, num)
    state = rules.CityState()
    for key in ("turn", "max_turns", "ap", "max_ap", "money", "audit_stage", "prosperity", "unrest", "culture", "risk"):
        if key in values and values[key][1] is not None:
            setattr(state, key, int(values[key][1]))
    for key in ("status", "last_report"):
        if key in values:
            setattr(state, key, values[key][0] or "")
    if "stakeholder_heat" in values and values["stakeholder_heat"][0]:
        try:
            parsed = json.loads(values["stakeholder_heat"][0])
            state.stakeholder_heat = {str(key): int(value) for key, value in parsed.items()}
        except Exception:
            state.stakeholder_heat = {}
    return state


def encode_group_bands(value, maximum=4):
    out = {}
    for group, band in (value or {}).items():
        if group in rules.CITIZEN_GROUPS:
            out[group] = max(0, min(maximum, int(band or 0)))
    return json.dumps({group: band for group, band in sorted(out.items()) if band > 0}, sort_keys=True)


def decode_group_bands(text, maximum=4):
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    out = {}
    for group, band in parsed.items():
        if group in rules.CITIZEN_GROUPS:
            out[group] = max(0, min(maximum, int(band or 0)))
    return out


def encode_service_gap(value):
    out = {}
    for service, gap in (value or {}).items():
        if service in rules.SERVICE_TYPES:
            out[service] = max(0, int(gap or 0))
    return json.dumps({service: gap for service, gap in sorted(out.items()) if gap > 0}, sort_keys=True)


def decode_service_gap(text):
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    out = {}
    for service, gap in parsed.items():
        if service in rules.SERVICE_TYPES:
            out[service] = max(0, int(gap or 0))
    return out


def read_districts(paths):
    out = {}
    fields = [
        "cell_id",
        "district_name",
        "population",
        "prosperity",
        "unrest",
        "culture",
        "risk",
        "services",
        "district_type",
        "land_use",
        "zoning_overlay",
        "display_state",
        "service_gap_json",
        "population_mix_json",
        "dissatisfaction_json",
        "incident_state",
        "incident_group",
        "public_profile",
    ]
    with arcpy.da.SearchCursor(paths["districts"], fields) as cursor:
        for row in cursor:
            profile = rules.DistrictProfile(
                cell_id=row[0],
                name=row[1],
                population=int(row[2] or 0),
                prosperity=int(row[3] or 0),
                unrest=int(row[4] or 0),
                culture=int(row[5] or 0),
                risk=int(row[6] or 0),
                services=int(row[7] or 0),
                district_type=row[8] or "mercantile",
                land_use=row[9] or "",
                zoning_overlay=row[10] or "",
                display_state=row[11] or "stable",
                service_gap=decode_service_gap(row[12]),
                population_mix=decode_group_bands(row[13], maximum=3),
                dissatisfaction=decode_group_bands(row[14], maximum=4),
                incident_state=row[15] or "none",
                incident_group=row[16] or "",
                public_profile=row[17] or "",
            )
            rules.normalize_profile(profile)
            out[profile.cell_id] = profile
    return out


def write_district_updates(paths, districts, report, affected_ids=None):
    affected = set(affected_ids or districts)
    fields = [
        "cell_id",
        "population",
        "prosperity",
        "unrest",
        "culture",
        "risk",
        "services",
        "land_use",
        "zoning_overlay",
        "display_state",
        "service_gap_json",
        "population_mix_json",
        "dissatisfaction_json",
        "incident_state",
        "incident_group",
        "public_profile",
        "last_report",
    ]
    with arcpy.da.UpdateCursor(paths["districts"], fields) as cursor:
        for row in cursor:
            cid = row[0]
            if cid not in districts:
                continue
            profile = districts[cid]
            rules.normalize_profile(profile)
            row[1] = profile.population
            row[2] = profile.prosperity
            row[3] = profile.unrest
            row[4] = profile.culture
            row[5] = profile.risk
            row[6] = profile.services
            row[7] = profile.land_use
            row[8] = profile.zoning_overlay
            row[9] = profile.display_state
            row[10] = encode_service_gap(profile.service_gap)
            row[11] = encode_group_bands(profile.population_mix, maximum=3)
            row[12] = encode_group_bands(profile.dissatisfaction, maximum=4)
            row[13] = profile.incident_state
            row[14] = profile.incident_group
            row[15] = profile.public_profile
            if cid in affected:
                row[16] = report[:512]
            cursor.updateRow(row)


def generate_docket_rows(paths, seed, messages):
    state = read_state(paths)
    districts = read_districts(paths)
    arcpy.management.DeleteRows(paths["docket"])
    items = rules.generate_docket(turn=state.turn, seed=seed, count=3, state=state, districts=districts)
    fields = [
        "item_id",
        "turn",
        "template_id",
        "title",
        "geometry_type",
        "status",
        "inspected",
        "target_cell_ids",
        "preview_text",
        "risk_band",
        "carryover",
        "stakeholder",
        "origin_item_id",
        "target_rule",
    ]
    with arcpy.da.InsertCursor(paths["docket"], fields) as cursor:
        for item in items:
            cursor.insertRow([
                item.item_id,
                item.turn,
                item.template_id,
                item.title,
                item.geometry_type,
                item.status,
                1 if item.inspected else 0,
                ",".join(item.target_cell_ids),
                item.preview_text,
                item.risk_band,
                item.carryover,
                item.stakeholder,
                item.origin_item_id,
                item.target_rule,
            ])
    _log(messages, "DOCKET", f"generated {len(items)} docket item(s) for turn {state.turn}")
    return items


def read_docket(paths):
    items = []
    fields = [
        "item_id",
        "turn",
        "template_id",
        "title",
        "geometry_type",
        "status",
        "inspected",
        "target_cell_ids",
        "preview_text",
        "risk_band",
        "carryover",
        "stakeholder",
        "origin_item_id",
        "target_rule",
    ]
    with arcpy.da.SearchCursor(paths["docket"], fields) as cursor:
        for row in cursor:
            item = rules.DocketItem(
                item_id=row[0],
                template_id=row[2],
                title=row[3],
                geometry_type=row[4],
                turn=int(row[1] or 1),
                status=row[5] or "open",
                inspected=bool(row[6]),
                target_cell_ids=[part for part in (row[7] or "").split(",") if part],
                preview_text=row[8] or "",
                risk_band=row[9] or "unknown",
                carryover=row[10] or "expire_or_return",
                stakeholder=row[11] or "",
                origin_item_id=row[12] or "",
                target_rule=row[13] or "",
            )
            items.append(item)
    return items


def write_docket_item(paths, item):
    fields = ["item_id", "status", "inspected", "target_cell_ids", "preview_text", "risk_band", "carryover", "stakeholder", "origin_item_id", "target_rule"]
    with arcpy.da.UpdateCursor(paths["docket"], fields) as cursor:
        for row in cursor:
            if row[0] != item.item_id:
                continue
            row[1] = item.status
            row[2] = 1 if item.inspected else 0
            row[3] = ",".join(item.target_cell_ids)
            row[4] = item.preview_text
            row[5] = item.risk_band
            row[6] = item.carryover
            row[7] = item.stakeholder
            row[8] = item.origin_item_id
            row[9] = item.target_rule
            cursor.updateRow(row)
            return


def selected_cell_ids(layer):
    if not layer:
        return []
    has_selection = False
    try:
        fidset = arcpy.da.Describe(layer).get("FIDSet")
        if isinstance(fidset, (list, tuple, set)):
            has_selection = bool(fidset)
        elif isinstance(fidset, str):
            has_selection = bool(fidset.strip())
        elif fidset:
            has_selection = True
    except Exception:
        try:
            fidset = getattr(arcpy.Describe(layer), "FIDSet", None)
            has_selection = bool(str(fidset).strip()) if fidset is not None else False
        except Exception:
            has_selection = False
    if not has_selection:
        return []
    fields = {field.name.lower(): field.name for field in arcpy.ListFields(layer)}
    cell_field = fields.get("cell_id")
    if not cell_field:
        return []
    return [row[0] for row in arcpy.da.SearchCursor(layer, [cell_field])]


def district_geometry_lookup(paths):
    lookup = {}
    with arcpy.da.SearchCursor(paths["districts"], ["cell_id", "SHAPE@"]) as cursor:
        for cid, geom in cursor:
            lookup[cid] = geom
    return lookup


def insert_or_replace_proposal(paths, item, target_ids, messages):
    for fc in (paths["points"], paths["lines"], paths["zones"]):
        with arcpy.da.UpdateCursor(fc, ["item_id", "status"]) as cursor:
            for row in cursor:
                if row[1] == "proposed":
                    cursor.deleteRow()

    template = rules.TEMPLATES[item.template_id]
    archetype = rules.feature_archetype_for_template(template)
    metadata = rules.feature_metadata_for_template(template)
    geoms = district_geometry_lookup(paths)
    valid = [cid for cid in target_ids if cid in geoms]
    if item.geometry_type == "POINT" and len(valid) != 1:
        raise ValueError("Point permits require exactly one selected district.")
    if item.geometry_type == "LINE" and len(valid) != 2:
        raise ValueError("Line permits require exactly two selected districts.")
    if item.geometry_type == "POLYGON" and not valid:
        raise ValueError("Zone permits require one or more selected districts.")

    feature_id = str(uuid.uuid4())
    target_text = ",".join(valid)
    attrs = [
        feature_id,
        item.item_id,
        item.template_id,
        item.title,
        template.category,
        archetype.archetype_id,
        archetype.family,
        archetype.service_type,
        float(archetype.coverage_radius_m),
        archetype.capacity,
        archetype.land_use,
        archetype.incident_type,
        item.stakeholder or template.stakeholder,
        max(1, archetype.capacity or 1),
        json.dumps(metadata, sort_keys=True)[:2048],
        "proposed",
        item.turn,
        item.turn + template.expires_after if template.expires_after else -1,
        target_text,
        "proposed",
        template.preview,
    ]
    if item.geometry_type == "POINT":
        geom = arcpy.PointGeometry(geoms[valid[0]].centroid, geoms[valid[0]].spatialReference)
        fc = paths["points"]
    elif item.geometry_type == "LINE":
        p1 = geoms[valid[0]].centroid
        p2 = geoms[valid[1]].centroid
        geom = arcpy.Polyline(arcpy.Array([p1, p2]), geoms[valid[0]].spatialReference)
        fc = paths["lines"]
    else:
        geom = inset_polygon(geoms[valid[0]])
        fc = paths["zones"]

    with arcpy.da.InsertCursor(fc, ["SHAPE@"] + [field[0] for field in SUPPORT_FIELDS]) as cursor:
        cursor.insertRow([geom] + attrs)
    item.target_cell_ids = valid
    write_docket_item(paths, item)
    _log(messages, "PREVIEW", f"created proposed {item.geometry_type.lower()} for {item.item_id}: {target_text}")
    return valid


def inset_polygon(geom):
    extent = geom.extent
    width = max(10.0, (extent.XMax - extent.XMin) * 0.58)
    height = max(10.0, (extent.YMax - extent.YMin) * 0.58)
    cx = (extent.XMin + extent.XMax) / 2.0
    cy = (extent.YMin + extent.YMax) / 2.0
    arr = arcpy.Array([
        arcpy.Point(cx - width / 2, cy - height / 2),
        arcpy.Point(cx + width / 2, cy - height / 2),
        arcpy.Point(cx + width / 2, cy + height / 2),
        arcpy.Point(cx - width / 2, cy + height / 2),
        arcpy.Point(cx - width / 2, cy - height / 2),
    ])
    return arcpy.Polygon(arr, geom.spatialReference)


def proposal_spillover(paths, item):
    proposed_fc = {"POINT": paths["points"], "LINE": paths["lines"], "POLYGON": paths["zones"]}[item.geometry_type]
    where = "item_id = '{0}' AND status = 'proposed'".format(item.item_id.replace("'", "''"))
    layer_name = f"proposal_{uuid.uuid4().hex[:8]}"
    arcpy.management.MakeFeatureLayer(proposed_fc, layer_name, where)
    buffer_fc = r"memory\permit_office_spillover"
    if arcpy.Exists(buffer_fc):
        arcpy.management.Delete(buffer_fc)
    archetype = rules.feature_archetype_for_template(item.template_id)
    radius = max(1, int(archetype.coverage_radius_m or 125))
    arcpy.analysis.Buffer(layer_name, buffer_fc, f"{radius} Meters")
    district_layer = f"district_spill_{uuid.uuid4().hex[:8]}"
    arcpy.management.MakeFeatureLayer(paths["districts"], district_layer)
    arcpy.management.SelectLayerByLocation(district_layer, "INTERSECT", buffer_fc, selection_type="NEW_SELECTION")
    ids = selected_cell_ids(district_layer)
    arcpy.management.Delete(layer_name)
    arcpy.management.Delete(district_layer)
    if arcpy.Exists(buffer_fc):
        arcpy.management.Delete(buffer_fc)
    return ids


def activate_proposal(paths, item, report):
    fc = {"POINT": paths["points"], "LINE": paths["lines"], "POLYGON": paths["zones"]}[item.geometry_type]
    fields = ["item_id", "status", "display_state", "report"]
    status = item.status if item.status in ("active", "failed", "enforced", "settled") else "active"
    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        for row in cursor:
            if row[0] == item.item_id and row[1] == "proposed":
                row[1] = status
                row[2] = status
                row[3] = report[:1024]
                cursor.updateRow(row)


def mark_proposals(paths, item_id, status, report=""):
    for fc in (paths["points"], paths["lines"], paths["zones"]):
        with arcpy.da.UpdateCursor(fc, ["item_id", "status", "display_state", "report"]) as cursor:
            for row in cursor:
                if row[0] == item_id and row[1] == "proposed":
                    row[1] = status
                    row[2] = status
                    row[3] = report[:1024]
                    cursor.updateRow(row)


def command_insert(paths, action, item_id, target_ids, payload=None):
    command_id = str(uuid.uuid4())
    fields = ["command_id", "created_utc", "action", "item_id", "status", "attempt_count", "target_cell_ids", "payload_json", "message"]
    with arcpy.da.InsertCursor(paths["commands"], fields) as cursor:
        cursor.insertRow([command_id, now_utc(), action, item_id, "created", 0, ",".join(target_ids), json.dumps(payload or {})[:4000], "created"])
    return command_id


def command_finish(paths, command_id, status, message="", error=""):
    fields = ["command_id", "finished_utc", "status", "attempt_count", "message", "error_message"]
    with arcpy.da.UpdateCursor(paths["commands"], fields) as cursor:
        for row in cursor:
            if row[0] != command_id:
                continue
            row[1] = now_utc()
            row[2] = status
            row[3] = (row[3] or 0) + 1
            row[4] = message[:1024]
            row[5] = error[:1024]
            cursor.updateRow(row)
            return


def action_log(paths, state, result):
    with arcpy.da.InsertCursor(paths["action_log"], ["created_utc", "turn", "action", "item_id", "target_cell_ids", "result", "city_delta"]) as cursor:
        cursor.insertRow([
            now_utc(),
            state.turn,
            result.action,
            result.item_id,
            ",".join(result.affected_cell_ids),
            result.report[:2048],
            json.dumps(result.city_delta)[:512],
        ])


def refresh_all(paths, messages):
    for name in (DISTRICTS, POINTS, LINES, ZONES):
        try:
            arcpy.RefreshLayer(name)
            _log(messages, "REFRESH", f"RefreshLayer({name!r}) OK")
        except Exception as exc:
            _warn(messages, "REFRESH", f"RefreshLayer({name!r}) failed: {exc}")


def add_outputs_to_map(paths, messages):
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap
        if active_map is None:
            return
        existing = {lyr.name: lyr for lyr in active_map.listLayers()}
        for name, key in ((DISTRICTS, "districts"), (POINTS, "points"), (LINES, "lines"), (ZONES, "zones")):
            if name not in existing:
                lyr = active_map.addDataFromPath(paths[key])
                lyr.name = name
                existing[name] = lyr
                _log(messages, "MAP", f"added {name}")
            apply_simple_symbology(existing[name], key, messages)
    except Exception as exc:
        _warn(messages, "MAP", f"add outputs failed: {exc}")


def apply_simple_symbology(layer, key, messages):
    try:
        if not layer.supports("SYMBOLOGY"):
            return
        sym = layer.symbology
        sym.updateRenderer("UniqueValueRenderer")
        sym.renderer.fields = ["display_state"]
        try:
            sym.renderer.useDefaultSymbol = True
        except Exception:
            pass
        layer.symbology = sym
    except Exception as exc:
        _warn(messages, "SYM", f"symbology setup skipped for {getattr(layer, 'name', key)}: {exc}")


def open_effect_report(title, report, affected, state):
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return
    root = tk.Toplevel()
    root.title("Permit Effect Report")
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(frame, text=title, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
    ttk.Label(frame, text=report, wraplength=560).grid(row=1, column=0, sticky="w", pady=4)
    ttk.Label(frame, text=f"Affected districts: {', '.join(affected) if affected else '(none)'}", wraplength=560).grid(row=2, column=0, sticky="w", pady=4)
    metrics = f"AP {state.ap}/{state.max_ap} | ${state.money} | Prosperity {state.prosperity} | Unrest {state.unrest} | Culture {state.culture} | Risk {state.risk} | Heat {rules.heat_summary(state)}"
    ttk.Label(frame, text=metrics, wraplength=560).grid(row=3, column=0, sticky="w", pady=4)
    ttk.Button(frame, text="Close", command=root.destroy).grid(row=4, column=0, sticky="e", pady=(10, 0))
    root.grab_set()
    root.wait_window()


class DashboardController:
    def __init__(self, paths, district_layer, seed, messages):
        self.paths = paths
        self.district_layer = district_layer
        self.seed = seed
        self.messages = messages

    def open(self):
        try:
            import tkinter as tk
            from tkinter import ttk
        except Exception as exc:
            raise RuntimeError(f"tkinter is not available: {exc}")

        self.root = tk.Tk()
        self.root.title("Permit Office")
        self.root.geometry("760x520")
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        self.item_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.metrics_var = tk.StringVar()
        self.detail_var = tk.StringVar()

        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Permit Office", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.metrics_var).grid(row=0, column=1, sticky="e")

        ttk.Label(frame, text="Active docket item").grid(row=1, column=0, sticky="w", pady=(12, 2))
        self.combo = ttk.Combobox(frame, textvariable=self.item_var, state="readonly", width=54)
        self.combo.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.combo.bind("<<ComboboxSelected>>", lambda _evt: self.refresh_detail())

        ttk.Label(frame, textvariable=self.detail_var, wraplength=720, justify="left").grid(row=3, column=0, columnspan=2, sticky="w", pady=10)

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)
        for text, command in (
            ("Preview From Selection", self.preview_selected),
            ("Inspect", self.inspect),
            ("Approve", lambda: self.apply_decision("approve", False)),
            ("Approve + Mitigate", lambda: self.apply_decision("approve_mitigated", True)),
            ("Deny", self.deny),
            ("Advance Turn", self.advance_turn),
        ):
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 6), pady=3)

        ttk.Label(frame, textvariable=self.status_var, wraplength=720).grid(row=5, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(frame, text="Close", command=self.root.destroy).grid(row=6, column=1, sticky="e", pady=(18, 0))

        self.reload()
        self.root.mainloop()

    def reload(self):
        state = read_state(self.paths)
        districts = read_districts(self.paths)
        items = read_docket(self.paths)
        labels = [self.item_label(item) for item in items if item.status in ("open", "inspected", "active", "carried")]
        self.combo["values"] = labels
        if labels and self.item_var.get() not in labels:
            self.item_var.set(labels[0])
        heat = rules.heat_summary(state)
        population = rules.population_city_summary(districts)
        incidents = rules.incident_summary(districts)
        self.metrics_var.set(
            f"Turn {state.turn}/6 | AP {state.ap}/{state.max_ap} | ${state.money} | P {state.prosperity} U {state.unrest} C {state.culture} R {state.risk} | {population} | Heat {heat} | Incidents {incidents}"
        )
        self.refresh_detail()

    def item_label(self, item):
        return f"{item.item_id} | {item.geometry_type} | {item.status} | {item.title}"

    def active_item(self):
        selected = self.item_var.get()
        if not selected:
            return None
        item_id = selected.split(" | ", 1)[0]
        for item in read_docket(self.paths):
            if item.item_id == item_id:
                return item
        return None

    def refresh_detail(self):
        item = self.active_item()
        if not item:
            self.detail_var.set("No active docket item.")
            return
        state = read_state(self.paths)
        template = rules.TEMPLATES[item.template_id]
        archetype = rules.feature_archetype_for_template(template)
        stakeholder = item.stakeholder or template.stakeholder
        target_rule = item.target_rule or template.target_rule
        heat = state.stakeholder_heat.get(stakeholder, 0)
        districts = read_districts(self.paths)
        target_profiles = [districts[cid] for cid in item.target_cell_ids if cid in districts]
        population_hint = rules.target_population_hint(item, target_profiles)
        population_line = f"\n{population_hint}" if population_hint else ""
        action_note = "Approve=enforce; Approve + Mitigate=settle/retro-permit; Deny=defer." if template.is_enforcement else "Approve=issue permit; Approve + Mitigate=issue with conditions; Deny=reject."
        if template.is_incident:
            action_note = "Approve=formal response; Approve + Mitigate=settle/service response; Deny=defer incident."
        text = (
            f"{item.title}\n"
            f"Type: {template.category}; geometry: {item.geometry_type}; stakeholder: {stakeholder.replace('_', ' ')}; heat: {heat}\n"
            f"Feature: {archetype.label}; family: {archetype.family}; service: {archetype.service_type or 'none'}; land use: {archetype.land_use or 'none'}\n"
            f"Cost: {template.ap_cost} AP / ${template.money_cost}; mitigation +${template.mitigation_cost}\n"
            f"Target rule: {target_rule}\n"
            f"Failure mode: {template.failure_mode or 'none filed'}\n"
            f"Contact: {template.contact_name or 'not assigned'}\n"
            f"Actions: {action_note}\n"
            f"Targets: {', '.join(item.target_cell_ids) if item.target_cell_ids else '(select on map, then preview)'}\n"
            f"{item.preview_text}{population_line}"
        )
        self.detail_var.set(text)

    def preview_selected(self):
        item = self.active_item()
        if not item:
            return
        try:
            selected = selected_cell_ids(self.district_layer)
            target_ids = insert_or_replace_proposal(self.paths, item, selected, self.messages)
            refresh_all(self.paths, self.messages)
            self.status_var.set(f"Previewed {item.title} for {', '.join(target_ids)}.")
            self.reload()
        except Exception as exc:
            self.status_var.set(f"Preview failed: {exc}")
            _warn(self.messages, "DASH", traceback.format_exc().strip().splitlines()[-1])

    def inspect(self):
        item = self.active_item()
        if not item:
            return
        command_id = command_insert(self.paths, "inspect", item.item_id, item.target_cell_ids)
        try:
            state = read_state(self.paths)
            districts = read_districts(self.paths)
            result = rules.resolve_decision(state, item, districts, "inspect", item.target_cell_ids, seed=self.seed)
            write_state(self.paths, state)
            write_docket_item(self.paths, item)
            action_log(self.paths, state, result)
            command_finish(self.paths, command_id, result.command_status, result.report)
            self.status_var.set(result.report)
            open_effect_report(item.title, result.report, result.affected_cell_ids, state)
        except Exception as exc:
            command_finish(self.paths, command_id, "error", error=str(exc))
            self.status_var.set(f"Inspect failed: {exc}")
        self.reload()

    def apply_decision(self, action, mitigated):
        item = self.active_item()
        if not item:
            return
        command_id = command_insert(self.paths, action, item.item_id, item.target_cell_ids)
        try:
            if not item.target_cell_ids:
                selected = selected_cell_ids(self.district_layer)
                insert_or_replace_proposal(self.paths, item, selected, self.messages)
            spillover = proposal_spillover(self.paths, item)
            state = read_state(self.paths)
            districts = read_districts(self.paths)
            result = rules.resolve_decision(
                state,
                item,
                districts,
                action,
                item.target_cell_ids,
                spillover,
                seed=self.seed,
                mitigated=mitigated,
            )
            if not result.ok:
                command_finish(self.paths, command_id, "error", result.report, result.report)
                self.status_var.set(result.report)
                self.reload()
                return
            activate_proposal(self.paths, item, result.report)
            write_district_updates(self.paths, districts, result.report, result.affected_cell_ids)
            write_state(self.paths, state)
            write_docket_item(self.paths, item)
            action_log(self.paths, state, result)
            command_finish(self.paths, command_id, result.command_status, result.report)
            refresh_all(self.paths, self.messages)
            self.status_var.set(result.report)
            open_effect_report(item.title, result.report, result.affected_cell_ids, state)
        except Exception as exc:
            command_finish(self.paths, command_id, "error", error=str(exc))
            self.status_var.set(f"Approve failed: {exc}")
            _warn(self.messages, "DASH", traceback.format_exc().strip().splitlines()[-1])
        self.reload()

    def deny(self):
        item = self.active_item()
        if not item:
            return
        command_id = command_insert(self.paths, "deny", item.item_id, item.target_cell_ids)
        try:
            state = read_state(self.paths)
            districts = read_districts(self.paths)
            result = rules.resolve_decision(state, item, districts, "deny", item.target_cell_ids, seed=self.seed)
            if not result.ok:
                command_finish(self.paths, command_id, "error", result.report, result.report)
                self.status_var.set(result.report)
                self.reload()
                return
            proposal_status = item.status if item.status in ("denied", "deferred") else "denied"
            mark_proposals(self.paths, item.item_id, proposal_status, result.report)
            write_district_updates(self.paths, districts, result.report, result.affected_cell_ids)
            write_state(self.paths, state)
            write_docket_item(self.paths, item)
            action_log(self.paths, state, result)
            command_finish(self.paths, command_id, result.command_status, result.report)
            refresh_all(self.paths, self.messages)
            self.status_var.set(result.report)
            open_effect_report(item.title, result.report, result.affected_cell_ids, state)
        except Exception as exc:
            command_finish(self.paths, command_id, "error", error=str(exc))
            self.status_var.set(f"Deny failed: {exc}")
        self.reload()

    def advance_turn(self):
        command_id = command_insert(self.paths, "advance_turn", "", [])
        try:
            state = read_state(self.paths)
            items = read_docket(self.paths)
            districts = read_districts(self.paths)
            report = rules.advance_turn(state, items, districts)
            write_state(self.paths, state)
            write_district_updates(self.paths, districts, report)
            for item in items:
                write_docket_item(self.paths, item)
            generate_docket_rows(self.paths, self.seed, self.messages)
            command_finish(self.paths, command_id, "applied", report)
            refresh_all(self.paths, self.messages)
            self.status_var.set(report)
        except Exception as exc:
            command_finish(self.paths, command_id, "error", error=str(exc))
            self.status_var.set(f"Advance failed: {exc}")
        self.reload()


class Toolbox(object):
    def __init__(self):
        self.label = TOOLBOX_LABEL
        self.alias = TOOLBOX_ALIAS
        self.tools = [PermitOfficePrototype]


class PermitOfficePrototype(object):
    def __init__(self):
        self.label = "Permit Office Prototype"
        self.description = "Generated-district permit office dashboard prototype."
        self.canRunInBackground = False

    def getParameterInfo(self):
        p_workspace = arcpy.Parameter("Game Workspace (optional)", "game_workspace", "DEWorkspace", "Optional", "Input")
        p_districts = arcpy.Parameter("District Layer", "district_layer", "GPFeatureLayer", "Optional", "Input")
        p_action = arcpy.Parameter("Action", "action", "GPString", "Required", "Input")
        p_action.filter.type = "ValueList"
        p_action.filter.list = list(ACTIONS)
        p_action.value = "Ping Environment"
        p_seed = arcpy.Parameter("Random Seed", "random_seed", "GPLong", "Optional", "Input")
        p_seed.value = 2026
        p_output = arcpy.Parameter("Output District Layer", "output_district_layer", "GPFeatureLayer", "Derived", "Output")
        return [p_workspace, p_districts, p_action, p_seed, p_output]

    def updateParameters(self, parameters):
        action = parameters[P_ACTION].valueAsText
        parameters[P_DISTRICTS].enabled = action == "Open Dashboard"

    def execute(self, parameters, messages):
        action = parameters[P_ACTION].valueAsText or "Ping Environment"
        seed = int(parameters[P_SEED].value or 2026)
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        paths = ensure_schema(gdb_path, messages)

        if action == "Ping Environment":
            _log(messages, "PING", f"workspace = {gdb_path}")
            _log(messages, "PING", f"templates = {', '.join(sorted(rules.TEMPLATES))}")
            return
        if action == "New Game":
            clear_game_rows(paths)
            create_district_board(paths, seed, messages)
            write_state(paths, rules.CityState())
            generate_docket_rows(paths, seed, messages)
            add_outputs_to_map(paths, messages)
            refresh_all(paths, messages)
            arcpy.SetParameterAsText(P_OUTPUT, paths["districts"])
            return
        if action == "Generate Docket":
            generate_docket_rows(paths, seed, messages)
            refresh_all(paths, messages)
            return
        if action == "Show Scorecard":
            state = read_state(paths)
            districts = read_districts(paths)
            grade, report = rules.scorecard(state)
            _log(messages, "AUDIT", f"{report} {rules.population_city_summary(districts)}; incidents={rules.incident_summary(districts)}.")
            return
        if action == "Open Dashboard":
            district_layer = parameters[P_DISTRICTS].value or paths["districts"]
            add_outputs_to_map(paths, messages)
            if int(arcpy.management.GetCount(paths["districts"])[0]) == 0:
                _err(messages, "DASH", "Run New Game before opening the dashboard.")
                return
            if int(arcpy.management.GetCount(paths["docket"])[0]) == 0:
                generate_docket_rows(paths, seed, messages)
            DashboardController(paths, district_layer, seed, messages).open()
            arcpy.SetParameterAsText(P_OUTPUT, paths["districts"])
            return
        _err(messages, "DISPATCH", f"unknown action: {action}")
