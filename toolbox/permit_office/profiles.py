"""Profile, docket, and inspection generation for the rules package."""

from __future__ import annotations

import random
from typing import Iterable

from .models import *
from .catalogs import *
from .helpers import *
from .systems import normalize_feature_instance, project_step_template


def generate_district_profiles(rows: int = 5, cols: int = 5, seed: int = 2026) -> list[DistrictProfile]:
    """Generate deterministic district profiles for a rectangular board."""

    rng = random.Random(seed)
    prefixes = ["North", "Old", "Canal", "Bright", "Lower", "Cinder", "Glass", "Civic"]
    suffixes = ["Ward", "Market", "Steps", "Yard", "Row", "Crossing", "Annex", "Green"]
    profiles: list[DistrictProfile] = []
    for row in range(rows):
        for col in range(cols):
            cell_id = f"D{row:02d}{col:02d}"
            dtype = DISTRICT_TYPES[(row + col + rng.randrange(len(DISTRICT_TYPES))) % len(DISTRICT_TYPES)]
            base = 30 + rng.randrange(36)
            prosperity = max(10, min(90, base + rng.randrange(-12, 13)))
            unrest = max(5, min(80, 28 + rng.randrange(-14, 15)))
            culture = max(10, min(90, 34 + rng.randrange(-14, 22)))
            risk = max(5, min(80, 26 + rng.randrange(-12, 18)))
            services = max(5, min(90, 35 + rng.randrange(-15, 16)))
            population_mix = _initial_population_mix(dtype, rng)
            dissatisfaction = _initial_dissatisfaction(population_mix, prosperity, unrest, risk, services)
            profile = DistrictProfile(
                cell_id=cell_id,
                name=f"{rng.choice(prefixes)} {rng.choice(suffixes)}",
                population=650 + rng.randrange(2200),
                prosperity=prosperity,
                unrest=unrest,
                culture=culture,
                risk=risk,
                services=services,
                district_type=dtype,
                population_mix=population_mix,
                dissatisfaction=dissatisfaction,
            )
            normalize_profile(profile)
            profiles.append(profile)
    assign_grid_adjacency(profiles, rows, cols)
    for profile in profiles:
        normalize_profile(profile)
    return profiles


def generate_docket(
    turn: int,
    seed: int = 2026,
    count: int = 3,
    state: CityState | None = None,
    districts: dict[str, DistrictProfile] | None = None,
    projects: Iterable[ProjectRecord] | dict[str, ProjectRecord] | None = None,
    active_features: Iterable[FeatureInstance] | None = None,
) -> list[DocketItem]:
    """Generate the current turn docket, including due follow-up items first."""

    scenario = SCENARIO_RULES.get(state.scenario_id if state else "default", SCENARIO_RULES["default"])
    chosen = _scenario_ordered_templates(turn, scenario)
    if len(chosen) < count:
        rng = random.Random(seed * 1000 + turn)
        pool = [template_id for template_id in DEMO_TEMPLATE_IDS if template_id not in chosen]
        chosen.extend(rng.sample(pool, min(count - len(chosen), len(pool))))

    items: list[DocketItem] = []
    for due in _project_due_items(turn, projects):
        if len(items) >= count:
            break
        items.append(due)

    if active_features:
        followup = _maintenance_followup_item(turn, active_features)
        if followup and len(items) < count:
            items.append(followup)

    if districts:
        followup = _incident_followup_item(turn, districts)
        if followup and len(items) < count:
            items.append(followup)

    if state:
        followup = _heat_followup_item(turn, state)
        if followup and len(items) < count:
            items.append(followup)

    # Fill remaining docket slots with the deterministic demo sequence after
    # mandatory follow-up work has been given priority.
    for template_id in chosen:
        if len(items) >= count:
            break
        items.append(_make_docket_item(turn, len(items) + 1, template_id))
    return items


def _scenario_ordered_templates(turn: int, scenario: ScenarioRule) -> list[str]:
    """Merge scenario-priority templates ahead of the base demo sequence."""

    chosen: list[str] = []
    for template_id in scenario.docket_priority:
        if template_id in TEMPLATES and template_id not in chosen:
            chosen.append(template_id)
    for template_id in DEMO_SEQUENCE.get(turn, ()):
        if template_id not in chosen:
            chosen.append(template_id)
    return chosen


def _project_due_items(turn: int, projects: Iterable[ProjectRecord] | dict[str, ProjectRecord] | None) -> list[DocketItem]:
    """Convert due project records into docket items for the current turn."""

    if not projects:
        return []
    records = projects.values() if isinstance(projects, dict) else projects
    due: list[tuple[int, str, ProjectRecord, ProjectStepTemplate]] = []
    for project in records:
        if project.status not in ("active", "delayed", "overdue"):
            continue
        if project.due_turn > turn:
            continue
        step = project_step_template(project.chain_template_id, project.current_step_id)
        if step:
            due.append((project.due_turn, project.project_id, project, step))
    out: list[DocketItem] = []
    # Each due project step reuses its template, but carries project ids and
    # targets forward so the decision resolver can advance the chain.
    for idx, (_due_turn, _project_id, project, step) in enumerate(sorted(due, key=lambda row: (row[0], row[1])), start=1):
        item = _make_docket_item(turn, idx, step.template_id, stakeholder=step.stakeholder or project.stakeholder, origin_item_id=f"project:{project.project_id}")
        item.project_id = project.project_id
        item.chain_step_id = step.step_id
        item.target_cell_ids = list(project.target_cell_ids)
        if project.due_turn < turn:
            item.preview_text = f"{item.preview_text} Project step is overdue from turn {project.due_turn}."
        else:
            item.preview_text = f"{item.preview_text} Project step due this turn."
        out.append(item)
    return out


def _make_docket_item(turn: int, idx: int, template_id: str, stakeholder: str = "", origin_item_id: str = "") -> DocketItem:
    """Instantiate a docket item and specialize follow-up case labels."""

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
    elif template.is_incident and item_stakeholder != template.stakeholder:
        label = _group_label(item_stakeholder).title()
        title = f"Civic Incident Response: {label}"
        item_id = f"T{turn:02d}-{idx:02d}-{template_id}-{item_stakeholder}"
        preview = f"{template.preview} Incident file is currently attached to {label}."
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
        chain_step_id=template.project_step_id,
    )


def _heat_followup_item(turn: int, state: CityState) -> DocketItem | None:
    """Return the highest-priority stakeholder heat follow-up due this turn."""

    hot = []
    for stakeholder, heat in state.stakeholder_heat.items():
        profile = _stakeholder_profile(stakeholder)
        if heat >= profile.escalation_threshold and turn >= state.stakeholder_memory.get(stakeholder, 0):
            hot.append((stakeholder, heat, _stakeholder_escalation_score(stakeholder, heat)))
    if not hot:
        return None
    stakeholder, _heat, _score = sorted(hot, key=lambda row: (-row[2], row[0]))[0]
    template_id = _stakeholder_profile(stakeholder).followup_template_id
    if template_id not in TEMPLATES:
        template_id = ENFORCEMENT_TEMPLATE_ID
    return _make_docket_item(turn, 1, template_id, stakeholder=stakeholder, origin_item_id="stakeholder_heat")


def _maintenance_followup_item(turn: int, active_features: Iterable[FeatureInstance]) -> DocketItem | None:
    """Return the most urgent feature maintenance item, if one is due."""

    candidates = []
    for feature in active_features:
        normalize_feature_instance(feature, turn)
        if feature.status in ("maintenance_due", "degraded", "failed"):
            candidates.append((feature.condition, feature.feature_id, feature))
    if not candidates:
        return None
    _condition, _feature_id, feature = sorted(candidates, key=lambda row: (row[0], row[1]))[0]
    item = _make_docket_item(turn, 1, MAINTENANCE_TEMPLATE_ID, stakeholder=feature.owner_group or "maintenance_office", origin_item_id=f"feature:{feature.feature_id}")
    item.title = f"Maintenance Order: {feature.archetype_id.replace('_', ' ').title()}"
    item.subject_feature_id = feature.feature_id
    item.target_cell_ids = list(feature.target_cell_ids)
    item.priority = 3 if feature.status == "failed" else 2 if feature.status == "degraded" else 1
    item.due_turn = turn + 1
    item.case_json = {
        "maintenance": {
            "feature_id": feature.feature_id,
            "archetype_id": feature.archetype_id,
            "condition": feature.condition,
            "status": feature.status,
        }
    }
    item.preview_text = f"{item.preview_text} Feature {feature.feature_id} is {feature.status} at condition {feature.condition}."
    return item


def _incident_followup_item(turn: int, districts: dict[str, DistrictProfile]) -> DocketItem | None:
    """Return the earliest visible local grievance that needs civic response."""

    visible = []
    for profile in districts.values():
        normalize_profile(profile)
        if profile.incident_state != "none" and profile.incident_group:
            visible.append((profile.incident_state, profile.incident_group, profile.cell_id))
    if not visible:
        return None
    incident_state, group, cell_id = sorted(visible, key=lambda row: (row[2], row[1], row[0]))[0]
    item = _make_docket_item(turn, 1, CIVIC_INCIDENT_TEMPLATE_ID, stakeholder=group, origin_item_id=f"dissatisfaction:{cell_id}:{group}")
    item.target_cell_ids = [cell_id]
    item.preview_text = f"{item.preview_text} Visible condition: {incident_state} in {cell_id}."
    return item


def inspect_item(item: DocketItem, seed: int = 2026, target_profiles: Iterable[DistrictProfile] | None = None) -> DocketItem:
    """Attach deterministic inspection evidence and risk to a docket item."""

    template = TEMPLATES[item.template_id]
    rng = random.Random(f"{seed}:{item.item_id}:inspect")
    profiles = list(target_profiles or ())
    item.inspected = True
    item.stakeholder = item.stakeholder or template.stakeholder
    item.target_rule = item.target_rule or template.target_rule
    item.risk_band = rng.choice(["low", "medium", "medium", "high"])
    inspection_case = inspection_case_for_item(item, profiles, seed=seed, fallback_risk_band=item.risk_band)
    item.risk_band = str(inspection_case["risk_band"])
    item.case_json = dict(item.case_json or {})
    item.case_json["inspection"] = inspection_case
    failure_text = f" Failure mode on file: {template.failure_mode}." if template.failure_mode else ""
    population_text = inspection_population_note(template, profiles)
    evidence_text = _inspection_summary_text(inspection_case)
    consequence_text = _inspection_consequence_text(template, inspection_case)
    item.preview_text = (
        f"Inspection: filed {item.risk_band.upper()} side-effect risk. Certain effects if approved: "
        f"{_format_delta(template.base_effects)}. Risk/side effects: {consequence_text}{failure_text} "
        f"{template.inspect_hint} {population_text} {evidence_text}"
    ).strip()
    return item


def inspection_case_for_item(
    item: DocketItem,
    target_profiles: Iterable[DistrictProfile],
    seed: int = 2026,
    fallback_risk_band: str = "medium",
) -> dict[str, object]:
    """Build structured inspection evidence and violations for a docket item."""

    template = TEMPLATES[item.template_id]
    rule = INSPECTION_RULES.get(template.template_id, INSPECTION_RULES["default"])
    profiles = list(target_profiles)
    rng = random.Random(f"{seed}:{item.item_id}:evidence")
    avg_risk = sum(profile.risk for profile in profiles) / max(1, len(profiles))
    avg_services = sum(profile.services for profile in profiles) / max(1, len(profiles))
    max_grievance = max((_top_dissatisfaction(profile)[1] for profile in profiles), default=0)

    # Evidence codes are catalog data; this branch translates each code into
    # context-sensitive severity without making templates carry game math.
    evidence: list[EvidenceRecord] = []
    for code in rule.evidence_codes:
        severity = "watch"
        note = "Routine file check."
        if code == "service_gap":
            if avg_services < 25:
                severity = "critical"
                note = "Service capacity is already below the operating floor."
            elif avg_services < 40:
                severity = "warning"
                note = "Service capacity is thin enough to affect compliance."
            else:
                note = "Service capacity can absorb the request."
        elif code == "unsafe_work":
            if avg_risk >= 65:
                severity = "critical"
                note = "Site risk is high enough to require follow-through."
            elif avg_risk >= 45:
                severity = "warning"
                note = "Site risk is visible in the inspection worksheet."
            else:
                note = "No acute site safety concern is visible."
        elif code == "public_nuisance":
            if max_grievance >= DISSATISFACTION_INCIDENT_THRESHOLD:
                severity = "critical"
                note = "Local grievance is already incident-ready."
            elif max_grievance >= DISSATISFACTION_AGGRIEVED_THRESHOLD:
                severity = "warning"
                note = "Local grievance is aggrieved."
            elif rng.random() < 0.35:
                severity = "watch"
                note = "Public comment is noisy but not decisive."
        elif code == "maintenance_overdue":
            severity = "warning"
            note = "Referenced support feature has an open maintenance condition."
        elif rng.random() < 0.2:
            severity = "warning"
            note = "The file is mostly consistent but needs one assumption checked."
        label = VIOLATION_CODES.get(code, {}).get("label", code.replace("_", " ").title())
        evidence.append(EvidenceRecord(f"{item.item_id}:{code}", label, severity, code, note))

    # Risk bands intentionally derive from evidence, then violations inherit
    # the band so inspections and later compliance audits agree.
    severity_score = sum({"watch": 1, "warning": 2, "critical": 4}.get(record.severity, 1) for record in evidence)
    if any(record.severity == "critical" for record in evidence) or severity_score >= 6:
        risk_band = "high"
    elif any(record.severity == "warning" for record in evidence) or severity_score >= 3:
        risk_band = "medium"
    else:
        risk_band = fallback_risk_band if fallback_risk_band in {"low", "medium", "high"} else "low"

    violations: list[ViolationRecord] = []
    if risk_band in {"medium", "high"}:
        severity = "critical" if risk_band == "high" else "warning"
        deadline = item.turn + (1 if severity == "critical" else rule.deadline_turns)
        for code in rule.violation_codes:
            evidence_ids = tuple(record.evidence_id for record in evidence if record.source == code)
            violations.append(
                ViolationRecord(
                    f"{item.item_id}:{code}",
                    code,
                    severity,
                    deadline,
                    evidence_ids=evidence_ids,
                )
            )

    return {
        "rule_id": rule.rule_id,
        "risk_band": risk_band,
        "evidence": [record.__dict__ for record in evidence],
        "violations": [record.__dict__ | {"evidence_ids": list(record.evidence_ids)} for record in violations],
    }


def _inspection_summary_text(inspection_case: dict[str, object]) -> str:
    """Format structured inspection evidence into short packet text."""

    evidence = inspection_case.get("evidence", [])
    violations = inspection_case.get("violations", [])
    if not evidence:
        return ""
    worst = "watch"
    for record in evidence:
        if isinstance(record, dict) and record.get("severity") == "critical":
            worst = "critical"
            break
        if isinstance(record, dict) and record.get("severity") == "warning":
            worst = "warning"
    violation_text = f" Violations opened: {len(violations)}." if violations else ""
    return f"Evidence filed: {len(evidence)} item(s), highest severity {worst}.{violation_text}"


def _inspection_consequence_text(template: DocketTemplate, inspection_case: dict[str, object]) -> str:
    """Format sharper post-inspection consequence hints for previews."""

    risk = str(inspection_case.get("risk_band") or "unknown").lower()
    violations = inspection_case.get("violations", [])
    if risk == "high":
        base = f"{template.failure_mode or 'approval failure'} is a live risk"
    elif risk == "medium":
        base = f"{template.failure_mode or 'side effects'} should be watched"
    elif risk == "low":
        base = "no acute side-effect flag"
    else:
        base = "side-effect review is incomplete"
    if violations:
        return f"{base}; {len(violations)} compliance deadline(s) may follow."
    return f"{base}; no compliance deadline opened."


__all__ = [name for name in globals() if not name.startswith("__")]
