"""Pure Python rules for the Permit Office prototype.

This module intentionally does not import ArcPy. The Python toolbox persists
these rules into feature classes and tables, but the gameplay math is kept
testable outside ArcGIS Pro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Iterable


CORE_METRICS = ("prosperity", "unrest", "culture", "risk")

DISTRICT_TYPES = ("mercantile", "traditional", "industrial", "academic")

DISPLAY_STATES = (
    "stable",
    "prosperous",
    "restless",
    "cultured",
    "at_risk",
    "strained",
)


@dataclass(frozen=True)
class DocketTemplate:
    template_id: str
    title: str
    category: str
    geometry_type: str
    base_effects: dict[str, int]
    spillover_effects: dict[str, int]
    ap_cost: int = 1
    money_cost: int = 10
    mitigation_cost: int = 8
    expires_after: int = 0
    preview: str = ""
    inspect_hint: str = ""


@dataclass
class DistrictProfile:
    cell_id: str
    name: str
    population: int
    prosperity: int
    unrest: int
    culture: int
    risk: int
    services: int
    district_type: str
    display_state: str = "stable"


@dataclass
class CityState:
    turn: int = 1
    max_turns: int = 6
    ap: int = 3
    max_ap: int = 3
    money: int = 60
    audit_stage: int = 0
    status: str = "playing"
    last_report: str = ""
    prosperity: int = 50
    unrest: int = 20
    culture: int = 35
    risk: int = 25


@dataclass
class DocketItem:
    item_id: str
    template_id: str
    title: str
    geometry_type: str
    turn: int
    status: str = "open"
    inspected: bool = False
    target_cell_ids: list[str] = field(default_factory=list)
    preview_text: str = ""
    risk_band: str = "unknown"
    carryover: str = "expire_or_return"


@dataclass
class DecisionResult:
    ok: bool
    action: str
    item_id: str
    report: str
    city_delta: dict[str, int] = field(default_factory=dict)
    affected_cell_ids: list[str] = field(default_factory=list)
    district_deltas: dict[str, dict[str, int]] = field(default_factory=dict)
    item_status: str = ""
    command_status: str = "applied"


TEMPLATES: dict[str, DocketTemplate] = {
    "night_market": DocketTemplate(
        "night_market",
        "After-Hours Market License",
        "business",
        "POINT",
        {"prosperity": 7, "culture": 3, "unrest": 1, "risk": 1},
        {"prosperity": 2, "culture": 1, "unrest": 1},
        money_cost=12,
        mitigation_cost=6,
        preview="Likely prosperity gain near the host district; nuisance risk uncertain.",
        inspect_hint="Public comments mention foot traffic, late music, and unusually precise snack zoning.",
    ),
    "clinic": DocketTemplate(
        "clinic",
        "Neighborhood Wellness Annex",
        "service",
        "POINT",
        {"risk": -8, "prosperity": 2, "culture": 1},
        {"risk": -2, "unrest": -1},
        money_cost=18,
        mitigation_cost=5,
        preview="Likely reduces health/risk pressure; small service confidence gain nearby.",
        inspect_hint="Inspection found strong need indicators and only minor signage objections.",
    ),
    "festival_route": DocketTemplate(
        "festival_route",
        "Licensed Procession Route",
        "event",
        "LINE",
        {"culture": 8, "prosperity": 2, "unrest": 3, "risk": 1},
        {"culture": 2, "unrest": 1},
        money_cost=10,
        mitigation_cost=8,
        expires_after=1,
        preview="Temporary culture boost along a route; crowd-control side effects possible.",
        inspect_hint="Route review found enthusiasm, bottlenecks, and three mutually incompatible banner standards.",
    ),
    "transit_corridor": DocketTemplate(
        "transit_corridor",
        "Connector Corridor Pilot",
        "infrastructure",
        "LINE",
        {"prosperity": 5, "risk": -2, "unrest": 2},
        {"prosperity": 2, "risk": -1},
        money_cost=24,
        mitigation_cost=10,
        preview="Improves access between districts; construction unrest may spill along the corridor.",
        inspect_hint="Preliminary ridership estimate is good; construction complaints are already alphabetized.",
    ),
    "housing_zone": DocketTemplate(
        "housing_zone",
        "Compact Housing Variance",
        "development",
        "POLYGON",
        {"prosperity": 4, "unrest": 2, "risk": 2},
        {"prosperity": 1, "unrest": 1},
        money_cost=16,
        mitigation_cost=9,
        preview="Adds growth pressure in a zone; effects depend on local tolerance and services.",
        inspect_hint="Inspection found demand for housing and concern about shadows, parking, and mailbox destiny.",
    ),
    "factory": DocketTemplate(
        "factory",
        "Light Industrial Courtesy Permit",
        "industry",
        "POLYGON",
        {"prosperity": 9, "risk": 6, "unrest": 2, "culture": -2},
        {"prosperity": 2, "risk": 2},
        money_cost=20,
        mitigation_cost=12,
        preview="Strong prosperity upside; risk and culture effects need review.",
        inspect_hint="Environmental notes are acceptable if read quickly and in the approved order.",
    ),
    "complaint_response": DocketTemplate(
        "complaint_response",
        "Consolidated Complaint Response",
        "incident",
        "POINT",
        {"unrest": -5, "risk": -1, "culture": -1},
        {"unrest": -1},
        money_cost=8,
        mitigation_cost=4,
        expires_after=1,
        preview="Likely calms one district; may reduce local culture if over-managed.",
        inspect_hint="Complaint density is high, but half the forms cite each other as evidence.",
    ),
}


def generate_district_profiles(rows: int = 5, cols: int = 5, seed: int = 2026) -> list[DistrictProfile]:
    rng = random.Random(seed)
    prefixes = ["North", "Old", "Canal", "Bright", "Lower", "Cinder", "Glass", "Civic"]
    suffixes = ["Ward", "Market", "Steps", "Yard", "Row", "Crossing", "Annex", "Green"]
    profiles: list[DistrictProfile] = []
    for row in range(rows):
        for col in range(cols):
            cell_id = f"D{row:02d}{col:02d}"
            dtype = DISTRICT_TYPES[(row + col + rng.randrange(len(DISTRICT_TYPES))) % len(DISTRICT_TYPES)]
            base = 30 + rng.randrange(36)
            profile = DistrictProfile(
                cell_id=cell_id,
                name=f"{rng.choice(prefixes)} {rng.choice(suffixes)}",
                population=650 + rng.randrange(2200),
                prosperity=max(10, min(90, base + rng.randrange(-12, 13))),
                unrest=max(5, min(80, 28 + rng.randrange(-14, 15))),
                culture=max(10, min(90, 34 + rng.randrange(-14, 22))),
                risk=max(5, min(80, 26 + rng.randrange(-12, 18))),
                services=max(5, min(90, 35 + rng.randrange(-15, 16))),
                district_type=dtype,
            )
            profile.display_state = display_state_for_profile(profile)
            profiles.append(profile)
    return profiles


def generate_docket(turn: int, seed: int = 2026, count: int = 3) -> list[DocketItem]:
    rng = random.Random(seed * 1000 + turn)
    template_ids = list(TEMPLATES)
    chosen = rng.sample(template_ids, min(count, len(template_ids)))
    items: list[DocketItem] = []
    for idx, template_id in enumerate(chosen, start=1):
        template = TEMPLATES[template_id]
        item_id = f"T{turn:02d}-{idx:02d}-{template_id}"
        items.append(
            DocketItem(
                item_id=item_id,
                template_id=template_id,
                title=template.title,
                geometry_type=template.geometry_type,
                turn=turn,
                preview_text=template.preview,
            )
        )
    return items


def inspect_item(item: DocketItem, seed: int = 2026) -> DocketItem:
    template = TEMPLATES[item.template_id]
    rng = random.Random(f"{seed}:{item.item_id}:inspect")
    item.inspected = True
    item.risk_band = rng.choice(["low", "medium", "medium", "high"])
    item.preview_text = f"{template.preview} Inspection: {item.risk_band.upper()} side-effect risk. {template.inspect_hint}"
    return item


def resolve_decision(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile],
    action: str,
    target_cell_ids: Iterable[str],
    spillover_cell_ids: Iterable[str] = (),
    seed: int = 2026,
    mitigated: bool = False,
) -> DecisionResult:
    action_key = action.lower().strip()
    targets = _unique_known(target_cell_ids, districts)
    spillovers = [cid for cid in _unique_known(spillover_cell_ids, districts) if cid not in targets]
    template = TEMPLATES[item.template_id]

    if action_key == "inspect":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Inspection requires 1 AP.")
        state.ap -= 1
        inspect_item(item, seed)
        item.status = "inspected"
        return DecisionResult(
            True,
            action,
            item.item_id,
            f"Inspection completed for {item.title}: {item.preview_text}",
            affected_cell_ids=targets,
            item_status=item.status,
        )

    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Denial requires 1 AP.")
        state.ap -= 1
        item.status = "denied"
        delta = {"unrest": 1, "prosperity": -1}
        _apply_city_delta(state, delta)
        report = f"Denied {item.title}. Project risk avoided; applicant friction entered the public record."
        return DecisionResult(True, action, item.item_id, report, delta, targets, item_status=item.status)

    if action_key not in ("approve", "approve_mitigated"):
        return _blocked(action, item.item_id, f"Unknown decision action {action!r}.")
    if not targets:
        return _blocked(action, item.item_id, "Approve requires at least one selected target district.")
    if state.ap < template.ap_cost:
        return _blocked(action, item.item_id, f"Approval requires {template.ap_cost} AP.")
    total_money = template.money_cost + (template.mitigation_cost if mitigated else 0)
    if state.money < total_money:
        return _blocked(action, item.item_id, f"Approval requires ${total_money}.")

    state.ap -= template.ap_cost
    state.money -= total_money
    item.status = "active"
    item.target_cell_ids = targets

    district_deltas: dict[str, dict[str, int]] = {}
    city_delta = {metric: 0 for metric in CORE_METRICS}
    rng = random.Random(f"{seed}:{item.item_id}:{','.join(targets)}:{mitigated}")

    for cid in targets:
        delta = _district_adjusted_effects(template.base_effects, districts[cid].district_type, template.category)
        if mitigated:
            delta = _mitigate(delta)
        _apply_profile_delta(districts[cid], delta)
        district_deltas[cid] = delta
        _merge_delta(city_delta, delta)

    for cid in spillovers:
        delta = dict(template.spillover_effects)
        if mitigated:
            delta = _mitigate(delta)
        _apply_profile_delta(districts[cid], delta)
        district_deltas[cid] = delta
        _merge_delta(city_delta, delta)

    side = _context_side_effect(template, [districts[cid] for cid in targets], rng, mitigated)
    if side:
        for cid in targets:
            _apply_profile_delta(districts[cid], side)
            _merge_delta(district_deltas.setdefault(cid, {}), side)
        _merge_delta(city_delta, side)

    averaged = {metric: round(value / max(1, len(targets) + len(spillovers))) for metric, value in city_delta.items()}
    _apply_city_delta(state, averaged)
    affected = targets + spillovers
    mitigation_text = " with mitigation" if mitigated else ""
    report = (
        f"Approved {item.title}{mitigation_text}. Affected {len(affected)} district(s): "
        f"{', '.join(affected)}. City delta: {_format_delta(averaged)}."
    )
    return DecisionResult(True, action, item.item_id, report, averaged, affected, district_deltas, item.status)


def advance_turn(state: CityState, open_items: Iterable[DocketItem]) -> str:
    carried = 0
    expired = 0
    for item in open_items:
        if item.status in ("open", "inspected"):
            if item.carryover == "expire_or_return" and (item.turn + len(item.item_id)) % 2 == 0:
                item.status = "carried"
                carried += 1
            else:
                item.status = "expired"
                expired += 1
    state.turn += 1
    state.ap = state.max_ap
    if state.turn in (3, 6):
        state.audit_stage += 1
    if state.turn > state.max_turns:
        state.status = "complete"
    return f"Advanced turn. Carried {carried} item(s), expired {expired} item(s)."


def display_state_for_profile(profile: DistrictProfile) -> str:
    if profile.unrest >= 60 and profile.risk >= 55:
        return "strained"
    if profile.unrest >= 55:
        return "restless"
    if profile.risk >= 55:
        return "at_risk"
    if profile.prosperity >= 65:
        return "prosperous"
    if profile.culture >= 60:
        return "cultured"
    return "stable"


def scorecard(state: CityState) -> tuple[str, str]:
    score = state.prosperity + state.culture - state.unrest - state.risk + state.money // 3
    if score >= 70:
        grade = "PASS"
    elif score >= 40:
        grade = "CONDITIONAL"
    else:
        grade = "FAIL"
    return grade, f"Audit {grade}: score={score}; prosperity={state.prosperity}, unrest={state.unrest}, culture={state.culture}, risk={state.risk}, money={state.money}."


def _unique_known(values: Iterable[str], districts: dict[str, DistrictProfile]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value in districts and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _district_adjusted_effects(base: dict[str, int], district_type: str, category: str) -> dict[str, int]:
    delta = dict(base)
    if district_type == "mercantile" and category in ("business", "infrastructure"):
        delta["prosperity"] = delta.get("prosperity", 0) + 3
        delta["unrest"] = delta.get("unrest", 0) - 1
    elif district_type == "traditional" and category in ("event", "development", "industry"):
        delta["culture"] = delta.get("culture", 0) + 2
        delta["unrest"] = delta.get("unrest", 0) + 2
    elif district_type == "industrial" and category == "industry":
        delta["prosperity"] = delta.get("prosperity", 0) + 4
        delta["risk"] = delta.get("risk", 0) + 2
    elif district_type == "academic" and category in ("service", "event"):
        delta["culture"] = delta.get("culture", 0) + 3
        delta["risk"] = delta.get("risk", 0) - 1
    return delta


def _mitigate(delta: dict[str, int]) -> dict[str, int]:
    out = {}
    for metric, value in delta.items():
        if metric in ("unrest", "risk") and value > 0:
            out[metric] = max(0, value - 2)
        elif metric in ("prosperity", "culture") and value > 0:
            out[metric] = max(0, value - 1)
        else:
            out[metric] = value
    return out


def _context_side_effect(template: DocketTemplate, target_profiles: list[DistrictProfile], rng: random.Random, mitigated: bool) -> dict[str, int]:
    if mitigated:
        threshold = 0.12
    else:
        threshold = 0.28
    avg_unrest = sum(p.unrest for p in target_profiles) / max(1, len(target_profiles))
    avg_risk = sum(p.risk for p in target_profiles) / max(1, len(target_profiles))
    if template.category in ("event", "industry", "development") and (avg_unrest > 50 or rng.random() < threshold):
        return {"unrest": 2, "risk": 1}
    if template.category == "service" and avg_risk > 45:
        return {"risk": -2, "unrest": -1}
    return {}


def _apply_profile_delta(profile: DistrictProfile, delta: dict[str, int]) -> None:
    for metric, value in delta.items():
        if metric in CORE_METRICS:
            setattr(profile, metric, _clamp(getattr(profile, metric) + value))
    profile.display_state = display_state_for_profile(profile)


def _apply_city_delta(state: CityState, delta: dict[str, int]) -> None:
    for metric, value in delta.items():
        if metric in CORE_METRICS:
            setattr(state, metric, _clamp(getattr(state, metric) + value))


def _merge_delta(target: dict[str, int], delta: dict[str, int]) -> None:
    for metric, value in delta.items():
        target[metric] = target.get(metric, 0) + value


def _blocked(action: str, item_id: str, report: str) -> DecisionResult:
    return DecisionResult(False, action, item_id, report, command_status="error")


def _format_delta(delta: dict[str, int]) -> str:
    parts = []
    for metric in CORE_METRICS:
        value = delta.get(metric, 0)
        if value:
            parts.append(f"{metric} {value:+d}")
    return ", ".join(parts) if parts else "no net citywide metric change"


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))

