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

DISTRICT_TYPES = ("residential", "mercantile", "industrial", "civic", "academic", "natural")

STAKEHOLDER_HEAT_THRESHOLD = 3
ENFORCEMENT_TEMPLATE_ID = "unpermitted_followthrough"

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
    target_rule: str = ""
    stakeholder: str = "general_public"
    denial_heat: int = 1
    ignore_heat: int = 1
    failure_mode: str = ""
    failure_effects: dict[str, int] = field(default_factory=dict)
    failure_base_chance: float = 0.18
    good_fit_types: tuple[str, ...] = ()
    bad_fit_types: tuple[str, ...] = ()
    is_enforcement: bool = False


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
    stakeholder_heat: dict[str, int] = field(default_factory=dict)


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
    stakeholder: str = ""
    origin_item_id: str = ""
    target_rule: str = ""


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
    stakeholder_delta: dict[str, int] = field(default_factory=dict)
    failure_triggered: bool = False


TEMPLATES: dict[str, DocketTemplate] = {
    "connector_corridor": DocketTemplate(
        "connector_corridor",
        "Connector Corridor Pilot",
        "transit",
        "LINE",
        {"prosperity": 5, "risk": -2, "unrest": 2},
        {"prosperity": 2, "risk": -1, "unrest": 1},
        money_cost=24,
        mitigation_cost=10,
        preview="Improves access between two districts; construction unrest and alignment complaints are possible.",
        inspect_hint="Ridership math is favorable, but construction notices have already been pre-appealed.",
        target_rule="Select exactly two districts to connect.",
        stakeholder="transit_authority",
        failure_mode="construction delay",
        failure_effects={"unrest": 3, "risk": 2, "prosperity": -2},
        failure_base_chance=0.22,
        good_fit_types=("mercantile", "civic"),
        bad_fit_types=("residential", "natural"),
    ),
    "procession_route": DocketTemplate(
        "procession_route",
        "Licensed Procession Route",
        "event",
        "LINE",
        {"culture": 8, "prosperity": 2, "unrest": 3, "risk": 1},
        {"culture": 2, "unrest": 1},
        money_cost=10,
        mitigation_cost=8,
        expires_after=1,
        preview="Temporary culture boost along a route; crowd-control side effects are plausible.",
        inspect_hint="Route review found enthusiasm, bottlenecks, and three mutually incompatible banner standards.",
        target_rule="Select exactly two districts for the route endpoints.",
        stakeholder="celebrants",
        denial_heat=2,
        failure_mode="crowd-control miss",
        failure_effects={"unrest": 3, "risk": 3, "culture": -1},
        failure_base_chance=0.24,
        good_fit_types=("civic", "academic", "mercantile"),
        bad_fit_types=("industrial", "natural"),
    ),
    "utility_expansion_trench": DocketTemplate(
        "utility_expansion_trench",
        "Utility Expansion Trench",
        "utility",
        "LINE",
        {"risk": -6, "prosperity": 2, "unrest": 2},
        {"risk": -2, "unrest": 1},
        money_cost=22,
        mitigation_cost=8,
        preview="Reduces infrastructure risk; trench timing may create outages and formal sidewalk theories.",
        inspect_hint="Maps agree on the pipe location except where the pipe is most important.",
        target_rule="Select exactly two districts crossed by the utility work.",
        stakeholder="utility_board",
        ignore_heat=2,
        failure_mode="service outage",
        failure_effects={"risk": 5, "unrest": 2, "prosperity": -1},
        failure_base_chance=0.25,
        good_fit_types=("industrial", "civic"),
        bad_fit_types=("residential", "natural"),
    ),
    "natural_reserve_conversion": DocketTemplate(
        "natural_reserve_conversion",
        "Natural Reserve Conversion",
        "land",
        "POLYGON",
        {"culture": 5, "risk": -4, "prosperity": -2, "unrest": 1},
        {"culture": 2, "risk": -1, "prosperity": -1},
        money_cost=12,
        mitigation_cost=5,
        preview="Protects land and lowers hazard pressure; development pressure may reappear in better shoes.",
        inspect_hint="Boundary markers are persuasive, except one that appears to have legal opinions.",
        target_rule="Select one or more districts proposed for reserve status.",
        stakeholder="conservation_trust",
        denial_heat=2,
        failure_mode="boundary dispute",
        failure_effects={"unrest": 3, "risk": 2, "culture": -2},
        failure_base_chance=0.20,
        good_fit_types=("natural", "academic"),
        bad_fit_types=("industrial", "mercantile"),
    ),
    "mixed_use_rezoning": DocketTemplate(
        "mixed_use_rezoning",
        "Mixed-Use Rezoning Petition",
        "development",
        "POLYGON",
        {"prosperity": 6, "unrest": 3, "risk": 2, "culture": 1},
        {"prosperity": 2, "unrest": 1},
        money_cost=16,
        mitigation_cost=9,
        preview="Adds growth pressure and tax base; neighborhood fit and service capacity are uncertain.",
        inspect_hint="Applicant submitted renderings with people smiling near loading docks.",
        target_rule="Select one or more districts to rezone.",
        stakeholder="developers",
        denial_heat=2,
        failure_mode="zoning appeal",
        failure_effects={"unrest": 4, "risk": 1, "prosperity": -2},
        failure_base_chance=0.23,
        good_fit_types=("residential", "mercantile"),
        bad_fit_types=("natural", "civic"),
    ),
    "child_development_park_annex": DocketTemplate(
        "child_development_park_annex",
        "Child Development Park Annex",
        "education",
        "POINT",
        {"culture": 5, "risk": -3, "unrest": -1, "prosperity": 1},
        {"culture": 1, "risk": -1},
        money_cost=18,
        mitigation_cost=6,
        preview="Adds family recreation and child services; traffic and staffing risk require reading the small folder.",
        inspect_hint="Need is clear; staffing plan depends on a committee that has named itself provisional twice.",
        target_rule="Select exactly one district for the annex.",
        stakeholder="families",
        denial_heat=2,
        failure_mode="staffing shortfall",
        failure_effects={"risk": 3, "unrest": 2, "culture": -1},
        failure_base_chance=0.18,
        good_fit_types=("residential", "academic", "civic"),
        bad_fit_types=("industrial",),
    ),
    "street_vendor_compact": DocketTemplate(
        "street_vendor_compact",
        "Street Vendor Compact",
        "business",
        "POINT",
        {"prosperity": 6, "culture": 4, "unrest": 2, "risk": 1},
        {"prosperity": 2, "culture": 1, "unrest": 1},
        money_cost=12,
        mitigation_cost=6,
        preview="Creates visible small commerce; nuisance, sanitation, and queue geometry are lightly veiled issues.",
        inspect_hint="Public comments mention foot traffic, late music, and unusually precise snack zoning.",
        target_rule="Select exactly one host district.",
        stakeholder="vendors",
        denial_heat=2,
        ignore_heat=2,
        failure_mode="unlicensed spillover",
        failure_effects={"unrest": 3, "risk": 2, "prosperity": -1},
        failure_base_chance=0.22,
        good_fit_types=("mercantile", "residential"),
        bad_fit_types=("civic", "natural"),
    ),
    "contractor_renovation_waiver": DocketTemplate(
        "contractor_renovation_waiver",
        "Contractor Renovation Waiver",
        "residential",
        "POINT",
        {"prosperity": 4, "risk": 3, "unrest": 1},
        {"unrest": 1, "risk": 1},
        money_cost=14,
        mitigation_cost=7,
        preview="Speeds a residential project; contractor reliability and inspection burden are only partly knowable.",
        inspect_hint="The contractor has completed many jobs, several of which are admired from a distance.",
        target_rule="Select exactly one district containing the work.",
        stakeholder="contractors",
        ignore_heat=2,
        failure_mode="inspection failure",
        failure_effects={"risk": 6, "unrest": 2, "prosperity": -2},
        failure_base_chance=0.28,
        good_fit_types=("residential", "mercantile"),
        bad_fit_types=("natural", "academic"),
    ),
    "fire_budget_escalation": DocketTemplate(
        "fire_budget_escalation",
        "Fire Department Budget Escalation",
        "department",
        "POLYGON",
        {"risk": -7, "unrest": -1, "prosperity": -2},
        {"risk": -2},
        money_cost=20,
        mitigation_cost=5,
        preview="Improves response capacity; denial or delay will be remembered in very formal red ink.",
        inspect_hint="The department's incident trend is real; the proposed equipment list includes ceremonial ladders.",
        target_rule="Select one or more districts covered by the budget request.",
        stakeholder="fire_department",
        denial_heat=3,
        ignore_heat=2,
        failure_mode="coverage gap",
        failure_effects={"risk": 4, "unrest": 2},
        failure_base_chance=0.16,
        good_fit_types=("industrial", "civic", "residential"),
        bad_fit_types=("natural",),
    ),
    "public_art_museum_grant": DocketTemplate(
        "public_art_museum_grant",
        "Public Art and Museum Grant",
        "culture",
        "POINT",
        {"culture": 7, "prosperity": 1, "unrest": 1},
        {"culture": 2},
        money_cost=15,
        mitigation_cost=6,
        preview="Raises cultural profile; controversy risk is filed under community interpretation.",
        inspect_hint="The museum board is solvent, passionate, and unable to agree on the word temporary.",
        target_rule="Select exactly one district for the grant site.",
        stakeholder="arts_council",
        failure_mode="procurement scandal",
        failure_effects={"unrest": 3, "culture": -3, "prosperity": -1},
        failure_base_chance=0.20,
        good_fit_types=("civic", "academic", "mercantile"),
        bad_fit_types=("industrial",),
    ),
    ENFORCEMENT_TEMPLATE_ID: DocketTemplate(
        ENFORCEMENT_TEMPLATE_ID,
        "Unpermitted Follow-Through",
        "enforcement",
        "POINT",
        {"risk": -3, "unrest": 2, "prosperity": -1},
        {"unrest": 1},
        money_cost=8,
        mitigation_cost=6,
        preview="A previously rejected or ignored request appears to have proceeded in practical terms.",
        inspect_hint="Compliance photos are persuasive but timestamped with civic optimism.",
        target_rule="Select exactly one district where the unpermitted work or event is visible.",
        stakeholder="general_public",
        denial_heat=2,
        ignore_heat=2,
        is_enforcement=True,
    ),
}

DEMO_TEMPLATE_IDS = (
    "connector_corridor",
    "procession_route",
    "utility_expansion_trench",
    "natural_reserve_conversion",
    "mixed_use_rezoning",
    "child_development_park_annex",
    "street_vendor_compact",
    "contractor_renovation_waiver",
    "fire_budget_escalation",
    "public_art_museum_grant",
)

DEMO_SEQUENCE = {
    1: ("connector_corridor", "procession_route", "street_vendor_compact"),
    2: ("utility_expansion_trench", "contractor_renovation_waiver", "public_art_museum_grant"),
    3: ("natural_reserve_conversion", "mixed_use_rezoning", "fire_budget_escalation"),
    4: ("child_development_park_annex", "street_vendor_compact", "utility_expansion_trench"),
    5: ("connector_corridor", "mixed_use_rezoning", "public_art_museum_grant"),
    6: ("natural_reserve_conversion", "fire_budget_escalation", "procession_route"),
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


def generate_docket(turn: int, seed: int = 2026, count: int = 3, state: CityState | None = None) -> list[DocketItem]:
    chosen = list(DEMO_SEQUENCE.get(turn, ()))
    if len(chosen) < count:
        rng = random.Random(seed * 1000 + turn)
        pool = [template_id for template_id in DEMO_TEMPLATE_IDS if template_id not in chosen]
        chosen.extend(rng.sample(pool, min(count - len(chosen), len(pool))))

    items: list[DocketItem] = []
    if state:
        followup = _heat_followup_item(turn, state)
        if followup:
            items.append(followup)

    for template_id in chosen:
        if len(items) >= count:
            break
        items.append(_make_docket_item(turn, len(items) + 1, template_id))
    return items


def _make_docket_item(turn: int, idx: int, template_id: str, stakeholder: str = "", origin_item_id: str = "") -> DocketItem:
    template = TEMPLATES[template_id]
    item_stakeholder = stakeholder or template.stakeholder
    item_id = f"T{turn:02d}-{idx:02d}-{template_id}"
    title = template.title
    preview = template.preview
    if template.is_enforcement and item_stakeholder != template.stakeholder:
        label = item_stakeholder.replace("_", " ").title()
        title = f"Compliance Follow-Up: {label}"
        item_id = f"T{turn:02d}-{idx:02d}-{template_id}-{item_stakeholder}"
        preview = f"{template.preview} Stakeholder heat is now focused on {label}."
    return DocketItem(
        item_id=item_id,
        template_id=template_id,
        title=title,
        geometry_type=template.geometry_type,
        turn=turn,
        preview_text=preview,
        stakeholder=item_stakeholder,
        origin_item_id=origin_item_id,
        target_rule=template.target_rule,
    )


def _heat_followup_item(turn: int, state: CityState) -> DocketItem | None:
    hot = [(stakeholder, heat) for stakeholder, heat in state.stakeholder_heat.items() if heat >= STAKEHOLDER_HEAT_THRESHOLD]
    if not hot:
        return None
    stakeholder, _heat = sorted(hot, key=lambda pair: (-pair[1], pair[0]))[0]
    return _make_docket_item(turn, 1, ENFORCEMENT_TEMPLATE_ID, stakeholder=stakeholder, origin_item_id="stakeholder_heat")


def inspect_item(item: DocketItem, seed: int = 2026) -> DocketItem:
    template = TEMPLATES[item.template_id]
    rng = random.Random(f"{seed}:{item.item_id}:inspect")
    item.inspected = True
    item.stakeholder = item.stakeholder or template.stakeholder
    item.target_rule = item.target_rule or template.target_rule
    item.risk_band = rng.choice(["low", "medium", "medium", "high"])
    failure_text = f" Failure mode on file: {template.failure_mode}." if template.failure_mode else ""
    item.preview_text = f"{template.preview} Inspection: {item.risk_band.upper()} side-effect risk. {template.inspect_hint}{failure_text}"
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
    item.stakeholder = item.stakeholder or template.stakeholder
    item.target_rule = item.target_rule or template.target_rule

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

    if template.is_enforcement:
        return _resolve_enforcement_decision(
            state,
            item,
            districts,
            action,
            action_key,
            targets,
            spillovers,
            template,
            mitigated,
        )

    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Denial requires 1 AP.")
        state.ap -= 1
        item.status = "denied"
        delta = {"unrest": 1, "prosperity": -1}
        _apply_city_delta(state, delta)
        heat_delta = _adjust_heat(state, item.stakeholder, template.denial_heat)
        report = (
            f"Denied {item.title}. Project risk avoided; {item.stakeholder.replace('_', ' ')} heat "
            f"{heat_delta:+d} entered the public record."
        )
        return DecisionResult(
            True,
            action,
            item.item_id,
            report,
            delta,
            targets,
            item_status=item.status,
            stakeholder_delta={item.stakeholder: heat_delta},
        )

    if action_key not in ("approve", "approve_mitigated"):
        return _blocked(action, item.item_id, f"Unknown decision action {action!r}.")
    if not targets:
        return _blocked(action, item.item_id, "Approve requires at least one selected target district.")
    if state.ap < template.ap_cost:
        return _blocked(action, item.item_id, f"Approval requires {template.ap_cost} AP.")
    total_money = template.money_cost + (template.mitigation_cost if mitigated else 0)
    if state.money < total_money:
        return _blocked(action, item.item_id, f"Approval requires ${total_money}.")

    district_deltas: dict[str, dict[str, int]] = {}
    city_delta = {metric: 0 for metric in CORE_METRICS}
    rng = random.Random(f"{seed}:{item.item_id}:{','.join(targets)}:{mitigated}")

    state.ap -= template.ap_cost
    state.money -= total_money
    item.target_cell_ids = targets

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

    failure_delta = _approval_failure_effect(template, [districts[cid] for cid in targets], item.risk_band, rng, mitigated)
    failure_triggered = bool(failure_delta)
    if failure_triggered:
        item.status = "failed"
        for cid in targets:
            _apply_profile_delta(districts[cid], failure_delta)
            _merge_delta(district_deltas.setdefault(cid, {}), failure_delta)
        _merge_delta(city_delta, failure_delta)
    else:
        item.status = "active"

    averaged = {metric: round(value / max(1, len(targets) + len(spillovers))) for metric, value in city_delta.items()}
    _apply_city_delta(state, averaged)
    affected = targets + spillovers
    mitigation_text = " with mitigation" if mitigated else ""
    failure_text = ""
    if failure_triggered:
        failure_text = f" Outcome failed: {template.failure_mode}; corrective delta {_format_delta(failure_delta)}."
    report = (
        f"Approved {item.title}{mitigation_text}. Affected {len(affected)} district(s): "
        f"{', '.join(affected)}. City delta: {_format_delta(averaged)}.{failure_text}"
    )
    return DecisionResult(
        True,
        action,
        item.item_id,
        report,
        averaged,
        affected,
        district_deltas,
        item.status,
        failure_triggered=failure_triggered,
    )


def _resolve_enforcement_decision(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile],
    action: str,
    action_key: str,
    targets: list[str],
    spillovers: list[str],
    template: DocketTemplate,
    mitigated: bool,
) -> DecisionResult:
    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Deferring enforcement requires 1 AP.")
        state.ap -= 1
        item.status = "deferred"
        delta = {"unrest": 2, "risk": 1}
        _apply_city_delta(state, delta)
        heat_delta = _adjust_heat(state, item.stakeholder, template.denial_heat)
        report = (
            f"Deferred enforcement for {item.title}. The unpermitted condition remains useful to someone; "
            f"{item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}."
        )
        return DecisionResult(
            True,
            action,
            item.item_id,
            report,
            delta,
            targets,
            item_status=item.status,
            stakeholder_delta={item.stakeholder: heat_delta},
        )

    if action_key not in ("approve", "approve_mitigated"):
        return _blocked(action, item.item_id, f"Unknown decision action {action!r}.")
    if not targets:
        return _blocked(action, item.item_id, "Enforcement requires one selected district.")
    if state.ap < template.ap_cost:
        return _blocked(action, item.item_id, f"Enforcement requires {template.ap_cost} AP.")
    total_money = template.money_cost + (template.mitigation_cost if mitigated else 0)
    if state.money < total_money:
        return _blocked(action, item.item_id, f"Enforcement requires ${total_money}.")

    state.ap -= template.ap_cost
    state.money -= total_money
    item.target_cell_ids = targets
    item.status = "settled" if mitigated else "enforced"

    district_deltas: dict[str, dict[str, int]] = {}
    city_delta = {metric: 0 for metric in CORE_METRICS}
    base = _mitigate(template.base_effects) if mitigated else dict(template.base_effects)
    spill = _mitigate(template.spillover_effects) if mitigated else dict(template.spillover_effects)

    for cid in targets:
        _apply_profile_delta(districts[cid], base)
        district_deltas[cid] = dict(base)
        _merge_delta(city_delta, base)

    for cid in spillovers:
        delta = dict(spill)
        _apply_profile_delta(districts[cid], delta)
        district_deltas[cid] = delta
        _merge_delta(city_delta, delta)

    heat_relief = -2 if mitigated else -STAKEHOLDER_HEAT_THRESHOLD
    heat_delta = _adjust_heat(state, item.stakeholder, heat_relief)
    averaged = {metric: round(value / max(1, len(targets) + len(spillovers))) for metric, value in city_delta.items()}
    _apply_city_delta(state, averaged)
    affected = targets + spillovers
    if mitigated:
        report = (
            f"Settled {item.title} through a retroactive permit and compliance schedule. "
            f"City delta: {_format_delta(averaged)}. {item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}."
        )
    else:
        report = (
            f"Enforced {item.title}. The record is clearer and several people are louder. "
            f"City delta: {_format_delta(averaged)}. {item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}."
        )
    return DecisionResult(
        True,
        action,
        item.item_id,
        report,
        averaged,
        affected,
        district_deltas,
        item.status,
        stakeholder_delta={item.stakeholder: heat_delta},
    )


def advance_turn(state: CityState, open_items: Iterable[DocketItem]) -> str:
    carried = 0
    expired = 0
    heated = 0
    for item in open_items:
        if item.status in ("open", "inspected"):
            template = TEMPLATES[item.template_id]
            item.stakeholder = item.stakeholder or template.stakeholder
            if _adjust_heat(state, item.stakeholder, template.ignore_heat):
                heated += 1
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
    heat_text = f" Stakeholder heat added to {heated} unresolved case(s)." if heated else ""
    return f"Advanced turn. Carried {carried} item(s), expired {expired} item(s).{heat_text}"


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


def heat_summary(state: CityState) -> str:
    hot = [(stakeholder, heat) for stakeholder, heat in state.stakeholder_heat.items() if heat > 0]
    if not hot:
        return "none"
    return ", ".join(f"{stakeholder.replace('_', ' ')} {heat}" for stakeholder, heat in sorted(hot, key=lambda pair: (-pair[1], pair[0]))[:3])


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
    if district_type == "residential" and category in ("education", "residential"):
        delta["culture"] = delta.get("culture", 0) + 1
        delta["risk"] = delta.get("risk", 0) - 1
    elif district_type == "residential" and category in ("transit", "utility", "development"):
        delta["unrest"] = delta.get("unrest", 0) + 1
    elif district_type == "mercantile" and category in ("business", "transit", "culture"):
        delta["prosperity"] = delta.get("prosperity", 0) + 3
        delta["unrest"] = delta.get("unrest", 0) - 1
    elif district_type == "industrial" and category in ("utility", "department", "development"):
        delta["prosperity"] = delta.get("prosperity", 0) + 2
        delta["risk"] = delta.get("risk", 0) + 1
    elif district_type == "civic" and category in ("department", "education", "culture", "event"):
        delta["culture"] = delta.get("culture", 0) + 2
        delta["risk"] = delta.get("risk", 0) - 1
    elif district_type == "academic" and category in ("education", "culture", "event", "land"):
        delta["culture"] = delta.get("culture", 0) + 3
        delta["risk"] = delta.get("risk", 0) - 1
    elif district_type == "natural" and category == "land":
        delta["culture"] = delta.get("culture", 0) + 3
        delta["risk"] = delta.get("risk", 0) - 2
    elif district_type == "natural" and category in ("development", "utility", "transit", "business"):
        delta["unrest"] = delta.get("unrest", 0) + 2
        delta["risk"] = delta.get("risk", 0) + 1
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
    if template.category in ("event", "development", "residential", "transit", "utility", "business") and (avg_unrest > 50 or rng.random() < threshold):
        return {"unrest": 2, "risk": 1}
    if template.category in ("education", "department", "land") and avg_risk > 45:
        return {"risk": -2, "unrest": -1}
    return {}


def _approval_failure_effect(
    template: DocketTemplate,
    target_profiles: list[DistrictProfile],
    risk_band: str,
    rng: random.Random,
    mitigated: bool,
) -> dict[str, int]:
    if not template.failure_effects:
        return {}
    chance = _failure_chance(template, target_profiles, risk_band, mitigated)
    if rng.random() >= chance:
        return {}
    delta = dict(template.failure_effects)
    if mitigated:
        delta = _mitigate(delta)
    return delta


def _failure_chance(template: DocketTemplate, target_profiles: list[DistrictProfile], risk_band: str, mitigated: bool) -> float:
    avg_services = sum(p.services for p in target_profiles) / max(1, len(target_profiles))
    avg_risk = sum(p.risk for p in target_profiles) / max(1, len(target_profiles))
    chance = template.failure_base_chance
    chance += {"low": -0.12, "medium": 0.02, "high": 0.25, "unknown": 0.05}.get(risk_band, 0.05)
    if avg_services < 25:
        chance += 0.16
    elif avg_services > 55:
        chance -= 0.08
    if avg_risk > 55:
        chance += 0.10
    district_types = {profile.district_type for profile in target_profiles}
    if district_types & set(template.good_fit_types):
        chance -= 0.10
    if district_types & set(template.bad_fit_types):
        chance += 0.14
    if mitigated:
        chance -= 0.20
    if risk_band == "high" and avg_services < 20 and avg_risk > 75 and district_types & set(template.bad_fit_types):
        chance = 1.0
    return max(0.03, min(1.0, chance))


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


def _adjust_heat(state: CityState, stakeholder: str, amount: int) -> int:
    if not stakeholder or amount == 0:
        return 0
    before = state.stakeholder_heat.get(stakeholder, 0)
    after = max(0, before + amount)
    if after:
        state.stakeholder_heat[stakeholder] = after
    else:
        state.stakeholder_heat.pop(stakeholder, None)
    return after - before


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
