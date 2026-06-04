"""Presentation model for the Permit Office desk surface.

Pure gameplay-to-text formatting: no Tkinter, no drawing. The desk view imports
these dataclasses and builders to render one frame.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Callable

from .rules_loader import rules


ACTIVE_STATUSES = ("open", "inspected", "active", "carried")
HEADLINE_METRICS = (("Week", "WEEK"), ("AP", "AP"), ("Money", "$"), ("Heat", "HEAT"), ("Audit", "AUDIT"), ("Pressure", "PRESS"))


@dataclass(frozen=True)
class DeskCallbacks:
    """UI actions exposed by the dashboard controller."""

    toggle_exhibit: Callable[[], None]
    update_from_map: Callable[[], None]
    inspect: Callable[[], None]
    approve: Callable[[], None]
    approve_mitigated: Callable[[], None]
    deny: Callable[[], None]
    advance_turn: Callable[[], None]
    new_game: Callable[[], None]
    scorecard: Callable[[], None]
    close: Callable[[], None]


@dataclass(frozen=True)
class DocketRow:
    """One visible in-tray case row."""

    item_id: str
    title: str
    geometry_type: str
    status: str
    selected: bool = False
    priority: int = 0
    due_turn: int = 0


@dataclass(frozen=True)
class CaseField:
    """A labeled line in the permit packet."""

    label: str
    value: str


@dataclass(frozen=True)
class ImpactBucket:
    """One compact permit-impact summary bucket."""

    label: str
    value: str
    tone: str = "neutral"


@dataclass(frozen=True)
class CaseSummary:
    """Structured permit-packet content for the selected case."""

    title: str = "No Active Case"
    item_id: str = ""
    status: str = ""
    category: str = ""
    fields: tuple[CaseField, ...] = ()
    districts: str = "(seeded exhibit; use Update From Map to revise)"
    preview: str = "Select a docket item from the in tray."
    inspection: str = "No inspection addendum filed."
    action_note: str = ""
    risk_band: str = "unknown"
    impact_buckets: tuple[ImpactBucket, ...] = ()


@dataclass(frozen=True)
class LedgerRow:
    """A compact audit ledger line."""

    label: str
    value: str
    tone: str = "neutral"
    meter: int | None = None


@dataclass(frozen=True)
class ReceiptModel:
    """The latest filed-report receipt drawn inline at the foot of the desk."""

    title: str = ""
    report: str = ""
    affected: tuple[str, ...] = ()
    metrics: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DeskViewModel:
    """Everything the desk view needs to draw one frame."""

    docket_rows: tuple[DocketRow, ...] = ()
    selected_item_id: str = ""
    case: CaseSummary = field(default_factory=CaseSummary)
    ledger_rows: tuple[LedgerRow, ...] = ()
    status_text: str = ""
    exhibit_visible: bool = False
    deadline_text: str = ""
    deadline_meter: int = 0
    deadline_running: bool = False
    receipt: ReceiptModel | None = None


def build_desk_model(
    state,
    districts,
    items,
    selected_item_id="",
    status_text="",
    proposal_visible_by_item=None,
    deadline_text="",
    deadline_meter=0,
    deadline_running=False,
    active_features=None,
    receipt=None,
) -> DeskViewModel:
    """Format gameplay state into a presentation-only desk model."""

    proposal_visible_by_item = proposal_visible_by_item or {}
    active_items = [item for item in items if item.status in ACTIVE_STATUSES]
    selected = _resolve_selected_item(active_items, selected_item_id)
    selected_id = selected.item_id if selected else ""
    docket_rows = tuple(
        DocketRow(
            item_id=item.item_id,
            title=item.title,
            geometry_type=item.geometry_type,
            status=item.status,
            selected=item.item_id == selected_id,
            priority=item.priority,
            due_turn=item.due_turn,
        )
        for item in active_items
    )
    case = _case_summary(state, districts, selected)
    ledger_rows = _ledger_rows(state, districts, active_features, active_items)
    status = status_text or "No report yet. Select a docket row; use Update From Map when changing targets."
    exhibit_visible = bool(proposal_visible_by_item.get(selected_id))
    return DeskViewModel(
        docket_rows,
        selected_id,
        case,
        ledger_rows,
        status,
        exhibit_visible,
        deadline_text,
        deadline_meter,
        deadline_running,
        receipt,
    )


def _resolve_selected_item(items, selected_item_id):
    """Return the requested active item or the first item as a fallback."""

    if selected_item_id:
        for item in items:
            if item.item_id == selected_item_id:
                return item
    return items[0] if items else None


def _case_summary(state, districts, item) -> CaseSummary:
    """Convert a docket item into the structured case packet model."""

    if not item:
        return CaseSummary()

    # Template, archetype, stakeholder, and district context are merged here so
    # the Canvas layer only has presentation-ready text to draw.
    template = rules.TEMPLATES[item.template_id]
    archetype = rules.feature_archetype_for_template(template)
    stakeholder = item.stakeholder or template.stakeholder
    target_rule = item.target_rule or template.target_rule
    heat = state.stakeholder_heat.get(stakeholder, 0)
    target_profiles = [districts[cid] for cid in item.target_cell_ids if cid in districts]
    population_hint = rules.target_population_hint(item, target_profiles)
    preview = item.preview_text or template.preview
    if population_hint:
        preview = f"{preview} {population_hint}"
    cost = f"{template.ap_cost} AP / ${template.money_cost}; conditions +${template.mitigation_cost}"
    fields = (
        CaseField("Applicant", f"{_display(stakeholder)}; heat {heat}"),
        CaseField("Category", f"{_display(template.category)} / {item.geometry_type}"),
        CaseField("Feature", f"{archetype.label} ({_display(archetype.family)})"),
        CaseField("Contact", template.contact_name or "not assigned"),
        CaseField("Service", _display(archetype.service_type or "none")),
        CaseField("Cost", cost),
        CaseField("Target Rule", target_rule or "No targeting rule filed."),
        CaseField("Failure Mode", template.failure_mode or "none filed"),
    )
    action_note = _action_note(template)
    districts_text = ", ".join(item.target_cell_ids) if item.target_cell_ids else "(seeded exhibit; use Update From Map to revise)"
    inspection = _inspection_summary(item)
    impact_buckets = _impact_buckets(state, districts, item, template)
    return CaseSummary(
        title=item.title,
        item_id=item.item_id,
        status=item.status,
        category=template.category,
        fields=fields,
        districts=districts_text,
        preview=preview,
        inspection=inspection,
        action_note=action_note,
        risk_band=item.risk_band or "unknown",
        impact_buckets=impact_buckets,
    )


def _impact_buckets(state, districts, item, template) -> tuple[ImpactBucket, ...]:
    """Build concise impact buckets for the selected case."""

    targets = [districts[cid] for cid in item.target_cell_ids if cid in districts]
    inspection = (item.case_json or {}).get("inspection") if isinstance(item.case_json, dict) else None
    total_money = template.money_cost + template.mitigation_cost
    cost_tone = "bad" if state.ap < template.ap_cost or state.money < template.money_cost else "watch" if state.money < total_money else "neutral"
    cost = _cost_bucket_value(template)
    city = _city_forecast_bucket(template, targets, mitigated=False)
    city_tone = _delta_tone(template.base_effects | template.spillover_effects)
    local = _local_bucket_value(item, template, targets)
    local_tone = _local_bucket_tone(item, template, targets)
    services = _services_bucket_value(template, targets)
    services_tone = _services_bucket_tone(targets)
    recurring = _recurring_bucket_value(template)
    recurring_tone = _recurring_tone(template)

    if inspection:
        people, people_tone = _inspected_people_bucket(template, targets)
        followup, followup_tone = _inspection_followup_bucket(inspection, item)
    else:
        people = _qualitative_people_bucket(template)
        people_tone = "watch" if template.concerned_groups else "neutral"
        followup = _qualitative_followup_bucket(template)
        followup_tone = "watch" if template.failure_mode else "neutral"

    return (
        ImpactBucket("Cost", cost, cost_tone),
        ImpactBucket("City", city, city_tone),
        ImpactBucket("Local", local, local_tone),
        ImpactBucket("People", people, people_tone),
        ImpactBucket("Services", services, services_tone),
        ImpactBucket("Aftermath", f"{recurring}; {followup}", _worst_tone(recurring_tone, followup_tone)),
    )


def _cost_bucket_value(template) -> str:
    """Format direct decision costs for all stamp choices."""

    return f"Issue {template.ap_cost}AP/${template.money_cost}; conditions +${template.mitigation_cost}; deny 0AP"


def _city_forecast_bucket(template, targets, mitigated: bool) -> str:
    """Forecast likely immediate metric effects before a decision is filed."""

    if not targets:
        base = rules._mitigate(template.base_effects) if mitigated else template.base_effects
        spill = rules._mitigate(template.spillover_effects) if mitigated else template.spillover_effects
        base_text = _format_effects(base)
        spill_text = _format_effects(spill)
        if spill_text != "none":
            return f"target {base_text}; spill {spill_text}"
        return f"target {base_text}"

    archetype = rules.feature_archetype_for_template(template)
    total = {metric: 0 for metric in rules.CORE_METRICS}
    for profile in targets:
        delta = rules._district_adjusted_effects(template.base_effects, profile.district_type, template.category)
        delta = rules._land_use_adjusted_effects(delta, profile, archetype)
        rules._merge_delta(delta, rules._service_coverage_effect(archetype, profile, "target"))
        if mitigated:
            delta = rules._mitigate(delta)
        for metric in rules.CORE_METRICS:
            total[metric] = total.get(metric, 0) + delta.get(metric, 0)
    averaged = {metric: round(value / max(1, len(targets))) for metric, value in total.items()}
    return _format_effects(averaged)


def _recurring_bucket_value(template) -> str:
    """Format recurring feature revenue and upkeep forecast."""

    archetype = rules.feature_archetype_for_template(template)
    operating = rules.operating_rule_for_feature(archetype.archetype_id)
    revenue = operating.revenue_per_turn
    upkeep = operating.upkeep_per_turn
    net = revenue - upkeep
    if revenue or upkeep:
        return f"rev ${revenue}/week, upkeep ${upkeep}/week, net ${net:+d}"
    return "no recurring budget"


def _recurring_tone(template) -> str:
    """Return dashboard tone for recurring budget forecast."""

    archetype = rules.feature_archetype_for_template(template)
    operating = rules.operating_rule_for_feature(archetype.archetype_id)
    net = operating.revenue_per_turn - operating.upkeep_per_turn
    if net > 0:
        return "good"
    if net < 0:
        return "watch"
    return "neutral"


def _local_bucket_value(item, template, targets) -> str:
    """Format selected target context without long prose."""

    if not item.target_cell_ids:
        return "seeded target pending map update"
    archetype = rules.feature_archetype_for_template(template)
    types = sorted({profile.district_type for profile in targets if profile.district_type})
    type_text = "/".join(types[:2]) if types else "filed"
    fit = _land_use_fit_text(template, archetype, targets)
    local_effect = _city_forecast_bucket(template, targets, mitigated=False)
    causes = _pressure_cause_summary(targets) if targets else "cause pending"
    return f"{len(item.target_cell_ids)} district(s); {type_text}; {fit}; {causes}; {local_effect}"


def _local_bucket_tone(item, template, targets) -> str:
    """Return a tone for target fit and local adjusted effects."""

    if not item.target_cell_ids:
        return "watch"
    archetype = rules.feature_archetype_for_template(template)
    if any(
        profile.district_type in template.bad_fit_types
        or profile.district_type in archetype.conflict_district_types
        for profile in targets
    ):
        return "watch"
    return _delta_tone(template.base_effects)


def _land_use_fit_text(template, archetype, targets) -> str:
    """Summarize target fit/conflict against template and feature rules."""

    if not targets:
        return "fit unknown"
    good = sum(
        1
        for profile in targets
        if profile.district_type in template.good_fit_types
        or profile.district_type in archetype.allowed_district_types
    )
    conflict = sum(
        1
        for profile in targets
        if profile.district_type in template.bad_fit_types
        or profile.district_type in archetype.conflict_district_types
    )
    if conflict:
        return f"{conflict} conflict"
    if good:
        return f"{good} fit"
    return "neutral fit"


def _services_bucket_value(template, targets) -> str:
    """Format the most relevant service, network, hazard, or housing pressure."""

    archetype = rules.feature_archetype_for_template(template)
    service = archetype.service_type or archetype.network_type
    service_text = _service_gap_summary(targets, service)
    if service_text != "no service gap":
        return service_text
    hazard_text = _hazard_summary(targets)
    if hazard_text != "no active hazards":
        return hazard_text
    housing_text = _housing_pressure_summary(targets)
    if housing_text != "housing steady":
        return housing_text
    return "services steady"


def _services_bucket_tone(targets) -> str:
    """Return a tone for local service/hazard/housing pressure."""

    worst_gap = max((gap for profile in targets for gap in (profile.service_gap or {}).values()), default=0)
    worst_hazard = max((band for profile in targets for band in (profile.hazards or {}).values()), default=0)
    housing_pressure = any(_profile_housing_pressure(profile) for profile in targets)
    if worst_gap >= 40 or worst_hazard >= 3:
        return "bad"
    if worst_gap >= 25 or worst_hazard or housing_pressure:
        return "watch"
    return "neutral"


def _qualitative_people_bucket(template) -> str:
    """Format pre-inspection people impact qualitatively."""

    supporters = _join_labels(template.supporter_groups[:2])
    objectors = _join_labels(template.concerned_groups[:2])
    if supporters != "none" and objectors != "none":
        return f"{supporters} support; {objectors} object"
    if supporters != "none":
        return f"{supporters} likely support"
    if objectors != "none":
        return f"{objectors} may object"
    return "public comment pending"


def _qualitative_followup_bucket(template) -> str:
    """Format pre-inspection follow-up qualitatively."""

    if template.failure_mode:
        return f"inspect for {template.failure_mode}"
    return "routine filing path"


def _inspected_people_bucket(template, targets) -> tuple[str, str]:
    """Format inspected supporter, objector, and grievance context."""

    supporter = _strongest_group(targets, template.supporter_groups)
    objector = _strongest_group(targets, template.concerned_groups)
    grievance_group, grievance_band = _top_grievance(targets)
    parts = []
    if supporter:
        parts.append(f"{_group_label(supporter)} support")
    if objector:
        parts.append(f"{_group_label(objector)} object")
    if grievance_band:
        parts.append(f"{_group_label(grievance_group)} {rules.GRIEVANCE_BAND_LABELS[grievance_band]}")
    tone = "bad" if grievance_band >= rules.DISSATISFACTION_INCIDENT_THRESHOLD else "watch" if grievance_band >= rules.DISSATISFACTION_AGGRIEVED_THRESHOLD or objector else "neutral"
    return "; ".join(parts) if parts else "population evidence filed", tone


def _inspection_followup_bucket(inspection, item) -> tuple[str, str]:
    """Format inspected risk, evidence, and violations."""

    evidence = inspection.get("evidence") or []
    violations = inspection.get("violations") or []
    risk = str(inspection.get("risk_band") or item.risk_band or "unknown").lower()
    warnings = sum(1 for record in evidence if isinstance(record, dict) and record.get("severity") in ("warning", "critical"))
    value = f"{risk} risk; {warnings}/{len(evidence)} flagged evidence; {len(violations)} violation(s)"
    return value, _risk_tone(risk)


def _format_effects(effects) -> str:
    """Format metric deltas for a compact bucket."""

    labels = {
        "activity": "activity",
        "friction": "friction",
        "trust": "trust",
        "exposure": "exposure",
        "services": "service",
    }
    parts = [f"{labels.get(metric, metric[:4])} {amount:+d}" for metric, amount in sorted((effects or {}).items()) if amount]
    return ", ".join(parts[:3]) if parts else "none"


def _delta_tone(effects) -> str:
    """Return a tone for a metric delta map."""

    effects = effects or {}
    if effects.get("exposure", 0) > 0 or effects.get("friction", 0) > 1:
        return "bad"
    if effects.get("exposure", 0) < 0 or effects.get("activity", 0) > 0 or effects.get("trust", 0) > 0:
        return "good"
    if any(value for value in effects.values()):
        return "watch"
    return "neutral"


def _risk_tone(risk) -> str:
    """Return the dashboard tone for an inspection risk band."""

    if risk == "high":
        return "bad"
    if risk == "medium":
        return "watch"
    if risk == "low":
        return "good"
    return "neutral"


def _strongest_group(profiles, groups) -> str:
    """Return the strongest configured group across target profiles."""

    scores = []
    for group in groups:
        score = sum(profile.population_mix.get(group, 0) for profile in profiles)
        if score > 0:
            scores.append((score, group))
    return sorted(scores, key=lambda row: (-row[0], row[1]))[0][1] if scores else ""


def _top_grievance(profiles) -> tuple[str, int]:
    """Return the highest dissatisfaction band across target profiles."""

    totals = {group: 0 for group in rules.CITIZEN_GROUPS}
    for profile in profiles:
        for group, band in (profile.dissatisfaction or {}).items():
            if group in totals:
                totals[group] += int(band or 0)
    return sorted(totals.items(), key=lambda row: (-row[1], row[0]))[0]


def _join_labels(groups) -> str:
    """Join group labels for a compact bucket value."""

    labels = [_group_label(group) for group in groups if group]
    if not labels:
        return "none"
    return "/".join(labels[:2])


def _group_label(group) -> str:
    """Return a display label for a citizen or stakeholder group id."""

    return rules.GROUP_LABELS.get(group, str(group).replace("_", " "))


def _service_gap_summary(profiles, preferred_service: str = "") -> str:
    """Summarize the worst local service gap."""

    rows = []
    for profile in profiles:
        gaps = profile.service_gap or {}
        for service, gap in gaps.items():
            if gap:
                rows.append((int(gap or 0), service, profile.cell_id))
    if not rows:
        return "no service gap"
    gap, service, cell_id = sorted(rows, key=lambda row: (-row[0], row[1], row[2]))[0]
    return f"{service.replace('_', ' ')} gap {gap} in {cell_id}"


def _hazard_summary(profiles) -> str:
    """Summarize active hazard bands across district profiles."""

    counts: dict[str, int] = {}
    worst: dict[str, int] = {}
    for profile in profiles:
        for hazard, band in (profile.hazards or {}).items():
            band = int(band or 0)
            if band <= 0:
                continue
            counts[hazard] = counts.get(hazard, 0) + 1
            worst[hazard] = max(worst.get(hazard, 0), band)
    if not counts:
        return "no active hazards"
    hazard = sorted(counts, key=lambda key: (-worst[key], -counts[key], key))[0]
    return f"{hazard.replace('_', ' ')} band {worst[hazard]} x{counts[hazard]}"


def _housing_pressure_summary(profiles) -> str:
    """Summarize housing capacity, vacancy, affordability, or displacement pressure."""

    pressure = [_profile_housing_pressure(profile) for profile in profiles]
    pressure = [text for text in pressure if text]
    if not pressure:
        return "housing steady"
    return pressure[0]


def _profile_housing_pressure(profile) -> str:
    """Return one compact housing warning for a profile, if any."""

    if profile.displacement:
        group, band = sorted(profile.displacement.items(), key=lambda row: (-int(row[1] or 0), row[0]))[0]
        if int(band or 0) > 0:
            return f"{profile.cell_id} displacement: {_group_label(group)} {band}"
    if profile.housing_capacity and profile.population > profile.housing_capacity:
        return f"{profile.cell_id} over capacity by {profile.population - profile.housing_capacity}"
    if profile.affordability and profile.affordability < 35:
        return f"{profile.cell_id} affordability {profile.affordability}"
    if profile.vacancy_rate and profile.vacancy_rate < 3:
        return f"{profile.cell_id} vacancy {profile.vacancy_rate}%"
    return ""


def _maintenance_summary(features) -> str:
    """Summarize active feature maintenance backlog."""

    candidates = [
        feature
        for feature in features or ()
        if getattr(feature, "status", "") in ("maintenance_due", "degraded", "failed")
        or int(getattr(feature, "condition", 100) or 100) < 35
    ]
    if not candidates:
        return "none"
    lowest = min(int(getattr(feature, "condition", 100) or 100) for feature in candidates)
    return f"{len(candidates)} due; lowest condition {lowest}"


def _worst_tone(*tones) -> str:
    """Return the most urgent tone from a small set."""

    priority = {"bad": 3, "watch": 2, "good": 1, "neutral": 0}
    return max((tone or "neutral" for tone in tones), key=lambda tone: priority.get(tone, 0))


def _ledger_rows(state, districts, active_features=None, docket=None) -> tuple[LedgerRow, ...]:
    """Build the city ledger rows shown in the dashboard sidebar."""

    heat = rules.heat_summary(state)
    audit_grade, _audit_report = rules.scorecard(state, deepcopy(districts), _feature_snapshots(active_features), deepcopy(docket or ()))
    population = rules.population_city_summary(districts)
    incidents = rules.incident_summary(districts)
    service_summary = _city_service_summary(districts)
    hazard_summary = _hazard_summary(districts.values() if isinstance(districts, dict) else districts)
    housing_summary = _housing_pressure_summary(districts.values() if isinstance(districts, dict) else districts)
    maintenance = _maintenance_summary(active_features) if active_features is not None else _maintenance_count_from_state(state)
    pressure = _pressure_cause_summary(districts)
    week_value = f"{state.turn}/{state.max_turns} CLOSED" if state.status == "complete" or state.turn > state.max_turns else f"{state.turn}/{state.max_turns}"
    return (
        LedgerRow("Week", week_value, "neutral", _meter(state.turn, state.max_turns)),
        LedgerRow("AP", f"{state.ap}/{state.max_ap}", "good" if state.ap else "watch", _meter(state.ap, state.max_ap)),
        LedgerRow("Money", f"${state.money}", "good" if state.money >= 20 else "watch"),
        LedgerRow("Heat", heat, "bad" if heat != "none" else "neutral"),
        LedgerRow("Audit", _short_audit_grade(audit_grade), "bad" if audit_grade == "FAIL" else "watch" if audit_grade == "CONDITIONAL" else "good"),
        LedgerRow("Pressure", pressure, "watch" if pressure != "stable" else "neutral"),
        LedgerRow("Activity", str(state.activity), "good", state.activity),
        LedgerRow("Friction", str(state.friction), "bad" if state.friction >= 50 else "watch", state.friction),
        LedgerRow("Trust", str(state.trust), "good", state.trust),
        LedgerRow("Exposure", str(state.exposure), "bad" if state.exposure >= 50 else "watch", state.exposure),
        LedgerRow("Economy", f"rev ${state.last_revenue}; up ${state.last_upkeep}; net {state.last_net:+d}", "watch" if state.last_net < 0 else "good" if state.last_net > 0 else "neutral"),
        LedgerRow("Services", service_summary, "bad" if "critical" in service_summary else "watch" if service_summary != "none" else "neutral"),
        LedgerRow("Hazards", hazard_summary, "watch" if hazard_summary != "no active hazards" else "neutral"),
        LedgerRow("Housing", housing_summary, "watch" if housing_summary != "housing steady" else "neutral"),
        LedgerRow("Maintenance", maintenance, "watch" if maintenance != "none" else "neutral"),
        LedgerRow("Population", population, "neutral"),
        LedgerRow("Incidents", incidents, "bad" if incidents != "none" else "neutral"),
    )


def _city_service_summary(districts) -> str:
    """Summarize citywide service gaps by count and worst service."""

    profiles = list(districts.values() if isinstance(districts, dict) else districts)
    rows = [(int(gap or 0), service, profile.cell_id) for profile in profiles for service, gap in (profile.service_gap or {}).items() if int(gap or 0) > 0]
    if not rows:
        return "none"
    worst_gap, worst_service, _cell_id = sorted(rows, key=lambda row: (-row[0], row[1], row[2]))[0]
    critical = sum(1 for gap, _service, _cell_id in rows if gap >= 40)
    label = "critical" if critical else "warning"
    return f"{len(rows)} {label}; worst {worst_service.replace('_', ' ')} {worst_gap}"


def _pressure_cause_summary(districts) -> str:
    """Summarize top non-money map causes for city health."""

    counts: dict[str, int] = {}
    for profile in list(districts.values() if isinstance(districts, dict) else districts):
        cause = getattr(profile, "display_state", "stable") or "stable"
        if cause != "stable":
            counts[cause] = counts.get(cause, 0) + 1
    if not counts:
        return "stable"
    return ", ".join(f"{cause.replace('_', ' ')} x{count}" for cause, count in sorted(counts.items(), key=lambda row: (-row[1], row[0]))[:3])


def _short_audit_grade(grade: str) -> str:
    """Return a compact audit grade for the top banner."""

    return "COND" if grade == "CONDITIONAL" else grade or "NA"


def _feature_snapshots(features) -> list:
    """Return rule-native feature copies for audit display calculations."""

    snapshots = []
    for feature in features or ():
        snapshots.append(
            rules.FeatureInstance(
                feature_id=getattr(feature, "feature_id", ""),
                archetype_id=getattr(feature, "archetype_id", ""),
                family=getattr(feature, "family", ""),
                service_type=getattr(feature, "service_type", ""),
                network_type=getattr(feature, "network_type", ""),
                target_cell_ids=list(getattr(feature, "target_cell_ids", []) or []),
                capacity=int(getattr(feature, "capacity", 0) or 0),
                intensity=int(getattr(feature, "intensity", 1) or 1),
                status=getattr(feature, "status", "active"),
                turn_created=int(getattr(feature, "turn_created", 0) or 0),
                expires_turn=int(getattr(feature, "expires_turn", -1) if getattr(feature, "expires_turn", -1) not in (None, "") else -1),
                project_id=getattr(feature, "project_id", ""),
                metadata=dict(getattr(feature, "metadata", {}) or {}),
                item_id=getattr(feature, "item_id", ""),
                template_id=getattr(feature, "template_id", ""),
                owner_group=getattr(feature, "owner_group", ""),
                condition=int(getattr(feature, "condition", 100) if getattr(feature, "condition", 100) not in (None, "") else 100),
                maintenance_due_turn=int(getattr(feature, "maintenance_due_turn", -1) if getattr(feature, "maintenance_due_turn", -1) not in (None, "") else -1),
                last_maintained_turn=int(getattr(feature, "last_maintained_turn", 0) or 0),
                display_state=getattr(feature, "display_state", ""),
                chain_step_id=getattr(feature, "chain_step_id", ""),
                state_json=dict(getattr(feature, "state_json", {}) or {}),
            )
        )
    return snapshots


def _maintenance_count_from_state(state) -> str:
    """Format the persisted maintenance backlog count."""

    backlog = int(getattr(state, "maintenance_backlog", 0) or 0)
    return f"{backlog} active" if backlog else "none"


def _inspection_summary(item) -> str:
    """Format inspection evidence and violations for the case packet."""

    inspection = (item.case_json or {}).get("inspection") if isinstance(item.case_json, dict) else None
    if not inspection:
        if item.inspected:
            return f"Inspection filed. Risk band: {item.risk_band or 'unknown'}."
        return "No inspection addendum filed."
    evidence = inspection.get("evidence") or []
    violations = inspection.get("violations") or []
    severities = [record.get("severity", "watch") for record in evidence if isinstance(record, dict)]
    worst = "critical" if "critical" in severities else "warning" if "warning" in severities else "watch"
    notes = []
    for record in evidence[:2]:
        if isinstance(record, dict) and record.get("label"):
            notes.append(f"{record.get('label')}: {record.get('severity', 'watch')}")
    note_text = "; ".join(notes)
    if note_text:
        note_text = f" {note_text}."
    return f"Risk {inspection.get('risk_band', item.risk_band)}; {len(evidence)} evidence item(s), highest {worst}; {len(violations)} violation(s).{note_text}"


def _action_note(template) -> str:
    """Describe how the stamp actions map to this template type."""

    if template.is_incident:
        return "Issue=response; Mitigate=settlement; Deny=defer incident."
    if template.is_enforcement:
        return "Issue=enforce; Mitigate=settle; Deny=defer."
    return "Issue=approve permit; Mitigate=approve with conditions; Deny=reject."


def _meter(value, maximum):
    """Convert a value and maximum into a 0-100 meter percentage."""

    try:
        if maximum <= 0:
            return 0
        return int(100 * value / maximum)
    except Exception:
        return 0


def _display(value):
    """Convert an identifier into title-style display text."""

    text = str(value or "none").replace("_", " ")
    return text[:1].upper() + text[1:]
