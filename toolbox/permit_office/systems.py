"""Long-running city systems for projects, features, hazards, and housing."""

from __future__ import annotations

from typing import Iterable

from .models import *
from .catalogs import *
from .helpers import *


def project_step_template(chain_template_id: str, step_id: str) -> ProjectStepTemplate | None:
    """Find a project step in a chain template."""

    chain = PROJECT_CHAINS.get(chain_template_id)
    if not chain:
        return None
    for step in chain.steps:
        if step.step_id == step_id:
            return step
    return None


def next_project_step(chain_template_id: str, step_id: str) -> ProjectStepTemplate | None:
    """Return the next configured project step after the current one."""

    chain = PROJECT_CHAINS.get(chain_template_id)
    current = project_step_template(chain_template_id, step_id)
    if not chain or not current or not current.next_step_id:
        return None
    return project_step_template(chain_template_id, current.next_step_id)


def start_project_from_approval(
    state: CityState,
    item: DocketItem,
    template: DocketTemplate,
    target_cell_ids: Iterable[str],
) -> ProjectRecord | None:
    """Create a project record when an approval starts a project chain."""

    chain_id = template.starts_chain_id
    if not chain_id:
        return None
    chain = PROJECT_CHAINS.get(chain_id)
    if not chain:
        return None
    initial = project_step_template(chain_id, template.project_step_id or chain.initial_step_id)
    if not initial:
        return None
    next_step = next_project_step(chain_id, initial.step_id)
    current_step = next_step or initial
    project_id = f"P{state.turn:02d}-{item.item_id}"
    record = ProjectRecord(
        project_id=project_id,
        chain_template_id=chain_id,
        current_step_id=current_step.step_id,
        status="active" if next_step else "settled",
        turn_started=state.turn,
        due_turn=state.turn + max(1, current_step.due_after),
        stakeholder=item.stakeholder or template.stakeholder,
        target_cell_ids=list(target_cell_ids),
        payload={"source_item_id": item.item_id, "source_template_id": template.template_id},
        last_report=f"{chain.label} created from {item.title}.",
    )
    item.project_id = record.project_id
    item.chain_step_id = initial.step_id
    return record


def advance_project_from_item(
    projects: dict[str, ProjectRecord],
    item: DocketItem,
    state: CityState,
    approved: bool,
    failed: bool = False,
) -> ProjectRecord | None:
    """Move an existing project according to the resolved docket item."""

    if not item.project_id or item.project_id not in projects:
        return None
    project = projects[item.project_id]
    step = project_step_template(project.chain_template_id, item.chain_step_id or project.current_step_id)
    if not step:
        return None
    if not approved:
        project.status = "delayed"
        project.due_turn = state.turn + 1
        project.last_report = f"{step.title} delayed from docket action."
        return project
    if failed:
        if step.failure_step_id:
            failure_step = project_step_template(project.chain_template_id, step.failure_step_id)
            if failure_step:
                project.current_step_id = failure_step.step_id
                project.status = step.status_on_failure
                project.due_turn = state.turn + max(1, failure_step.due_after)
                project.last_report = f"{step.title} failed; {failure_step.title} is now due."
                return project
        project.status = step.status_on_failure
        project.last_report = f"{step.title} failed."
        return project
    next_step = next_project_step(project.chain_template_id, step.step_id)
    if next_step:
        project.current_step_id = next_step.step_id
        project.status = "active"
        project.due_turn = state.turn + max(1, next_step.due_after)
        project.last_report = f"{step.title} approved; {next_step.title} due turn {project.due_turn}."
    else:
        project.status = step.status_on_approval if step.status_on_approval in ("settled", "complete", "active") else "settled"
        project.last_report = f"{step.title} settled {PROJECT_CHAINS[project.chain_template_id].label}."
    return project


def active_feature_instances(features: Iterable[FeatureInstance], turn: int | None = None) -> list[FeatureInstance]:
    """Return features that still participate in city systems."""

    active_status = {"active", "settled", "enforced", "responded", "maintenance_due", "degraded"}
    out = []
    for feature in features:
        if feature.status not in active_status:
            continue
        if turn is not None and feature.expires_turn not in (-1, 0, None) and feature.expires_turn < turn:
            continue
        if feature.archetype_id not in FEATURE_ARCHETYPES:
            continue
        out.append(feature)
    return out


def recompute_network_access(
    districts: dict[str, DistrictProfile],
    features: Iterable[FeatureInstance],
    turn: int | None = None,
) -> dict[str, dict[str, int]]:
    """Recompute service network access from active spatial features."""

    for profile in districts.values():
        profile.network_access = {service: 0 for service in SERVICE_TYPES}
    # Active spatial features contribute weighted service access to selected
    # districts and adjacent districts before service gaps are recalculated.
    for feature in active_feature_instances(features, turn):
        archetype = FEATURE_ARCHETYPES[feature.archetype_id]
        network_type = feature.network_type or archetype.network_type or feature.service_type or archetype.service_type
        if network_type not in SERVICE_TYPES:
            continue
        strength = max(1, int(feature.intensity or feature.capacity or archetype.network_strength or archetype.capacity or 1))
        for cid, weight in _feature_spatial_weights(feature, districts).items():
            if cid not in districts:
                continue
            value = _weighted_band(strength, weight)
            districts[cid].network_access[network_type] = min(12, districts[cid].network_access.get(network_type, 0) + value)
    for profile in districts.values():
        normalize_profile(profile)
    return {cid: dict(profile.network_access) for cid, profile in districts.items()}


def apply_hazard_turn(
    districts: dict[str, DistrictProfile],
    features: Iterable[FeatureInstance],
    turn: int | None = None,
) -> dict[str, int]:
    """Advance district hazard bands from sources, mitigations, and decay."""

    sources = {cid: {hazard: 0 for hazard in HAZARD_TYPES} for cid in districts}
    mitigations = {cid: {hazard: 0 for hazard in HAZARD_TYPES} for cid in districts}
    # Feature hazard and mitigation effects are gathered first so each district
    # can resolve source, decay, and mitigation in a single pass.
    for feature in active_feature_instances(features, turn):
        archetype = FEATURE_ARCHETYPES[feature.archetype_id]
        hazard_effects = _instance_effect_map(feature, archetype, "hazard_effects")
        mitigation_effects = _instance_effect_map(feature, archetype, "mitigation_effects")
        for cid, weight in _feature_spatial_weights(feature, districts).items():
            if cid not in districts:
                continue
            for hazard, amount in hazard_effects.items():
                if hazard in HAZARD_TYPES and amount > 0:
                    sources[cid][hazard] += _weighted_band(amount, weight)
            for hazard, amount in mitigation_effects.items():
                if hazard in HAZARD_TYPES and amount > 0:
                    mitigations[cid][hazard] += _weighted_band(amount, weight)
    for cid, profile in districts.items():
        for hazard, amount in _service_hazard_mitigation(profile).items():
            mitigations[cid][hazard] += amount

    severe = 0
    for cid, profile in districts.items():
        current = _normalize_service_map(profile.hazards, HAZARD_TYPES, maximum=4, include_zeros=True)
        next_hazards: dict[str, int] = {}
        for hazard in HAZARD_TYPES:
            source = sources[cid][hazard]
            mitigation = mitigations[cid][hazard]
            rule = HAZARD_RULES[hazard]
            if source:
                band = min(4, current.get(hazard, 0) + source)
            else:
                band = max(0, current.get(hazard, 0) - rule.decay)
            band = max(0, band - mitigation)
            if band:
                next_hazards[hazard] = min(4, band)
            if band >= 4:
                severe += 1
        profile.hazards = next_hazards
        _apply_hazard_pressure(profile)
        normalize_profile(profile)
    return {"severe_hazards": severe}


def apply_housing_dynamics(districts: dict[str, DistrictProfile]) -> dict[str, int]:
    """Advance housing capacity pressure and related population shifts."""

    population_delta = 0
    pressured = 0
    for profile in districts.values():
        before = profile.population
        normalize_profile(profile)
        pressure = max(profile.displacement.values(), default=0)
        if pressure >= 2:
            pressured += 1
            _adjust_dissatisfaction(profile, ("renters", "elders", "artists", "families"), 1 if pressure < 4 else 2)
        if pressure >= 3:
            _shift_mix(profile, ("renters", "artists"), -1)
            _shift_mix(profile, ("homeowners", "developers"), 1)
        if profile.housing_capacity and profile.population > profile.housing_capacity:
            profile.population = max(100, profile.population - max(4, (profile.population - profile.housing_capacity) // 3))
        normalize_profile(profile)
        population_delta += profile.population - before
    return {"housing_population_delta": population_delta, "displacement_pressure": pressured}


def apply_template_long_term_effects(template: DocketTemplate, profiles: Iterable[DistrictProfile], mitigated: bool = False) -> dict[str, dict[str, int]]:
    """Apply non-immediate housing and hazard effects from an approved template."""

    deltas: dict[str, dict[str, int]] = {}
    for profile in profiles:
        before = {
            "population": profile.population,
            "housing_capacity": profile.housing_capacity,
            "affordability": profile.affordability,
        }
        _apply_housing_effects(profile, template.housing_effects)
        if mitigated and template.hazard_effects:
            profile.hazards = {
                hazard: max(0, profile.hazards.get(hazard, 0) - 1)
                for hazard in HAZARD_TYPES
                if profile.hazards.get(hazard, 0)
            }
        else:
            _apply_hazard_effects(profile, template.hazard_effects)
        normalize_profile(profile)
        delta = {
            "population": profile.population - before["population"],
            "housing_capacity": profile.housing_capacity - before["housing_capacity"],
            "affordability": profile.affordability - before["affordability"],
        }
        deltas[profile.cell_id] = {key: value for key, value in delta.items() if value}
    return deltas


def apply_scenario(state: CityState, districts: dict[str, DistrictProfile], scenario_id: str | None = None) -> None:
    """Apply a scenario's starting biases to city and district state."""

    if scenario_id:
        state.scenario_id = scenario_id
    scenario = SCENARIO_RULES.get(state.scenario_id, SCENARIO_RULES["default"])
    _apply_city_delta(state, scenario.starting_city_effects)
    for profile in districts.values():
        _apply_profile_delta(profile, {key: value for key, value in scenario.starting_district_effects.items() if key in DISTRICT_METRICS})
        _apply_housing_effects(profile, {key: value for key, value in scenario.starting_district_effects.items() if key not in DISTRICT_METRICS})
        _apply_hazard_effects(profile, scenario.hazard_bias)
        normalize_profile(profile)


def _feature_spatial_weights(feature: FeatureInstance, districts: dict[str, DistrictProfile]) -> dict[str, float]:
    """Return target and adjacent-district weights for a feature instance."""

    targets = [cid for cid in feature.target_cell_ids if cid in districts]
    weights: dict[str, float] = {}
    for cid in targets:
        weights[cid] = max(weights.get(cid, 0.0), 1.0)
    # Feature classes only persist selected district IDs; adjacency gives
    # network and hazard systems a cheap stand-in for buffer overlap.
    neighbor_weight = 0.5
    for cid in targets:
        for adjacent in districts[cid].adjacent_cell_ids:
            if adjacent in districts and adjacent not in targets:
                weights[adjacent] = max(weights.get(adjacent, 0.0), neighbor_weight)
    return weights


def _weighted_band(amount: int, weight: float) -> int:
    """Scale a banded effect by spatial weight while preserving small effects."""

    if amount <= 0 or weight <= 0:
        return 0
    return max(1, round(amount * weight))


def _instance_effect_map(feature: FeatureInstance, archetype: FeatureArchetype, key: str) -> dict[str, int]:
    """Read archetype effects with feature metadata overrides."""

    values = getattr(archetype, key)
    out = {str(name): int(value) for name, value in values.items() if int(value or 0)}
    raw = feature.metadata.get(key)
    if isinstance(raw, dict):
        for name, value in raw.items():
            try:
                amount = int(value or 0)
            except (TypeError, ValueError):
                continue
            if amount:
                out[str(name)] = amount
    return out


def _service_hazard_mitigation(profile: DistrictProfile) -> dict[str, int]:
    """Convert service network access into hazard mitigation bands."""

    mitigation = {hazard: 0 for hazard in HAZARD_TYPES}
    for hazard, rule in HAZARD_RULES.items():
        for service, amount in rule.mitigation_service_types.items():
            access = profile.network_access.get(service, 0)
            if access:
                mitigation[hazard] += min(amount, max(1, access // 3))
    return {hazard: amount for hazard, amount in mitigation.items() if amount > 0}


def _apply_hazard_pressure(profile: DistrictProfile) -> None:
    """Apply risk, unrest, and grievance pressure from active hazards."""

    risk_delta = 0
    unrest_delta = 0
    for hazard, band in _normalize_service_map(profile.hazards, HAZARD_TYPES, maximum=4, include_zeros=False).items():
        rule = HAZARD_RULES[hazard]
        if band >= rule.risk_threshold:
            risk_delta += band - rule.risk_threshold + 1
            _adjust_dissatisfaction(profile, rule.affected_groups, 1 if band < 4 else 2)
        if band >= rule.unrest_threshold:
            unrest_delta += 1
    if risk_delta or unrest_delta:
        _apply_profile_delta(profile, {"risk": risk_delta, "unrest": unrest_delta})


def _apply_housing_effects(profile: DistrictProfile, effects: dict[str, int]) -> None:
    """Apply housing capacity, population, and affordability effects."""

    if not effects:
        return
    if "housing_capacity" in effects or "capacity" in effects:
        profile.housing_capacity = max(0, int(profile.housing_capacity) + int(effects.get("housing_capacity", effects.get("capacity", 0)) or 0))
    if "population" in effects:
        profile.population = max(100, int(profile.population) + int(effects.get("population", 0) or 0))
    if "affordability" in effects:
        profile.affordability = _clamp(int(profile.affordability) + int(effects.get("affordability", 0) or 0))
    if "vacancy_rate" in effects and profile.housing_capacity:
        extra_capacity = round(profile.housing_capacity * int(effects.get("vacancy_rate", 0) or 0) / 100)
        profile.housing_capacity = max(0, profile.housing_capacity + extra_capacity)


def _apply_hazard_effects(profile: DistrictProfile, effects: dict[str, int]) -> None:
    """Apply direct hazard band changes to one profile."""

    if not effects:
        return
    hazards = _normalize_service_map(profile.hazards, HAZARD_TYPES, maximum=4, include_zeros=True)
    for hazard, amount in effects.items():
        if hazard not in HAZARD_TYPES:
            continue
        hazards[hazard] = max(0, min(4, hazards.get(hazard, 0) + int(amount or 0)))
    profile.hazards = {hazard: band for hazard, band in hazards.items() if band > 0}




def operating_rule_for_feature(feature_or_archetype_id: FeatureInstance | str) -> FeatureOperatingRule:
    """Return lifecycle economics for a feature, falling back to defaults."""

    archetype_id = feature_or_archetype_id.archetype_id if isinstance(feature_or_archetype_id, FeatureInstance) else feature_or_archetype_id
    return FEATURE_OPERATING_RULES.get(archetype_id, FeatureOperatingRule(archetype_id, upkeep_per_turn=1, decay_per_turn=5, maintenance_interval=3, maintenance_cost=6))


def normalize_feature_instance(feature: FeatureInstance, turn: int | None = None) -> FeatureInstance:
    """Fill derived feature fields and clamp lifecycle state."""

    archetype = FEATURE_ARCHETYPES.get(feature.archetype_id)
    if archetype:
        feature.family = feature.family or archetype.family
        feature.service_type = feature.service_type or archetype.service_type
        feature.network_type = feature.network_type or archetype.network_type or archetype.service_type
        feature.capacity = feature.capacity or archetype.capacity
        feature.display_state = feature.display_state or archetype.display_state
    rule = operating_rule_for_feature(feature)
    feature.intensity = max(1, int(feature.intensity or 1))
    feature.condition = max(0, min(100, int(feature.condition if feature.condition is not None else 100)))
    if feature.turn_created <= 0 and turn is not None:
        feature.turn_created = max(1, turn)
    if rule.lifespan_turns and feature.expires_turn in (-1, 0, None):
        feature.expires_turn = max(1, feature.turn_created) + rule.lifespan_turns
    if rule.maintenance_interval and feature.maintenance_due_turn in (-1, 0, None):
        feature.maintenance_due_turn = max(1, feature.turn_created) + rule.maintenance_interval
    if feature.status == "active" and feature.condition <= rule.degrade_threshold:
        feature.status = "degraded" if feature.condition > rule.failure_threshold else "failed"
    feature.display_state = feature.status
    feature.state_json = dict(feature.state_json or {})
    feature.metadata = dict(feature.metadata or {})
    return feature


def feature_update_payload(feature: FeatureInstance) -> dict[str, object]:
    """Return the ArcGIS fields that need updating after lifecycle changes."""

    return {
        "status": feature.status,
        "condition": feature.condition,
        "maintenance_due_turn": feature.maintenance_due_turn,
        "last_maintained_turn": feature.last_maintained_turn,
        "display_state": feature.display_state,
        "state_json": dict(feature.state_json or {}),
    }


def _advance_feature_lifecycle(
    state: CityState,
    districts: dict[str, DistrictProfile],
    features: list[FeatureInstance],
    next_turn: int,
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, int]]]:
    """Decay active features, surface maintenance status, and collect updates."""

    updates: dict[str, dict[str, object]] = {}
    district_deltas: dict[str, dict[str, int]] = {}
    backlog = 0
    for feature in features:
        before = feature_update_payload(normalize_feature_instance(feature, state.turn))
        rule = operating_rule_for_feature(feature)
        if feature.status in ("proposed", "expired"):
            continue
        # Lifecycle state advances from expiration, decay, and maintenance due
        # dates before one-shot failure effects are applied to districts.
        if feature.expires_turn not in (-1, 0, None) and next_turn >= feature.expires_turn:
            feature.status = "expired"
        elif feature.status != "failed":
            if rule.decay_per_turn:
                feature.condition = max(0, feature.condition - rule.decay_per_turn)
            if rule.maintenance_interval and feature.maintenance_due_turn not in (-1, 0, None) and next_turn >= feature.maintenance_due_turn:
                feature.status = "maintenance_due"
            if feature.condition <= rule.failure_threshold:
                feature.status = "failed"
            elif feature.condition <= rule.degrade_threshold and feature.status == "active":
                feature.status = "degraded"
        if feature.status in ("maintenance_due", "degraded", "failed"):
            backlog += 1
        if feature.status == "failed" and not feature.state_json.get("failure_applied"):
            # Failure effects are one-shot so repeated turn advances do not compound them.
            for cid in feature.target_cell_ids:
                if cid not in districts:
                    continue
                _apply_profile_delta(districts[cid], rule.failure_effects)
                _merge_delta(district_deltas.setdefault(cid, {}), rule.failure_effects)
            averaged = {metric: round(value / max(1, len(feature.target_cell_ids))) for metric, value in rule.failure_effects.items() if metric in CORE_METRICS}
            _apply_city_delta(state, averaged)
            feature.state_json["failure_applied"] = True
        feature.display_state = feature.status
        after = feature_update_payload(feature)
        if after != before:
            updates[feature.feature_id] = after
    state.maintenance_backlog = backlog
    return updates, district_deltas


def _apply_recurring_economy(
    state: CityState,
    districts: dict[str, DistrictProfile],
    features: list[FeatureInstance],
) -> tuple[int, int, int]:
    """Compute turn revenue, upkeep, and net money from districts and features."""

    district_revenue = 0
    # District revenue rewards healthy population centers and penalizes risk or
    # unrest before feature-specific economics are added.
    for profile in districts.values():
        raw = profile.population // 1000
        raw += max(0, profile.prosperity - 40) // 25
        raw += max(0, profile.culture - 55) // 35
        raw -= max(0, profile.unrest - 55) // 30
        raw -= max(0, profile.risk - 55) // 30
        district_revenue += max(0, min(2, raw))
    district_revenue = min(24, district_revenue)

    feature_revenue = 0
    upkeep = 0
    # Only operating features contribute revenue or upkeep; degraded and due
    # features still cost money but produce less income.
    for feature in features:
        normalize_feature_instance(feature, state.turn)
        if feature.status not in ("active", "settled", "enforced", "responded", "maintenance_due", "degraded"):
            continue
        rule = operating_rule_for_feature(feature)
        revenue = rule.revenue_per_turn * feature.intensity
        if feature.status in ("maintenance_due", "degraded"):
            revenue = revenue // 2
        feature_revenue += revenue
        upkeep += rule.upkeep_per_turn * feature.intensity
        if feature.status == "maintenance_due":
            upkeep += 1
    revenue = district_revenue + feature_revenue
    net = revenue - upkeep
    state.money += net
    state.last_revenue = revenue
    state.last_upkeep = upkeep
    state.last_net = net
    return revenue, upkeep, net


__all__ = [name for name in globals() if not name.startswith("__")]
