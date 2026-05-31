"""Turn advancement and audit scoring for the Permit Office game loop."""

from __future__ import annotations

from typing import Iterable

from .models import *
from .catalogs import *
from .helpers import *
from .systems import (
    _advance_feature_lifecycle,
    _apply_recurring_economy,
    apply_hazard_turn,
    apply_housing_dynamics,
    normalize_feature_instance,
    recompute_network_access,
)

TURN_PERMIT_SPEND_KEY = "_turn_permit_spend"
PRESSURE_DAY_MAX = 4


def advance_daily_pressure(
    state: CityState,
    docket: Iterable[DocketItem],
    districts: dict[str, DistrictProfile] | None = None,
    active_features: Iterable[FeatureInstance] = (),
    target_day: int = 0,
) -> dict[str, int]:
    """Accumulate visible district pressure for newly entered office days."""

    current_day = max(0, min(PRESSURE_DAY_MAX, int(getattr(state, "week_day", 0) or 0)))
    target_day = max(0, min(PRESSURE_DAY_MAX, int(target_day or 0)))
    if target_day <= current_day:
        state.week_day = current_day
        return dict(state.daily_pressure)

    district_ids = set((districts or {}).keys())
    increments = _daily_pressure_increments(docket, districts or {}, active_features)
    pressure = {
        str(cid): max(0, min(PRESSURE_DAY_MAX, int(value or 0)))
        for cid, value in (getattr(state, "daily_pressure", {}) or {}).items()
        if str(cid) in district_ids or not district_ids
    }
    elapsed_days = target_day - current_day
    for cid, amount in increments.items():
        if district_ids and cid not in district_ids:
            continue
        pressure[cid] = min(PRESSURE_DAY_MAX, pressure.get(cid, 0) + amount * elapsed_days)
    state.week_day = target_day
    state.daily_pressure = dict(sorted((cid, value) for cid, value in pressure.items() if value > 0))
    return dict(state.daily_pressure)


def _daily_pressure_increments(
    docket: Iterable[DocketItem],
    districts: dict[str, DistrictProfile],
    active_features: Iterable[FeatureInstance],
) -> dict[str, int]:
    """Return per-day district pressure from unresolved work and city conditions."""

    increments: dict[str, int] = {}
    for item in docket or ():
        if item.status not in ("open", "inspected"):
            continue
        for cid in item.target_cell_ids:
            increments[cid] = increments.get(cid, 0) + 1
    for cid, profile in (districts or {}).items():
        if _profile_has_daily_pressure(profile):
            increments[cid] = increments.get(cid, 0) + 1
    for feature in active_features or ():
        if getattr(feature, "status", "") not in ("maintenance_due", "degraded"):
            continue
        for cid in feature.target_cell_ids:
            increments[cid] = increments.get(cid, 0) + 1
    return increments


def _profile_has_daily_pressure(profile: DistrictProfile) -> bool:
    """Return whether an existing district condition should count today."""

    if profile.incident_state != "none":
        return True
    if _top_dissatisfaction(profile)[1] >= DISSATISFACTION_AGGRIEVED_THRESHOLD:
        return True
    if max((int(gap or 0) for gap in (profile.service_gap or {}).values()), default=0) >= 30:
        return True
    if max((int(band or 0) for band in (profile.hazards or {}).values()), default=0) >= 2:
        return True
    if max((int(band or 0) for band in (profile.displacement or {}).values()), default=0) >= 2:
        return True
    return False


def _scenario_score(
    state: CityState,
    profiles: list[DistrictProfile],
    features: list[FeatureInstance],
    scenario: ScenarioRule,
) -> int:
    """Calculate audit score using either default or scenario-specific weights."""

    if scenario.scenario_id == "default":
        return state.prosperity + state.culture - state.unrest - state.risk + state.money // 3
    weights = scenario.score_weights or SCENARIO_RULES["default"].score_weights
    score = 0
    metric_values = {
        "prosperity": state.prosperity,
        "culture": state.culture,
        "unrest": state.unrest,
        "risk": state.risk,
        "money": state.money // 3,
    }
    # Scenario weights can inspect district-level systems, so fold those
    # aggregate values into the same metric map as citywide fields.
    if profiles:
        metric_values["housing_capacity"] = sum(profile.housing_capacity for profile in profiles) // max(1, len(profiles) * 100)
        metric_values["affordability"] = sum(profile.affordability for profile in profiles) // max(1, len(profiles))
        metric_values["vacancy_rate"] = sum(profile.vacancy_rate for profile in profiles) // max(1, len(profiles))
        metric_values["displacement"] = sum(max(profile.displacement.values(), default=0) for profile in profiles)
        metric_values["renter_dissatisfaction"] = sum(profile.dissatisfaction.get("renters", 0) for profile in profiles)
        for service in SERVICE_TYPES:
            metric_values[service] = sum(profile.network_access.get(service, 0) for profile in profiles)
        for hazard in HAZARD_TYPES:
            metric_values[hazard] = sum(profile.hazards.get(hazard, 0) for profile in profiles)
    for metric, weight in weights.items():
        score += metric_values.get(metric, 0) * int(weight)
    return score




def advance_turn(
    state: CityState,
    open_items: Iterable[DocketItem],
    districts: dict[str, DistrictProfile] | None = None,
    features: Iterable[FeatureInstance] = (),
    projects: dict[str, ProjectRecord] | None = None,
) -> str:
    """Advance the game one turn and return only the report text."""

    return advance_turn_result(state, open_items, districts, features, projects).report


def advance_turn_result(
    state: CityState,
    open_items: Iterable[DocketItem],
    districts: dict[str, DistrictProfile] | None = None,
    features: Iterable[FeatureInstance] = (),
    projects: dict[str, ProjectRecord] | None = None,
) -> TurnAdvanceResult:
    """Advance unresolved cases, city systems, economy, incidents, and audits."""

    if state.status == "complete" or state.turn > state.max_turns:
        if state.turn > state.max_turns:
            state.turn = state.max_turns
            state.status = "complete"
            state.audit_stage = max(state.audit_stage, 2)
        audit = generate_audit_result(state, districts, features, open_items)
        report = f"Final audit already filed. Scorecard: {audit.grade}."
        state.week_day = 0
        state.daily_pressure = {}
        state.last_report = report
        return TurnAdvanceResult(report, audit=audit)

    items = list(open_items)
    feature_list = list(features or ())
    carried = 0
    expired = 0
    heated = 0
    local_grievances = 0
    overdue_violations = 0
    feature_updates: dict[str, dict[str, object]] = {}
    district_deltas: dict[str, dict[str, int]] = {}
    money_before_recurring = state.money
    permit_spend = int(state.stakeholder_memory.pop(TURN_PERMIT_SPEND_KEY, 0) or 0)
    weekly_pressure = {
        str(cid): max(0, min(PRESSURE_DAY_MAX, int(value or 0)))
        for cid, value in (getattr(state, "daily_pressure", {}) or {}).items()
    }
    # Unresolved docket work creates heat, local grievances, carryover state,
    # and project delay before long-running systems advance.
    for item in items:
        overdue_violations += _advance_violation_deadlines(state, item)
        if item.status in ("open", "inspected"):
            template = TEMPLATES[item.template_id]
            item.stakeholder = item.stakeholder or template.stakeholder
            if _adjust_heat(state, item.stakeholder, template.ignore_heat):
                heated += 1
            item_pressure = max((weekly_pressure.get(cid, 0) for cid in item.target_cell_ids), default=0)
            extra_heat = (1 if item_pressure >= 2 else 0) + (1 if item_pressure >= PRESSURE_DAY_MAX else 0)
            if extra_heat and _adjust_heat(state, item.stakeholder, extra_heat):
                heated += 1
            if districts:
                for cid in item.target_cell_ids:
                    if cid in districts:
                        _apply_population_reaction(template, [districts[cid]], "ignore", False)
                        local_grievances += 1
                        if weekly_pressure.get(cid, 0) >= 3:
                            _apply_population_reaction(template, [districts[cid]], "ignore", False)
                            local_grievances += 1
            if item.carryover == "expire_or_return" and (item.turn + len(item.item_id)) % 2 == 0:
                item.status = "carried"
                carried += 1
            else:
                item.status = "expired"
                expired += 1
            if projects and item.project_id in projects:
                project = projects[item.project_id]
                project.status = "overdue"
                project.due_turn = state.turn + 1
                project.last_report = f"{item.title} was unresolved on turn {state.turn}."
    if feature_list:
        feature_updates, district_deltas = _advance_feature_lifecycle(state, districts or {}, feature_list, state.turn + 1)
    revenue, upkeep, net = _apply_recurring_economy(state, districts or {}, feature_list)
    population_delta = 0
    new_incidents = 0
    system_notes: list[str] = []
    if districts:
        # Network, hazard, housing, and population systems operate on normalized
        # profiles so the next dashboard render sees current derived fields.
        if feature_list or any(profile.hazards for profile in districts.values()):
            recompute_network_access(districts, feature_list, state.turn)
            hazard_report = apply_hazard_turn(districts, feature_list, state.turn)
            if hazard_report.get("severe_hazards"):
                system_notes.append(f"Severe hazard bands {hazard_report['severe_hazards']}.")
        housing_report = apply_housing_dynamics(districts)
        if housing_report.get("housing_population_delta"):
            population_delta += housing_report["housing_population_delta"]
        if housing_report.get("displacement_pressure"):
            system_notes.append(f"Displacement pressure in {housing_report['displacement_pressure']} district(s).")
        for profile in districts.values():
            population_delta += _advance_population_pressure(profile)
        new_incidents = _surface_new_incidents(state, districts.values())
    final_week = state.turn >= state.max_turns
    if not final_week:
        state.turn += 1
    state.ap = state.max_ap
    if not final_week and state.turn == 3:
        state.audit_stage += 1
    if final_week:
        state.status = "complete"
        state.audit_stage = max(state.audit_stage, 2)
    audit = generate_audit_result(state, districts, feature_list, items)
    state.week_day = 0
    state.daily_pressure = {}
    heat_text = f" Stakeholder heat added to {heated} unresolved case(s)." if heated else ""
    grievance_text = f" Local grievance files updated for {local_grievances} unresolved target(s)." if local_grievances else ""
    violation_text = f" Overdue violation(s): {overdue_violations}." if overdue_violations else ""
    feature_text = f" Feature updates: {len(feature_updates)}." if feature_updates else ""
    starting_money = money_before_recurring + permit_spend
    turn_net = state.money - starting_money
    economy_text = (
        f" Economy: start ${starting_money}, permit spend ${permit_spend}, "
        f"revenue ${revenue}, upkeep ${upkeep}, net {turn_net:+d}, end ${state.money}."
    )
    population_text = f" Population drift {population_delta:+d}." if population_delta else ""
    incident_text = f" New civic incident file(s): {new_incidents}." if new_incidents else ""
    system_text = f" {' '.join(system_notes)}" if system_notes else ""
    audit_text = f" Final audit: {audit.grade}." if state.status == "complete" else f" Audit snapshot: {audit.grade}." if state.turn == 3 else ""
    report = (
        f"{'Final week closed' if state.status == 'complete' else 'Advanced week'}. Carried {carried} item(s), expired {expired} item(s)."
        f"{heat_text}{grievance_text}{violation_text}{feature_text}{economy_text}{population_text}{incident_text}{system_text}{audit_text}"
    )
    state.last_report = report
    return TurnAdvanceResult(
        report,
        city_delta={"money": net},
        district_deltas=district_deltas,
        feature_updates=feature_updates,
        revenue=revenue,
        upkeep=upkeep,
        net=net,
        audit=audit,
    )




def scorecard(
    state: CityState,
    districts: Iterable[DistrictProfile] | dict[str, DistrictProfile] | None = None,
    active_features: Iterable[FeatureInstance] | None = None,
    docket: Iterable[DocketItem] | None = None,
) -> tuple[str, str]:
    """Return the current audit grade and human-readable report."""

    audit = generate_audit_result(state, districts, active_features, docket)
    return audit.grade, audit.report


def generate_audit_result(
    state: CityState,
    districts: Iterable[DistrictProfile] | dict[str, DistrictProfile] | None = None,
    active_features: Iterable[FeatureInstance] | None = None,
    docket: Iterable[DocketItem] | None = None,
) -> AuditResult:
    """Score city state and produce audit findings for visible risks."""

    findings: list[AuditFinding] = []
    profiles = list((districts.values() if isinstance(districts, dict) else districts) or ())
    features = list(active_features or ())
    scenario = SCENARIO_RULES.get(state.scenario_id, SCENARIO_RULES["default"])
    score = _scenario_score(state, profiles, features, scenario)
    score += max(-10, min(10, state.last_net))
    service_gap_counts: dict[str, int] = {}
    service_gap_total = 0
    service_gap_critical = 0
    incident_count = 0
    hazard_counts: dict[str, int] = {}
    displacement_count = 0
    if state.money < 0:
        findings.append(AuditFinding("money.negative", "critical", "money", "Budget is negative.", -25))
    elif state.money < 15:
        findings.append(AuditFinding("money.low", "warning", "money", "Budget is below the operating reserve.", -10))
    if state.last_net < 0:
        findings.append(AuditFinding("money.net_negative", "warning", "economy", "Recurring economy is losing money.", -5))
    if state.unrest >= 70:
        findings.append(AuditFinding("city.unrest", "critical", "city", "Citywide unrest is audit-critical.", -20))
    if state.risk >= 70:
        findings.append(AuditFinding("city.risk", "critical", "city", "Citywide risk is audit-critical.", -20))

    # Audit findings aggregate citywide signals but keep severe district facts visible.
    for profile in profiles:
        normalize_profile(profile)
        if profile.incident_state != "none":
            incident_count += 1
        if profile.risk >= 70:
            findings.append(AuditFinding(f"risk.{profile.cell_id}", "critical", "district", f"{profile.cell_id} risk is critical.", -12))
        if profile.unrest >= 70:
            findings.append(AuditFinding(f"unrest.{profile.cell_id}", "critical", "district", f"{profile.cell_id} unrest is critical.", -12))
        for service, gap in profile.service_gap.items():
            if gap >= AUDIT_THRESHOLDS["service_gap_critical"]:
                service_gap_total += 1
                service_gap_critical += 1
                service_gap_counts[service] = service_gap_counts.get(service, 0) + 1
            elif gap >= AUDIT_THRESHOLDS["service_gap_warning"]:
                service_gap_total += 1
                service_gap_counts[service] = service_gap_counts.get(service, 0) + 1
        for hazard, band in profile.hazards.items():
            if band >= 3:
                hazard_counts[hazard] = hazard_counts.get(hazard, 0) + 1
        displacement = max(profile.displacement.values(), default=0)
        if displacement >= 3:
            displacement_count += 1

    if service_gap_total:
        services = ", ".join(
            f"{service.replace('_', ' ')} x{count}"
            for service, count in sorted(service_gap_counts.items())
        )
        severity_text = "including critical gaps" if service_gap_critical else "warning-level gaps"
        findings.append(
            AuditFinding(
                "service_gap.citywide",
                "warning",
                "services",
                f"Citywide service review found {service_gap_total} district/service gap(s), {severity_text}: {services}.",
                -8 if service_gap_critical else -5,
            )
        )
    if incident_count:
        findings.append(
            AuditFinding(
                "incident.citywide",
                "warning",
                "district",
                f"Visible civic incident files remain in {incident_count} district(s).",
                -8,
            )
        )
    if hazard_counts:
        hazards = ", ".join(
            f"{hazard.replace('_', ' ')} x{count}"
            for hazard, count in sorted(hazard_counts.items())
        )
        findings.append(
            AuditFinding(
                "hazard.citywide",
                "warning",
                "hazards",
                f"Elevated hazard bands remain: {hazards}.",
                -8,
            )
        )
    if displacement_count:
        findings.append(
            AuditFinding(
                "displacement.citywide",
                "warning",
                "housing",
                f"Displacement pressure remains in {displacement_count} district(s).",
                -6,
            )
        )

    feature_condition_warnings = 0
    lowest_feature_condition = 100
    for feature in features:
        normalize_feature_instance(feature, state.turn)
        if feature.status == "failed":
            findings.append(AuditFinding(f"feature.failed.{feature.feature_id}", "critical", "features", f"{feature.feature_id} has failed.", -14))
        elif feature.status in ("maintenance_due", "degraded") or feature.condition <= AUDIT_THRESHOLDS["feature_condition_warning"]:
            if feature.condition <= AUDIT_THRESHOLDS["feature_condition_critical"]:
                findings.append(AuditFinding(f"feature.condition.{feature.feature_id}", "critical", "features", f"{feature.feature_id} condition is {feature.condition}.", -12))
            else:
                feature_condition_warnings += 1
                lowest_feature_condition = min(lowest_feature_condition, feature.condition)
    if feature_condition_warnings:
        findings.append(
            AuditFinding(
                "feature.condition.citywide",
                "warning",
                "features",
                f"{feature_condition_warnings} active feature(s) need maintenance review; lowest condition is {lowest_feature_condition}.",
                -6,
            )
        )

    for item in docket or ():
        for violation in _open_violations(item):
            deadline = int(violation.get("deadline_turn") or 0)
            if deadline and deadline < state.turn:
                severity = str(violation.get("severity") or "warning")
                penalty = -10 if severity == "critical" else -6
                findings.append(AuditFinding(f"violation.{item.item_id}.{violation.get('code')}", severity, "inspection", f"{item.item_id} has an overdue {violation.get('code')} violation.", penalty))

    score += sum(finding.score_delta for finding in findings)
    critical_count = sum(1 for finding in findings if finding.severity == "critical")
    if score >= 70 and state.money >= 0 and critical_count == 0:
        grade = "PASS"
    elif score >= 45 and critical_count <= 1:
        grade = "CONDITIONAL"
    else:
        grade = "FAIL"
    finding_text = "no findings" if not findings else f"{len(findings)} finding(s), {critical_count} critical"
    scenario_text = "" if state.scenario_id == "default" else f"; scenario={state.scenario_id}; priorities={', '.join(scenario.audit_priorities)}"
    report = (
        f"Audit {grade}: score={score}; prosperity={state.prosperity}, unrest={state.unrest}, "
        f"culture={state.culture}, risk={state.risk}, money={state.money}; net={state.last_net}{scenario_text}; {finding_text}."
    )
    return AuditResult(grade, score, tuple(findings), report)




def _settle_item_violations(item: DocketItem, mitigated: bool) -> None:
    """Close open inspection violations after a resolved decision."""

    inspection = dict((item.case_json or {}).get("inspection") or {})
    violations = list(inspection.get("violations") or [])
    changed = False
    for violation in violations:
        if not isinstance(violation, dict) or violation.get("status") not in ("open", "overdue"):
            continue
        if mitigated:
            violation["status"] = "complied"
            violation["compliance_outcome"] = "settled"
        else:
            violation["status"] = "accepted"
            violation["compliance_outcome"] = "conditions"
        changed = True
    if changed:
        inspection["violations"] = violations
        item.case_json = dict(item.case_json or {})
        item.case_json["inspection"] = inspection


def _advance_violation_deadlines(state: CityState, item: DocketItem) -> int:
    """Mark overdue inspection violations and add enforcement pressure."""

    overdue = 0
    inspection = dict((item.case_json or {}).get("inspection") or {})
    violations = list(inspection.get("violations") or [])
    changed = False
    for violation in violations:
        if not isinstance(violation, dict) or violation.get("status") not in ("open", "overdue"):
            continue
        deadline = int(violation.get("deadline_turn") or 0)
        if deadline and deadline <= state.turn and violation.get("status") != "overdue":
            violation["status"] = "overdue"
            violation["compliance_outcome"] = "missed"
            _adjust_heat(state, item.stakeholder or TEMPLATES[item.template_id].stakeholder, 1)
            item.priority += 1
            overdue += 1
            changed = True
    if changed:
        inspection["violations"] = violations
        item.case_json = dict(item.case_json or {})
        item.case_json["inspection"] = inspection
    return overdue


def _open_violations(item: DocketItem) -> list[dict[str, object]]:
    """Return currently open or overdue violation records on an item."""

    inspection = (item.case_json or {}).get("inspection") or {}
    if not isinstance(inspection, dict):
        return []
    return [violation for violation in inspection.get("violations") or [] if isinstance(violation, dict) and violation.get("status") in ("open", "overdue")]


__all__ = [name for name in globals() if not name.startswith("__")]
