"""Unattended docket expiration and city momentum rules."""

from __future__ import annotations

from dataclasses import dataclass
import random

from .catalogs import CIVIC_INCIDENT_TEMPLATE_ID, ENFORCEMENT_TEMPLATE_ID, TEMPLATES
from .helpers import _adjust_heat, normalize_profile
from .models import CityState, DistrictProfile, DocketItem, DocketTemplate


@dataclass(frozen=True)
class ExpirationResult:
    """Outcome from resolving one unattended docket item at week close."""

    item_id: str
    policy: str
    report: str
    affected_cell_ids: tuple[str, ...] = ()
    followup_template_id: str = ""


def resolve_unattended_item(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile] | None,
    seed: int = 2026,
) -> ExpirationResult:
    """Resolve one unresolved docket item without returning the same item."""

    template = TEMPLATES[item.template_id]
    item.stakeholder = item.stakeholder or template.stakeholder
    policy = template.expiration_policy or "city_momentum"
    affected = tuple(cid for cid in item.target_cell_ids if districts and cid in districts)
    _adjust_heat(state, item.stakeholder, template.ignore_heat)

    if policy == "mandatory_followup":
        item.status = "carried"
        return ExpirationResult(
            item.item_id,
            policy,
            f"{item.title} remains mandatory and returns next week.",
            affected,
            template.template_id,
        )

    item.status = "expired"
    if policy == "missed_window":
        return ExpirationResult(
            item.item_id,
            policy,
            f"{item.title} window closed without office action.",
            affected,
        )

    pressure_added = _apply_momentum_pressure(template, affected, districts or {})
    followup = ""
    if policy == "momentum_with_followup_risk":
        followup = _followup_from_bad_momentum(template.template_id, affected, districts or {}, seed)
    return ExpirationResult(
        item.item_id,
        policy,
        f"{item.title} expired into city momentum; pressure +{pressure_added}.",
        affected,
        followup,
    )


def _apply_momentum_pressure(
    template: DocketTemplate,
    affected: tuple[str, ...],
    districts: dict[str, DistrictProfile],
) -> int:
    """Apply hidden buyout pressure from unattended city momentum."""

    if not affected:
        return 0
    pressure = 2 if template.expiration_policy == "momentum_with_followup_risk" else 1
    for cid in affected:
        profile = districts[cid]
        profile.buyout_pressure = max(0, min(100, profile.buyout_pressure + pressure))
        if profile.prosperity < 50:
            profile.identity_state = "vulnerable"
        normalize_profile(profile)
    return pressure


def _followup_from_bad_momentum(
    template_id: str,
    affected: tuple[str, ...],
    districts: dict[str, DistrictProfile],
    seed: int,
) -> str:
    """Return a different follow-up template when unattended momentum goes badly."""

    if not affected:
        return ""
    worst = max((districts[cid].risk + districts[cid].unrest for cid in affected), default=0)
    rng = random.Random(f"momentum:{seed}:{template_id}:{','.join(affected)}:{worst}")
    if worst + rng.randrange(0, 40) < 80:
        return ""
    if template_id in {"contractor_renovation_waiver", "infill_construction_site"}:
        return ENFORCEMENT_TEMPLATE_ID
    return CIVIC_INCIDENT_TEMPLATE_ID


__all__ = [name for name in globals() if not name.startswith("__")]
