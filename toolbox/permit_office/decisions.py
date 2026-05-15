from __future__ import annotations

import random
from typing import Iterable

from .models import *
from .catalogs import *
from .helpers import *
from .profiles import inspect_item, inspection_case_for_item
from .systems import (
    advance_project_from_item,
    apply_template_long_term_effects,
    feature_update_payload,
    operating_rule_for_feature,
    start_project_from_approval,
)
from .turns import _settle_item_violations

def resolve_decision(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile],
    action: str,
    target_cell_ids: Iterable[str],
    spillover_cell_ids: Iterable[str] = (),
    seed: int = 2026,
    mitigated: bool = False,
    active_features: Iterable[FeatureInstance] | None = None,
    projects: dict[str, ProjectRecord] | None = None,
) -> DecisionResult:
    action_key = action.lower().strip()
    targets = _unique_known(target_cell_ids, districts)
    spillovers = [cid for cid in _unique_known(spillover_cell_ids, districts) if cid not in targets]
    template = TEMPLATES[item.template_id]
    archetype = feature_archetype_for_template(template)
    item.stakeholder = item.stakeholder or template.stakeholder
    item.target_rule = item.target_rule or template.target_rule

    if template.template_id == MAINTENANCE_TEMPLATE_ID:
        return _resolve_maintenance_decision(
            state,
            item,
            action,
            action_key,
            targets,
            template,
            mitigated,
            active_features,
        )

    if action_key == "inspect":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Inspection requires 1 AP.")
        state.ap -= 1
        inspect_item(item, seed, [districts[cid] for cid in targets])
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
            projects,
        )

    if template.is_incident:
        return _resolve_incident_decision(
            state,
            item,
            districts,
            action,
            action_key,
            targets,
            spillovers,
            template,
            mitigated,
            projects,
        )

    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Denial requires 1 AP.")
        state.ap -= 1
        item.status = "denied"
        delta = {"unrest": 1, "prosperity": -1}
        _apply_city_delta(state, delta)
        district_deltas = _apply_population_reaction(template, [districts[cid] for cid in targets], "deny", mitigated)
        surfaced = _surface_new_incidents(state, [districts[cid] for cid in targets])
        if surfaced:
            delta["unrest"] = delta.get("unrest", 0) + surfaced
        heat_delta = _adjust_heat(state, item.stakeholder, template.denial_heat)
        project_note = ""
        if projects and item.project_id:
            project = advance_project_from_item(projects, item, state, approved=False)
            if project:
                project_note = f" Project {project.project_id} delayed."
        report = (
            f"Denied {item.title}. Project risk avoided; {item.stakeholder.replace('_', ' ')} heat "
            f"{heat_delta:+d} entered the public record.{project_note} {_population_report_fragment([districts[cid] for cid in targets])}"
        )
        return DecisionResult(
            True,
            action,
            item.item_id,
            report,
            delta,
            targets,
            district_deltas,
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
        delta = _land_use_adjusted_effects(delta, districts[cid], archetype)
        _merge_delta(delta, _service_coverage_effect(archetype, districts[cid], "target"))
        if mitigated:
            delta = _mitigate(delta)
        _apply_profile_delta(districts[cid], delta)
        district_deltas[cid] = delta
        _merge_delta(city_delta, delta)

    for cid in spillovers:
        delta = dict(template.spillover_effects)
        delta = _land_use_adjusted_effects(delta, districts[cid], archetype)
        _merge_delta(delta, _service_coverage_effect(archetype, districts[cid], "spillover"))
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
        for cid in targets:
            _apply_land_use_change(districts[cid], archetype)
            normalize_profile(districts[cid])

    population_deltas = _apply_population_reaction(
        template,
        [districts[cid] for cid in targets],
        "failure" if failure_triggered else "approve",
        mitigated,
    )
    for cid, delta in population_deltas.items():
        _merge_delta(district_deltas.setdefault(cid, {}), delta)
    if not failure_triggered:
        long_term_deltas = apply_template_long_term_effects(template, [districts[cid] for cid in targets], mitigated)
        for cid, delta in long_term_deltas.items():
            _merge_delta(district_deltas.setdefault(cid, {}), delta)
    surfaced = _surface_new_incidents(state, [districts[cid] for cid in targets])

    averaged = {metric: round(value / max(1, len(targets) + len(spillovers))) for metric, value in city_delta.items()}
    _apply_city_delta(state, averaged)
    if surfaced:
        averaged["unrest"] = averaged.get("unrest", 0) + surfaced
    affected = targets + spillovers
    _settle_item_violations(item, mitigated)
    mitigation_text = " with mitigation" if mitigated else ""
    failure_text = ""
    if failure_triggered:
        failure_text = f" Outcome failed: {template.failure_mode}; corrective delta {_format_delta(failure_delta)}."
    project_text = ""
    if projects is not None and not failure_triggered:
        if template.starts_chain_id:
            project = start_project_from_approval(state, item, template, targets)
            if project:
                projects[project.project_id] = project
                project_text = f" Project {project.project_id} opened; next step {project.current_step_id} due turn {project.due_turn}."
        elif item.project_id:
            project = advance_project_from_item(projects, item, state, approved=True, failed=False)
            if project:
                project_text = f" Project {project.project_id} status {project.status}; current step {project.current_step_id}."
    elif projects is not None and failure_triggered and item.project_id:
        project = advance_project_from_item(projects, item, state, approved=True, failed=True)
        if project:
            project_text = f" Project {project.project_id} status {project.status}."
    report = (
        f"Approved {item.title}{mitigation_text}. Affected {len(affected)} district(s): "
        f"{', '.join(affected)}. City delta: {_format_delta(averaged)}.{failure_text} "
        f"{_population_report_fragment([districts[cid] for cid in targets])}{project_text}"
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


def _resolve_maintenance_decision(
    state: CityState,
    item: DocketItem,
    action: str,
    action_key: str,
    targets: list[str],
    template: DocketTemplate,
    mitigated: bool,
    active_features: Iterable[FeatureInstance] | None,
) -> DecisionResult:
    features = list(active_features or ())
    feature = next((candidate for candidate in features if candidate.feature_id == item.subject_feature_id), None)
    if action_key == "inspect":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Maintenance inspection requires 1 AP.")
        state.ap -= 1
        item.inspected = True
        item.status = "inspected"
        condition = feature.condition if feature else 0
        item.risk_band = "high" if condition <= 10 else "medium" if condition < 35 else "low"
        item.case_json = dict(item.case_json or {})
        item.case_json["inspection"] = inspection_case_for_item(item, (), fallback_risk_band=item.risk_band)
        item.preview_text = f"{template.preview} Inspection: referenced feature condition {condition}."
        return DecisionResult(True, action, item.item_id, f"Inspection completed for {item.title}: {item.preview_text}", affected_cell_ids=targets, item_status=item.status)

    if feature is None:
        return _blocked(action, item.item_id, "Maintenance order requires a referenced active feature.")
    rule = operating_rule_for_feature(feature)
    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Deferring maintenance requires 1 AP.")
        state.ap -= 1
        item.status = "deferred"
        feature.status = "maintenance_due"
        feature.display_state = "maintenance_due"
        heat_delta = _adjust_heat(state, feature.owner_group or "maintenance_office", template.denial_heat)
        delta = {"risk": 1}
        _apply_city_delta(state, delta)
        return DecisionResult(
            True,
            action,
            item.item_id,
            f"Deferred {item.title}. Maintenance remains open; heat {heat_delta:+d}.",
            delta,
            targets,
            item_status=item.status,
            stakeholder_delta={feature.owner_group or "maintenance_office": heat_delta},
            feature_updates={feature.feature_id: feature_update_payload(feature)},
        )

    if action_key not in ("approve", "approve_mitigated"):
        return _blocked(action, item.item_id, f"Unknown decision action {action!r}.")
    total_money = max(template.money_cost, rule.maintenance_cost) + (template.mitigation_cost if mitigated else 0)
    if state.ap < template.ap_cost:
        return _blocked(action, item.item_id, f"Maintenance requires {template.ap_cost} AP.")
    if state.money < total_money:
        return _blocked(action, item.item_id, f"Maintenance requires ${total_money}.")

    state.ap -= template.ap_cost
    state.money -= total_money
    repair = rule.repair_amount + (20 if mitigated else 0)
    feature.condition = max(0, min(100, feature.condition + repair))
    feature.last_maintained_turn = state.turn
    if rule.maintenance_interval:
        feature.maintenance_due_turn = state.turn + rule.maintenance_interval + (1 if mitigated else 0)
    feature.status = "active" if feature.condition > rule.degrade_threshold else "degraded"
    feature.display_state = feature.status
    feature.state_json = dict(feature.state_json or {})
    feature.state_json.pop("failure_applied", None)
    item.status = "settled" if mitigated else "maintained"
    _settle_item_violations(item, mitigated)
    delta = _mitigate(template.base_effects) if mitigated else dict(template.base_effects)
    _apply_city_delta(state, delta)
    return DecisionResult(
        True,
        action,
        item.item_id,
        f"Maintained {item.title}. Feature condition is now {feature.condition}; next due turn {feature.maintenance_due_turn}.",
        delta,
        targets,
        item_status=item.status,
        feature_updates={feature.feature_id: feature_update_payload(feature)},
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
    projects: dict[str, ProjectRecord] | None = None,
) -> DecisionResult:
    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Deferring enforcement requires 1 AP.")
        state.ap -= 1
        item.status = "deferred"
        delta = {"unrest": 2, "risk": 1}
        _apply_city_delta(state, delta)
        heat_delta = _adjust_heat(state, item.stakeholder, template.denial_heat)
        project_note = ""
        if projects and item.project_id:
            project = advance_project_from_item(projects, item, state, approved=False)
            if project:
                project_note = f" Project {project.project_id} delayed."
        report = (
            f"Deferred enforcement for {item.title}. The unpermitted condition remains useful to someone; "
            f"{item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}.{project_note}"
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
    _settle_item_violations(item, mitigated)
    project_note = ""
    if projects and item.project_id:
        project = advance_project_from_item(projects, item, state, approved=True, failed=False)
        if project:
            project_note = f" Project {project.project_id} status {project.status}."
    if mitigated:
        report = (
            f"Settled {item.title} through a retroactive permit and compliance schedule. "
            f"City delta: {_format_delta(averaged)}. {item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}.{project_note}"
        )
    else:
        report = (
            f"Enforced {item.title}. The record is clearer and several people are louder. "
            f"City delta: {_format_delta(averaged)}. {item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}.{project_note}"
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


def _resolve_incident_decision(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile],
    action: str,
    action_key: str,
    targets: list[str],
    spillovers: list[str],
    template: DocketTemplate,
    mitigated: bool,
    projects: dict[str, ProjectRecord] | None = None,
) -> DecisionResult:
    if not targets:
        return _blocked(action, item.item_id, "Incident response requires one selected district.")
    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Deferring a civic incident requires 1 AP.")
        state.ap -= 1
        item.status = "deferred"
        group = item.stakeholder if item.stakeholder in CITIZEN_GROUPS else _top_dissatisfaction(districts[targets[0]])[0]
        for cid in targets:
            _adjust_dissatisfaction(districts[cid], (group,), 1)
            normalize_profile(districts[cid])
        delta = {"unrest": 2, "risk": 1}
        _apply_city_delta(state, delta)
        heat_delta = _adjust_heat(state, group, template.denial_heat)
        project_note = ""
        if projects and item.project_id:
            project = advance_project_from_item(projects, item, state, approved=False)
            if project:
                project_note = f" Project {project.project_id} delayed."
        report = (
            f"Deferred {item.title}. The incident remains local in form and citywide in tone. "
            f"City delta: {_format_delta(delta)}. {_group_label(group).title()} heat {heat_delta:+d}.{project_note}"
        )
        return DecisionResult(
            True,
            action,
            item.item_id,
            report,
            delta,
            targets,
            {cid: {"dissatisfaction": 1} for cid in targets},
            item.status,
            stakeholder_delta={group: heat_delta},
        )

    if action_key not in ("approve", "approve_mitigated"):
        return _blocked(action, item.item_id, f"Unknown decision action {action!r}.")
    if state.ap < template.ap_cost:
        return _blocked(action, item.item_id, f"Incident response requires {template.ap_cost} AP.")
    total_money = template.money_cost + (template.mitigation_cost if mitigated else 0)
    if state.money < total_money:
        return _blocked(action, item.item_id, f"Incident response requires ${total_money}.")

    state.ap -= template.ap_cost
    state.money -= total_money
    item.target_cell_ids = targets
    item.status = "settled" if mitigated else "responded"
    group = item.stakeholder if item.stakeholder in CITIZEN_GROUPS else _top_dissatisfaction(districts[targets[0]])[0]
    relief = -3 if mitigated else -2
    base = _mitigate(template.base_effects) if mitigated else dict(template.base_effects)
    spill = _mitigate(template.spillover_effects) if mitigated else dict(template.spillover_effects)
    district_deltas: dict[str, dict[str, int]] = {}
    city_delta = {metric: 0 for metric in CORE_METRICS}

    for cid in targets:
        _apply_profile_delta(districts[cid], base)
        _adjust_dissatisfaction(districts[cid], (group,), relief)
        normalize_profile(districts[cid])
        district_deltas[cid] = dict(base)
        district_deltas[cid]["dissatisfaction"] = relief
        _merge_delta(city_delta, base)

    for cid in spillovers:
        delta = dict(spill)
        _apply_profile_delta(districts[cid], delta)
        _adjust_dissatisfaction(districts[cid], (group,), -1)
        normalize_profile(districts[cid])
        district_deltas[cid] = delta
        district_deltas[cid]["dissatisfaction"] = -1
        _merge_delta(city_delta, delta)

    averaged = {metric: round(value / max(1, len(targets) + len(spillovers))) for metric, value in city_delta.items()}
    _apply_city_delta(state, averaged)
    heat_delta = _adjust_heat(state, group, -1 if mitigated else 0)
    _settle_item_violations(item, mitigated)
    mode_text = "settled with conditions" if mitigated else "accepted for formal response"
    project_note = ""
    if projects and item.project_id:
        project = advance_project_from_item(projects, item, state, approved=True, failed=False)
        if project:
            project_note = f" Project {project.project_id} status {project.status}."
    report = (
        f"{item.title} {mode_text}. Target group: {_group_label(group)}. "
        f"City delta: {_format_delta(averaged)}. {_population_report_fragment([districts[cid] for cid in targets])}{project_note}"
    )
    return DecisionResult(
        True,
        action,
        item.item_id,
        report,
        averaged,
        targets + spillovers,
        district_deltas,
        item.status,
        stakeholder_delta={group: heat_delta} if heat_delta else {},
    )


__all__ = [name for name in globals() if not name.startswith("__")]
