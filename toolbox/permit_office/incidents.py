"""Civic incident identity helpers."""

from __future__ import annotations

from .catalogs import CITIZEN_GROUPS
from .models import DocketItem


def incident_identity(cell_id: str, group: str) -> str:
    """Return the stable local grievance incident identity."""

    if not cell_id or group not in CITIZEN_GROUPS:
        return ""
    return f"dissatisfaction:{cell_id}:{group}"


def incident_identity_from_item(item: DocketItem) -> tuple[str, str, str]:
    """Read a local civic incident identity from case JSON, origin, or targets."""

    case = item.case_json.get("incident") if isinstance(item.case_json, dict) else {}
    case = case if isinstance(case, dict) else {}
    identity = str(case.get("identity") or "")
    cell_id = str(case.get("cell_id") or "")
    group = str(case.get("group") or "")
    if not identity and item.origin_item_id.startswith("dissatisfaction:"):
        identity = item.origin_item_id
    if identity.startswith("dissatisfaction:"):
        parts = identity.split(":")
        if len(parts) == 3:
            cell_id = cell_id or parts[1]
            group = group or parts[2]
    if not cell_id and len(item.target_cell_ids) == 1:
        cell_id = item.target_cell_ids[0]
    if not group and item.stakeholder in CITIZEN_GROUPS:
        group = item.stakeholder
    if not identity:
        identity = incident_identity(cell_id, group)
    if not identity.startswith("dissatisfaction:"):
        return "", "", ""
    return identity, cell_id, group


def write_incident_case_identity(item: DocketItem, cell_id: str, group: str, incident_state: str = "") -> str:
    """Persist local civic incident identity on an item without schema changes."""

    identity = incident_identity(cell_id, group)
    if not identity:
        return ""
    item.origin_item_id = item.origin_item_id or identity
    item.target_cell_ids = [cell_id]
    item.stakeholder = group
    item.case_json = dict(item.case_json or {})
    incident_case = dict(item.case_json.get("incident") or {})
    incident_case.update({"identity": identity, "cell_id": cell_id, "group": group})
    if incident_state:
        incident_case["state"] = incident_state
    item.case_json["incident"] = incident_case
    return identity


__all__ = [name for name in globals() if not name.startswith("__")]
