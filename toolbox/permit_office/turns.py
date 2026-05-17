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

def _scenario_score(
    state: CityState,
    profiles: list[DistrictProfile],
    features: list[FeatureInstance],
    scenario: ScenarioRule,
) -> int:
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
    return advance_turn_result(state, open_items, districts, features, projects).report


def advance_turn_result(
    state: CityState,
    open_items: Iterable[DocketItem],
    districts: dict[str, DistrictProfile] | None = None,
    features: Iterable[FeatureInstance] = (),
    projects: dict[str, ProjectRecord] | None = None,
) -> TurnAdvanceResult:
    items = list(open_items)
    feature_list = list(features or ())
    carried = 0
    expired = 0
    heated = 0
    local_grievances = 0
    overdue_violations = 0
    feature_updates: dict[str, dict[str, object]] = {}
    district_deltas: dict[str, dict[str, int]] = {}
    for item in items:
        overdue_violations += _advance_violation_deadlines(state, item)
        if item.status in ("open", "inspected"):
            template = TEMPLATES[item.template_id]
            item.stakeholder = item.stakeholder or template.stakeholder
            if _adjust_heat(state, item.stakeholder, template.ignore_heat):
                heated += 1
            if districts:
                for cid in item.target_cell_ids:
                    if cid in districts:
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
    state.turn += 1
    state.ap = state.max_ap
    if state.turn in (3, 6):
        state.audit_stage += 1
    if state.turn > state.max_turns:
        state.status = "complete"
    audit = generate_audit_result(state, districts, feature_list, items)
    heat_text = f" Stakeholder heat added to {heated} unresolved case(s)." if heated else ""
    grievance_text = f" Local grievance files updated for {local_grievances} unresolved target(s)." if local_grievances else ""
    violation_text = f" Overdue violation(s): {overdue_violations}." if overdue_violations else ""
    feature_text = f" Feature updates: {len(feature_updates)}." if feature_updates else ""
    economy_text = f" Economy net {net:+d} (revenue {revenue}, upkeep {upkeep})." if revenue or upkeep else ""
    population_text = f" Population drift {population_delta:+d}." if population_delta else ""
    incident_text = f" New civic incident file(s): {new_incidents}." if new_incidents else ""
    system_text = f" {' '.join(system_notes)}" if system_notes else ""
    audit_text = f" Audit snapshot: {audit.grade}." if state.turn in (3, 6) or state.status == "complete" else ""
    report = (
        f"Advanced turn. Carried {carried} item(s), expired {expired} item(s)."
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
    audit = generate_audit_result(state, districts, active_features, docket)
    return audit.grade, audit.report


def generate_audit_result(
    state: CityState,
    districts: Iterable[DistrictProfile] | dict[str, DistrictProfile] | None = None,
    active_features: Iterable[FeatureInstance] | None = None,
    docket: Iterable[DocketItem] | None = None,
) -> AuditResult:
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
    inspection = (item.case_json or {}).get("inspection") or {}
    if not isinstance(inspection, dict):
        return []
    return [violation for violation in inspection.get("violations") or [] if isinstance(violation, dict) and violation.get("status") in ("open", "overdue")]


__all__ = [name for name in globals() if not name.startswith("__")]
