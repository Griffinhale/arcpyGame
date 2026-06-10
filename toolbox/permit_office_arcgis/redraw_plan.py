"""Hydrate decision/cache hints into concrete map redraw intent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

try:
    from toolbox.permit_office import dirty
except ModuleNotFoundError:
    from permit_office import dirty

DISTRICTS = "PermitDistricts"
POINTS = "PermitPoints"
LINES = "PermitLines"
ZONES = "PermitZones"


@dataclass(frozen=True)
class HydratedRedrawPlan:
    """Map-work plan built from authoritative result plus speculative hints."""

    source_state_hash: str = ""
    result_state_hash: str = ""
    affected_cell_ids: tuple[str, ...] = ()
    affected_district_bits: int = 0
    dirty_layer_bits: int = 0
    feature_layer_key: str = ""
    feature_ids: tuple[str, ...] = ()
    requires_district_rehydrate: bool = True
    feature_route: str = "refresh"
    district_route: str = "ring-rehydrate"
    selection_route: str = "clear"
    refresh_names: frozenset[str] = frozenset()
    remove_readd_names: frozenset[str] = frozenset()
    ring_policy: str = "known-good-spare"


def hydrate_decision_redraw_plan(result, future_hint=None, *, feature_layer_key: str = "") -> HydratedRedrawPlan:
    """Return redraw intent, trusting actual result fields over cache hints."""

    hint_bits = int(getattr(future_hint, "dirty_layer_bits", 0) or 0)
    hinted_layer = feature_layer_key or _hint_feature_layer(future_hint)
    feature_layer = _feature_layer_name(hinted_layer)
    affected = tuple(getattr(result, "affected_cell_ids", ()) or ())
    feature_ids = tuple(sorted((getattr(result, "feature_updates", {}) or {}).keys()))
    dirty_bits = hint_bits | dirty.DISTRICTS
    if feature_layer:
        dirty_bits |= _feature_dirty_bit(hinted_layer)
    refresh = frozenset({feature_layer} if feature_layer else ())
    remove_readd = set()
    if affected or (dirty_bits & dirty.DISTRICTS):
        remove_readd.add(DISTRICTS)
    if feature_layer:
        remove_readd.add(feature_layer)
    return HydratedRedrawPlan(
        source_state_hash=getattr(future_hint, "parent_hash", "") if future_hint is not None else "",
        result_state_hash=getattr(future_hint, "resulting_state_hash", "") if future_hint is not None else "",
        affected_cell_ids=affected,
        affected_district_bits=_actual_affected_bits(result, future_hint),
        dirty_layer_bits=dirty_bits,
        feature_layer_key=hinted_layer,
        feature_ids=feature_ids,
        requires_district_rehydrate=bool(remove_readd),
        refresh_names=refresh,
        remove_readd_names=frozenset(remove_readd),
    )


def layer_names_for_plan(plan: HydratedRedrawPlan) -> set[str]:
    """Return the combined layer scope expected by existing rebuild code."""

    return set(plan.refresh_names | plan.remove_readd_names)


def _hint_feature_layer(future_hint) -> str:
    if future_hint is None:
        return ""
    redraw = getattr(future_hint, "redraw_plan", None) or {}
    return str(redraw.get("feature_layer_key", "") or "")


def _feature_layer_name(layer_key: str) -> str:
    return {
        "points": POINTS,
        "lines": LINES,
        "zones": ZONES,
    }.get(str(layer_key or "").lower(), "")


def _feature_dirty_bit(layer_key: str) -> int:
    return {
        "points": dirty.POINTS,
        "lines": dirty.LINES,
        "zones": dirty.ZONES,
    }.get(str(layer_key or "").lower(), 0)


def _actual_affected_bits(result, future_hint) -> int:
    delta = getattr(future_hint, "delta", None)
    if delta is None:
        return int(getattr(future_hint, "affected_district_bits", 0) or 0) if future_hint is not None else 0
    hinted_cells = tuple(getattr(delta, "affected_cell_ids", ()) or ())
    actual_cells = tuple(getattr(result, "affected_cell_ids", ()) or ())
    if hinted_cells == actual_cells:
        return int(getattr(future_hint, "affected_district_bits", 0) or 0)
    return 0
