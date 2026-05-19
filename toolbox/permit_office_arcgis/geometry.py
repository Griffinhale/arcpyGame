"""ArcGIS geometry operations for previews, activation, and map refresh."""

from __future__ import annotations

import json
import uuid

import arcpy

from .messages import _log, _warn
from .rules_loader import rules
from .schema import DISTRICTS, LINES, POINTS, SUPPORT_FIELDS, ZONES
from .store import encode_json, write_docket_item


def _summary_map(value):
    """Format a compact sorted metadata map for ArcGIS text fields."""

    if not isinstance(value, dict) or not value:
        return ""
    return ", ".join(f"{key} {amount}" for key, amount in sorted(value.items()))[:512]

def selected_cell_ids(layer):
    """Return selected district IDs from a layer, or an empty list."""

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
    """Read district geometries keyed by cell ID."""

    lookup = {}
    with arcpy.da.SearchCursor(paths["districts"], ["cell_id", "SHAPE@"]) as cursor:
        for cid, geom in cursor:
            lookup[cid] = geom
    return lookup


def insert_or_replace_proposal(paths, item, target_ids, messages):
    """Create the proposed point, line, or polygon feature for a docket item."""

    # Only one proposed exhibit should exist at a time; the active docket item
    # owns the preview geometry the dashboard will later approve or deny.
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

    # The proposed ArcGIS row carries a normalized FeatureInstance payload so
    # lifecycle systems can read the same fields after approval.
    feature_id = str(uuid.uuid4())
    target_text = ",".join(valid)
    expires_turn = item.turn + template.expires_after if template.expires_after else -1
    feature_state = rules.FeatureInstance(
        feature_id=feature_id,
        item_id=item.item_id,
        template_id=item.template_id,
        archetype_id=archetype.archetype_id,
        family=archetype.family,
        service_type=archetype.service_type,
        network_type=archetype.network_type or archetype.service_type,
        owner_group=item.stakeholder or template.stakeholder,
        target_cell_ids=valid,
        capacity=archetype.capacity,
        intensity=max(1, archetype.capacity or 1),
        status="proposed",
        turn_created=item.turn,
        expires_turn=expires_turn,
        display_state="proposed",
        project_id=item.project_id,
        chain_step_id=item.chain_step_id,
        metadata=metadata,
    )
    rules.normalize_feature_instance(feature_state, item.turn)
    feature_state.status = "proposed"
    feature_state.display_state = "proposed"
    attrs = [
        feature_id,
        item.item_id,
        item.template_id,
        item.project_id,
        item.chain_step_id,
        item.title,
        template.category,
        archetype.archetype_id,
        archetype.family,
        archetype.service_type,
        archetype.network_type or archetype.service_type,
        float(archetype.coverage_radius_m),
        archetype.capacity,
        archetype.land_use,
        archetype.incident_type,
        item.stakeholder or template.stakeholder,
        max(1, archetype.capacity or 1),
        json.dumps(metadata, sort_keys=True)[:2048],
        _summary_map(metadata.get("hazard_effects")),
        _summary_map(metadata.get("mitigation_effects")),
        "proposed",
        item.turn,
        expires_turn,
        target_text,
        "proposed",
        template.preview,
        feature_state.condition,
        feature_state.maintenance_due_turn,
        feature_state.last_maintained_turn,
        encode_json(feature_state.state_json),
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
        # Zone proposals use a smaller display polygon within the first selected
        # district because the gameplay target list carries the full selection.
        geom = inset_polygon(geoms[valid[0]])
        fc = paths["zones"]

    with arcpy.da.InsertCursor(fc, ["SHAPE@"] + [field[0] for field in SUPPORT_FIELDS]) as cursor:
        cursor.insertRow([geom] + attrs)
    item.target_cell_ids = valid
    write_docket_item(paths, item)
    _log(messages, "PREVIEW", f"created proposed {item.geometry_type.lower()} for {item.item_id}: {target_text}")
    return valid


def inset_polygon(geom):
    """Return a smaller polygon centered inside a district geometry."""

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
    """Find districts touched by the proposed feature's coverage buffer."""

    proposed_fc = {"POINT": paths["points"], "LINE": paths["lines"], "POLYGON": paths["zones"]}[item.geometry_type]
    where = "item_id = '{0}' AND status = 'proposed'".format(item.item_id.replace("'", "''"))
    layer_name = f"proposal_{uuid.uuid4().hex[:8]}"
    arcpy.management.MakeFeatureLayer(proposed_fc, layer_name, where)
    buffer_fc = r"memory\permit_office_spillover"
    if arcpy.Exists(buffer_fc):
        arcpy.management.Delete(buffer_fc)
    archetype = rules.feature_archetype_for_template(item.template_id)
    radius = max(1, int(archetype.coverage_radius_m or 125))
    # ArcGIS does the geometric spillover calculation; the rules layer only sees
    # the resulting district ids.
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
    """Convert a proposed support feature into its resolved gameplay status."""

    fc = {"POINT": paths["points"], "LINE": paths["lines"], "POLYGON": paths["zones"]}[item.geometry_type]
    fields = ["item_id", "feature_id", "archetype_id", "project_id", "chain_step_id", "turn_created", "expires_turn", "status", "display_state", "report", "condition", "maintenance_due_turn", "last_maintained_turn", "state_json"]
    status = item.status if item.status in ("active", "failed", "enforced", "settled", "responded", "maintained") else "active"
    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        for row in cursor:
            if row[0] == item.item_id and row[7] == "proposed":
                # Rehydrate the lifecycle fields before writing status so
                # approval, failure, and maintenance state stay normalized.
                feature = rules.FeatureInstance(
                    feature_id=row[1],
                    archetype_id=row[2],
                    project_id=item.project_id or row[3] or "",
                    chain_step_id=item.chain_step_id or row[4] or "",
                    status=status,
                    turn_created=int(row[5] or item.turn),
                    expires_turn=int(row[6] if row[6] not in (None, "") else -1),
                    condition=int(row[10] if row[10] not in (None, "") else 100),
                    maintenance_due_turn=int(row[11] if row[11] not in (None, "") else -1),
                    last_maintained_turn=int(row[12] or 0),
                    state_json=decode_json(row[13]),
                )
                rules.normalize_feature_instance(feature, item.turn)
                feature.status = status
                feature.display_state = status
                row[3] = feature.project_id
                row[4] = feature.chain_step_id
                row[7] = feature.status
                row[8] = feature.display_state
                row[9] = report[:1024]
                row[10] = feature.condition
                row[11] = feature.maintenance_due_turn
                row[12] = feature.last_maintained_turn
                row[13] = encode_json(feature.state_json)
                cursor.updateRow(row)


def mark_proposals(paths, item_id, status, report=""):
    """Mark unresolved proposal features as denied, deferred, or otherwise closed."""

    for fc in (paths["points"], paths["lines"], paths["zones"]):
        with arcpy.da.UpdateCursor(fc, ["item_id", "status", "display_state", "report"]) as cursor:
            for row in cursor:
                if row[0] == item_id and row[1] == "proposed":
                    row[1] = status
                    row[2] = status
                    row[3] = report[:1024]
                    cursor.updateRow(row)


def refresh_all(paths, messages):
    """Refresh all known map layers after persisted game changes."""

    for name in (DISTRICTS, POINTS, LINES, ZONES):
        try:
            arcpy.RefreshLayer(name)
            _log(messages, "REFRESH", f"RefreshLayer({name!r}) OK")
        except Exception as exc:
            _warn(messages, "REFRESH", f"RefreshLayer({name!r}) failed: {exc}")


def add_outputs_to_map(paths, messages):
    """Add active game outputs to the current ArcGIS map when missing."""

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
    """Apply display-state unique-value symbology when the layer supports it."""

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
