"""ArcGIS geometry operations for previews, activation, and map refresh."""

from __future__ import annotations

import json
import random
import uuid

import arcpy

from .messages import _log, _warn
from .rules_loader import rules
from .schema import DISTRICTS, LINES, POINTS, SUPPORT_FIELDS, ZONES
from .store import decode_json, encode_json, read_districts, write_docket_item


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


def ensure_case_proposal(paths, item, seed, messages, target_ids=None) -> list[str]:
    """Ensure an unresolved docket item has a proposed exhibit row."""

    if item.status not in ("open", "inspected", "carried"):
        return list(item.target_cell_ids or ())
    if target_ids is not None:
        return insert_or_replace_proposal(paths, item, list(target_ids), messages)

    existing = _case_proposal_targets(paths, item.item_id)
    if existing:
        if not item.target_cell_ids:
            item.target_cell_ids = existing
            _try_write_docket_item(paths, item, messages)
        return existing

    districts = _district_records(paths)
    targets = list(item.target_cell_ids or _suggest_targets(item, districts, seed))
    return insert_or_replace_proposal(paths, item, targets, messages)


def hide_case_proposal(paths, item_id) -> bool:
    """Remove the selected unresolved proposal without touching city features."""

    hidden = False
    for fc in (paths["points"], paths["lines"], paths["zones"]):
        with arcpy.da.UpdateCursor(fc, ["item_id", "status"]) as cursor:
            for row in cursor:
                if row[0] == item_id and row[1] == "proposed":
                    cursor.deleteRow()
                    hidden = True
    return hidden


def case_proposal_visible(paths, item) -> bool:
    """Return whether a docket item's unresolved proposal is present on the map."""

    item_id = getattr(item, "item_id", item)
    return bool(_case_proposal_targets(paths, item_id))


def select_case_context(paths, district_layer, item, seed, messages) -> None:
    """Select the docket item's proposal, target districts, and referenced feature."""

    targets = ensure_case_proposal(paths, item, seed, messages)
    _select_district_targets(district_layer, targets, messages)
    _select_support_context(paths, item, messages)


def district_geometry_lookup(paths):
    """Read district geometries keyed by cell ID."""

    lookup = {}
    with arcpy.da.SearchCursor(paths["districts"], ["cell_id", "SHAPE@"]) as cursor:
        for cid, geom in cursor:
            lookup[cid] = geom
    return lookup


def _case_proposal_targets(paths, item_id):
    """Return stored target IDs for the first proposed row matching an item."""

    for fc in (paths["points"], paths["lines"], paths["zones"]):
        with arcpy.da.SearchCursor(fc, ["item_id", "status", "target_cell_ids"]) as cursor:
            for row in cursor:
                if row[0] == item_id and row[1] == "proposed":
                    return [part for part in (row[2] or "").split(",") if part]
    return []


def _try_write_docket_item(paths, item, messages):
    """Persist target IDs when proposal rows reveal older docket state."""

    try:
        write_docket_item(paths, item)
    except Exception as exc:
        _warn(messages, "PREVIEW", f"could not persist targets for {item.item_id}: {exc}")


def _select_district_targets(district_layer, target_ids, messages):
    """Select target districts in ArcGIS using their cell IDs."""

    where = _where_in("cell_id", target_ids)
    _select_layer(district_layer, "NEW_SELECTION", where, messages, "district targets")


def _select_support_context(paths, item, messages):
    """Select proposal/support rows owned by this case and its subject feature."""

    parts = []
    if item.item_id:
        parts.append(_where_equals("item_id", item.item_id))
    if item.subject_feature_id:
        parts.append(_where_equals("feature_id", item.subject_feature_id))
    where = " OR ".join(parts) if parts else None
    for layer_name, path in ((POINTS, paths["points"]), (LINES, paths["lines"]), (ZONES, paths["zones"])):
        if not _select_layer(layer_name, "NEW_SELECTION", where, messages, layer_name, warn=False):
            _select_layer(path, "NEW_SELECTION", where, messages, path)


def _select_layer(layer, selection_type, where, messages, label, warn=True) -> bool:
    """Apply a selection expression, returning whether ArcPy accepted it."""

    try:
        if where:
            arcpy.management.SelectLayerByAttribute(layer, selection_type, where)
        else:
            arcpy.management.SelectLayerByAttribute(layer, "CLEAR_SELECTION")
        return True
    except Exception as exc:
        if warn:
            _warn(messages, "SELECT", f"{label} selection failed: {exc}")
        return False


def _where_in(field, values):
    """Build a simple ArcGIS SQL IN expression for text IDs."""

    clean = [str(value) for value in values or () if value]
    if not clean:
        return None
    if len(clean) == 1:
        return _where_equals(field, clean[0])
    return f"{field} IN ({', '.join(_sql_text(value) for value in clean)})"


def _where_equals(field, value):
    """Build a simple ArcGIS SQL equality expression for a text ID."""

    return f"{field} = {_sql_text(value)}"


def _sql_text(value):
    """Quote a text literal for simple ArcGIS SQL expressions."""

    return "'{0}'".format(str(value).replace("'", "''"))


def insert_or_replace_proposal(paths, item, target_ids, messages):
    """Create the proposed point, line, or polygon feature for a docket item."""

    # Each docket item owns one proposed exhibit. Other open docket proposals
    # stay visible so the map reads as a real in-tray instead of a single preview.
    for fc in (paths["points"], paths["lines"], paths["zones"]):
        with arcpy.da.UpdateCursor(fc, ["item_id", "status"]) as cursor:
            for row in cursor:
                if row[0] == item.item_id and row[1] == "proposed":
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

    attrs = _support_attrs(
        item=item,
        template=template,
        archetype=archetype,
        target_ids=valid,
        status="proposed",
        display_state="proposed",
        report=template.preview,
        metadata=metadata,
    )
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
    _log(messages, "PREVIEW", f"created proposed {item.geometry_type.lower()} for {item.item_id}: {','.join(valid)}")
    return valid


def seed_docket_proposals(paths, items, seed, messages):
    """Create a deterministic proposed map exhibit for each open docket item."""

    purge_proposed_features(paths)
    districts = _district_records(paths)
    for item in items:
        if item.status not in ("open", "inspected", "carried"):
            continue
        target_ids = item.target_cell_ids or _suggest_targets(item, districts, seed)
        try:
            insert_or_replace_proposal(paths, item, target_ids, messages)
        except Exception as exc:
            _warn(messages, "PREVIEW", f"could not seed proposal for {item.item_id}: {exc}")


def purge_proposed_features(paths):
    """Remove unresolved proposed features without touching active city rows."""

    for fc in (paths["points"], paths["lines"], paths["zones"]):
        with arcpy.da.UpdateCursor(fc, ["status"]) as cursor:
            for row in cursor:
                if row[0] == "proposed":
                    cursor.deleteRow()


def seed_city_features(paths, seed, messages):
    """Seed deterministic baseline city detail so the map starts populated."""

    if any(_feature_count(paths[key]) for key in ("points", "lines", "zones")):
        return
    districts = read_districts(paths)
    descriptors = rules.generate_city_detail_features(districts, seed=seed)
    inserted = 0
    for descriptor in descriptors:
        try:
            _insert_city_detail_feature(paths, descriptor)
            inserted += 1
        except Exception as exc:
            _warn(messages, "CITY", f"could not seed {descriptor.name}: {exc}")
    if inserted:
        active = sum(1 for feature in descriptors if feature.status == "active")
        context = sum(1 for feature in descriptors if feature.status == "context")
        _log(messages, "CITY", f"seeded {inserted} city detail feature(s): {active} active, {context} context")


def _district_records(paths):
    """Read district geometry and placement hints used for generated exhibits."""

    records = {}
    fields = ["cell_id", "district_type", "SHAPE@"]
    with arcpy.da.SearchCursor(paths["districts"], fields) as cursor:
        for cell_id, district_type, geom in cursor:
            records[cell_id] = {"district_type": district_type or "", "geom": geom}
    return records


def _suggest_targets(item, districts, seed):
    """Choose deterministic target districts matching the docket geometry."""

    template = rules.TEMPLATES[item.template_id]
    archetype = rules.feature_archetype_for_template(template)
    rng = random.Random(f"{seed}:{item.item_id}:proposal")
    scored = []
    for cell_id, record in districts.items():
        district_type = record["district_type"]
        score = 0
        if district_type in template.good_fit_types:
            score += 4
        if district_type in archetype.allowed_district_types:
            score += 3
        if district_type in template.bad_fit_types:
            score -= 4
        if district_type in archetype.conflict_district_types:
            score -= 3
        scored.append((-score, rng.random(), cell_id))
    ordered = [cell_id for _score, _tie, cell_id in sorted(scored)]
    if item.geometry_type == "POINT":
        return ordered[:1]
    if item.geometry_type == "LINE":
        if not ordered:
            return []
        first = ordered[0]
        adjacent = _adjacent_ids(first, districts)
        for cell_id in ordered[1:]:
            if cell_id in adjacent:
                return [first, cell_id]
        return ordered[:2]
    count = 2 if len(ordered) > 1 else 1
    return ordered[:count]


def _adjacent_ids(cell_id, districts):
    """Return generated-grid four-way neighbors present in the current board."""

    try:
        row = int(cell_id[1:3])
        col = int(cell_id[3:5])
    except Exception:
        return set()
    candidates = (
        f"D{row - 1:02d}{col:02d}",
        f"D{row + 1:02d}{col:02d}",
        f"D{row:02d}{col - 1:02d}",
        f"D{row:02d}{col + 1:02d}",
    )
    return {candidate for candidate in candidates if candidate in districts}


def _support_attrs(item, template, archetype, target_ids, status, display_state, report, metadata):
    """Build the shared support-feature attribute payload."""

    feature_id = str(uuid.uuid4())
    target_text = ",".join(target_ids)
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
        target_cell_ids=list(target_ids),
        capacity=archetype.capacity,
        intensity=max(1, archetype.capacity or 1),
        status=status,
        turn_created=item.turn,
        expires_turn=expires_turn,
        display_state=display_state,
        project_id=item.project_id,
        chain_step_id=item.chain_step_id,
        metadata=metadata,
    )
    rules.normalize_feature_instance(feature_state, item.turn)
    feature_state.status = status
    feature_state.display_state = display_state
    return [
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
        status,
        item.turn,
        expires_turn,
        target_text,
        display_state,
        report,
        feature_state.condition,
        feature_state.maintenance_due_turn,
        feature_state.last_maintained_turn,
        encode_json(feature_state.state_json),
    ]


def _insert_baseline_feature(paths, archetype_id, target_ids, name):
    """Insert one active baseline feature using an existing archetype shape."""

    archetype = rules.FEATURE_ARCHETYPES[archetype_id]
    template_id = _template_for_archetype(archetype_id)
    template = rules.TEMPLATES[template_id]
    item = rules.DocketItem(
        item_id=f"BASE-{archetype_id}",
        template_id=template_id,
        title=name,
        geometry_type=archetype.geometry_type,
        turn=0,
        status="active",
        target_cell_ids=list(target_ids),
        stakeholder="city",
    )
    geoms = district_geometry_lookup(paths)
    metadata = rules.feature_metadata_for_template(template)
    attrs = _support_attrs(
        item=item,
        template=template,
        archetype=archetype,
        target_ids=target_ids,
        status="active",
        display_state=archetype.display_state or "active",
        report="Existing city feature.",
        metadata=metadata,
    )
    if archetype.geometry_type == "POINT":
        geom = arcpy.PointGeometry(geoms[target_ids[0]].centroid, geoms[target_ids[0]].spatialReference)
        fc = paths["points"]
    elif archetype.geometry_type == "LINE":
        p1 = geoms[target_ids[0]].centroid
        p2 = geoms[target_ids[-1]].centroid
        geom = arcpy.Polyline(arcpy.Array([p1, p2]), geoms[target_ids[0]].spatialReference)
        fc = paths["lines"]
    else:
        geom = inset_polygon(geoms[target_ids[0]])
        fc = paths["zones"]
    with arcpy.da.InsertCursor(fc, ["SHAPE@"] + [field[0] for field in SUPPORT_FIELDS]) as cursor:
        cursor.insertRow([geom] + attrs)


def _insert_city_detail_feature(paths, descriptor):
    """Insert one generated city-detail descriptor into a support layer."""

    geoms = district_geometry_lookup(paths)
    targets = [cid for cid in descriptor.target_cell_ids if cid in geoms]
    if not targets:
        raise ValueError("city detail descriptor has no valid target district")
    archetype = rules.FEATURE_ARCHETYPES.get(descriptor.archetype_id)
    metadata = {
        "archetype_id": descriptor.archetype_id,
        "seeded_city_detail": True,
        **dict(descriptor.metadata or {}),
    }
    feature_state = rules.FeatureInstance(
        feature_id=descriptor.feature_id,
        item_id="",
        template_id="",
        archetype_id=descriptor.archetype_id,
        family=archetype.family if archetype else "",
        service_type=archetype.service_type if archetype else "",
        network_type=(archetype.network_type or archetype.service_type) if archetype else "",
        owner_group=descriptor.owner_group,
        target_cell_ids=targets,
        capacity=descriptor.capacity,
        intensity=descriptor.intensity,
        status=descriptor.status,
        turn_created=0,
        expires_turn=-1,
        display_state=descriptor.display_state,
        metadata=metadata,
        state_json=dict(descriptor.state or {}),
    )
    rules.normalize_feature_instance(feature_state, 0)
    feature_state.status = descriptor.status
    feature_state.display_state = descriptor.display_state
    if descriptor.geometry_type == "POINT":
        geom = _point_from_hint(geoms[targets[0]], descriptor.geometry_hint)
        fc = paths["points"]
    elif descriptor.geometry_type == "LINE":
        geom = _line_from_hint([geoms[cid] for cid in targets], descriptor.geometry_hint)
        fc = paths["lines"]
    else:
        geom = _rect_from_hint(geoms[targets[0]], descriptor.geometry_hint)
        fc = paths["zones"]
    attrs = [
        descriptor.feature_id,
        "",
        "",
        "",
        "",
        descriptor.name,
        "city_context",
        descriptor.archetype_id,
        feature_state.family,
        feature_state.service_type,
        feature_state.network_type,
        float(archetype.coverage_radius_m if archetype else 0),
        feature_state.capacity,
        archetype.land_use if archetype else "",
        archetype.incident_type if archetype else "",
        descriptor.owner_group,
        feature_state.intensity,
        encode_json(feature_state.metadata, limit=2048),
        _summary_map(archetype.hazard_effects if archetype else {}),
        _summary_map(archetype.mitigation_effects if archetype else {}),
        feature_state.status,
        feature_state.turn_created,
        feature_state.expires_turn,
        ",".join(targets),
        feature_state.display_state,
        "Seeded city detail.",
        feature_state.condition,
        feature_state.maintenance_due_turn,
        feature_state.last_maintained_turn,
        encode_json(feature_state.state_json),
    ]
    with arcpy.da.InsertCursor(fc, ["SHAPE@"] + [field[0] for field in SUPPORT_FIELDS]) as cursor:
        cursor.insertRow([geom] + attrs)


def _point_from_hint(geom, hint):
    """Create a point inside a district from normalized offsets."""

    extent = geom.extent
    x = extent.XMin + (extent.XMax - extent.XMin) * float(hint.get("x", 0.5))
    y = extent.YMin + (extent.YMax - extent.YMin) * float(hint.get("y", 0.5))
    return arcpy.PointGeometry(arcpy.Point(x, y), geom.spatialReference)


def _line_from_hint(geoms, hint):
    """Create a corridor or short street line from district geometry hints."""

    if len(geoms) == 1 and hint.get("shape") == "stub":
        extent = geoms[0].extent
        orientation = hint.get("orientation", "horizontal")
        offset = float(hint.get("offset", 0.5))
        if orientation == "vertical":
            x = extent.XMin + (extent.XMax - extent.XMin) * offset
            points = [arcpy.Point(x, extent.YMin + (extent.YMax - extent.YMin) * 0.18), arcpy.Point(x, extent.YMax - (extent.YMax - extent.YMin) * 0.18)]
        else:
            y = extent.YMin + (extent.YMax - extent.YMin) * offset
            points = [arcpy.Point(extent.XMin + (extent.XMax - extent.XMin) * 0.18, y), arcpy.Point(extent.XMax - (extent.XMax - extent.XMin) * 0.18, y)]
        return arcpy.Polyline(arcpy.Array(points), geoms[0].spatialReference)
    points = [geom.centroid for geom in geoms]
    return arcpy.Polyline(arcpy.Array(points), geoms[0].spatialReference)


def _rect_from_hint(geom, hint):
    """Create a rectangle inside a district from normalized center and size."""

    extent = geom.extent
    width = max(8.0, (extent.XMax - extent.XMin) * float(hint.get("w", 0.25)))
    height = max(8.0, (extent.YMax - extent.YMin) * float(hint.get("h", 0.20)))
    cx = extent.XMin + (extent.XMax - extent.XMin) * float(hint.get("cx", 0.5))
    cy = extent.YMin + (extent.YMax - extent.YMin) * float(hint.get("cy", 0.5))
    x0 = max(extent.XMin + 2.0, min(extent.XMax - width - 2.0, cx - width / 2))
    y0 = max(extent.YMin + 2.0, min(extent.YMax - height - 2.0, cy - height / 2))
    arr = arcpy.Array([
        arcpy.Point(x0, y0),
        arcpy.Point(x0 + width, y0),
        arcpy.Point(x0 + width, y0 + height),
        arcpy.Point(x0, y0 + height),
        arcpy.Point(x0, y0),
    ])
    return arcpy.Polygon(arr, geom.spatialReference)


def _template_for_archetype(archetype_id):
    """Return a docket template that spawns the requested archetype."""

    for template in rules.TEMPLATES.values():
        if template.spawn_archetype_id == archetype_id:
            return template.template_id
    raise KeyError(archetype_id)


def _feature_count(path):
    """Return the row count for an ArcGIS feature class."""

    return int(arcpy.management.GetCount(path)[0])


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
        field_set, last_error = _set_unique_value_renderer_field(sym.renderer, "display_state")
        if not field_set:
            _warn(
                messages,
                "SYM",
                "unique-value symbology skipped for "
                f"{getattr(layer, 'name', key)}: renderer field API unavailable"
                f" ({last_error})",
            )
            return
        try:
            sym.renderer.useDefaultSymbol = True
        except Exception:
            pass
        layer.symbology = sym
    except Exception as exc:
        _warn(messages, "SYM", f"symbology setup skipped for {getattr(layer, 'name', key)}: {exc}")


def _set_unique_value_renderer_field(renderer, field_name):
    """Set a unique-value renderer field across ArcGIS Pro API variants."""

    last_error = None
    attempts = (
        ("fields", [field_name]),
        ("field", field_name),
        ("fields", (field_name,)),
    )
    for attr, value in attempts:
        if attr == "field" and not _renderer_has_attr(renderer, attr):
            continue
        try:
            setattr(renderer, attr, value)
            return True, None
        except Exception as exc:
            last_error = exc
    return False, last_error or "no supported field setter"


def _renderer_has_attr(renderer, attr):
    try:
        getattr(renderer, attr)
    except Exception:
        return False
    return True
