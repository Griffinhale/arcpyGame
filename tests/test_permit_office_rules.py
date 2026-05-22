"""Regression coverage for the active Permit Office rules package."""

import copy
from pathlib import Path

from toolbox import arcpy_permit_office_rules as rules


def test_generate_district_profiles_is_deterministic_and_named():
    """Verify seeded district generation is stable and fully normalized."""
    first = rules.generate_district_profiles(rows=2, cols=2, seed=2026)
    second = rules.generate_district_profiles(rows=2, cols=2, seed=2026)

    assert first == second
    assert [profile.cell_id for profile in first] == ["D0000", "D0001", "D0100", "D0101"]
    assert all(profile.name for profile in first)
    assert {profile.district_type for profile in first} <= set(rules.DISTRICT_TYPES)
    assert set(rules.DISTRICT_TYPES) == {"residential", "mercantile", "industrial", "civic", "academic", "natural"}
    assert {profile.display_state for profile in first} <= set(rules.DISPLAY_STATES)
    assert all(profile.public_profile for profile in first)
    assert all(set(profile.population_mix) == set(rules.CITIZEN_GROUPS) for profile in first)
    assert all(0 <= band <= 3 for profile in first for band in profile.population_mix.values())
    assert all(0 <= band <= 4 for profile in first for band in profile.dissatisfaction.values())


def test_demo_template_catalog_has_case_file_metadata():
    """Verify demo templates include the metadata needed for case files."""
    assert len(rules.DEMO_TEMPLATE_IDS) == 10
    assert set(rules.DEMO_TEMPLATE_IDS) < set(rules.TEMPLATES)
    for template_id in rules.DEMO_TEMPLATE_IDS:
        template = rules.TEMPLATES[template_id]
        assert template.target_rule
        assert template.stakeholder
        assert template.preview
        assert template.inspect_hint
        assert template.failure_mode
        assert template.failure_effects
        assert template.spawn_archetype_id in rules.FEATURE_ARCHETYPES


def test_feature_archetype_catalog_is_valid_and_covers_all_templates():
    """Verify templates resolve to valid feature archetypes and metadata."""
    assert rules.validate_feature_catalog() == []
    assert {"business", "public_resource", "natural_resource", "infrastructure", "event", "land_use", "incident", "compliance"} <= set(rules.FEATURE_FAMILIES)
    for template_id, template in rules.TEMPLATES.items():
        archetype = rules.feature_archetype_for_template(template_id)
        metadata = rules.feature_metadata_for_template(template)
        assert archetype.archetype_id == template.spawn_archetype_id
        assert archetype.geometry_type == template.geometry_type
        assert metadata["archetype_id"] == archetype.archetype_id


def test_generate_docket_has_three_seeded_items_with_templates():
    """Verify the first seeded docket has three valid template-backed cases."""
    docket = rules.generate_docket(turn=1, seed=2026, count=3)

    assert len(docket) == 3
    assert len({item.item_id for item in docket}) == 3
    assert [item.template_id for item in docket] == ["connector_corridor", "procession_route", "street_vendor_compact"]
    assert all(item.template_id in rules.TEMPLATES for item in docket)
    assert all(item.preview_text for item in docket)
    assert all(item.stakeholder for item in docket)
    assert all(item.target_rule for item in docket)
    assert {item.geometry_type for item in docket} <= {"POINT", "LINE", "POLYGON"}


def test_six_turn_demo_sequence_covers_shortlist():
    """Verify the deterministic demo schedule covers every shortlist case."""
    expected = {
        1: ["connector_corridor", "procession_route", "street_vendor_compact"],
        2: ["utility_expansion_trench", "contractor_renovation_waiver", "public_art_museum_grant"],
        3: ["natural_reserve_conversion", "mixed_use_rezoning", "fire_budget_escalation"],
        4: ["child_development_park_annex", "street_vendor_compact", "utility_expansion_trench"],
        5: ["connector_corridor", "mixed_use_rezoning", "public_art_museum_grant"],
        6: ["natural_reserve_conversion", "fire_budget_escalation", "procession_route"],
    }
    seen = set()
    for turn in range(1, 7):
        docket = rules.generate_docket(turn=turn, seed=2026, count=3)
        assert len(docket) == 3
        assert [item.template_id for item in docket] == expected[turn]
        seen.update(item.template_id for item in docket)

    assert set(rules.DEMO_TEMPLATE_IDS) <= seen


def _active_feature_from_route_item(item, turn):
    """Build a normalized feature instance from an approved route item."""
    template = rules.TEMPLATES[item.template_id]
    archetype = rules.feature_archetype_for_template(template)
    feature = rules.FeatureInstance(
        feature_id=f"F-{item.item_id}",
        archetype_id=archetype.archetype_id,
        item_id=item.item_id,
        template_id=item.template_id,
        owner_group=item.stakeholder or template.stakeholder,
        target_cell_ids=list(item.target_cell_ids),
        capacity=archetype.capacity,
        intensity=max(1, archetype.capacity or 1),
        status=item.status,
        turn_created=turn,
    )
    return rules.normalize_feature_instance(feature, turn)


def test_seed_2026_golden_route_produces_stable_conditional_scorecard():
    """Verify the six-turn golden route preserves its conditional audit result."""
    profiles = {profile.cell_id: profile for profile in rules.generate_district_profiles(seed=2026)}
    state = rules.CityState()
    active_features = []
    docket_history = []
    action_counts = {"inspect": 0, "approve": 0, "approve_mitigated": 0, "deny": 0}
    generated_followup_seen = False

    route = {
        1: [
            ("street_vendor_compact", "approve_mitigated", ["D0102"], ["D0101"], True),
            ("connector_corridor", "approve", ["D0101", "D0102"], [], False),
        ],
        2: [
            ("utility_expansion_trench", "approve", ["D0004", "D0104"], [], False),
            ("contractor_renovation_waiver", "deny", ["D0000"], [], False),
        ],
        3: [
            (rules.MAINTENANCE_TEMPLATE_ID, "approve", ["D0102"], [], False),
            ("natural_reserve_conversion", "approve", ["D0200", "D0304"], [], False),
        ],
        4: [
            (rules.CIVIC_INCIDENT_TEMPLATE_ID, "approve", ["D0001"], [], False),
            ("child_development_park_annex", "deny", ["D0000"], [], False),
            ("street_vendor_compact", "deny", ["D0102"], [], False),
        ],
    }
    expected_route_dockets = {
        1: ["connector_corridor", "procession_route", "street_vendor_compact"],
        2: ["utility_expansion_trench", "contractor_renovation_waiver", "public_art_museum_grant"],
        3: [rules.MAINTENANCE_TEMPLATE_ID, "natural_reserve_conversion", "mixed_use_rezoning"],
        4: [rules.CIVIC_INCIDENT_TEMPLATE_ID, "child_development_park_annex", "street_vendor_compact"],
        5: [rules.MAINTENANCE_TEMPLATE_ID, rules.CIVIC_INCIDENT_TEMPLATE_ID, "connector_corridor"],
        6: [rules.MAINTENANCE_TEMPLATE_ID, rules.CIVIC_INCIDENT_TEMPLATE_ID, rules.CIVIC_INCIDENT_TEMPLATE_ID],
    }

    # Each turn regenerates the visible docket from current state, then applies
    # only the scripted player actions for this golden-route scenario.
    for turn in range(1, 7):
        docket = rules.generate_docket(
            turn=state.turn,
            seed=2026,
            count=3,
            state=state,
            districts=profiles,
            active_features=active_features,
        )
        assert [item.template_id for item in docket] == expected_route_dockets[turn]
        generated_followup_seen = generated_followup_seen or any(
            item.template_id == rules.MAINTENANCE_TEMPLATE_ID for item in docket
        )

        for template_id, action, targets, spillovers, inspect_first in route.get(turn, []):
            item = next(item for item in docket if item.template_id == template_id)
            if inspect_first:
                inspected = rules.resolve_decision(
                    state,
                    item,
                    profiles,
                    "inspect",
                    targets,
                    seed=2026,
                    active_features=active_features,
                )
                assert inspected.ok is True
                action_counts["inspect"] += 1

            result = rules.resolve_decision(
                state,
                item,
                profiles,
                action,
                targets,
                spillover_cell_ids=spillovers,
                seed=2026,
                mitigated=action == "approve_mitigated",
                active_features=active_features,
            )
            assert result.ok is True
            action_counts[action] += 1
            if item.status in {"active", "failed", "enforced", "settled", "responded", "maintained"} and item.template_id != rules.MAINTENANCE_TEMPLATE_ID:
                active_features.append(_active_feature_from_route_item(item, state.turn))

        docket_history.extend(docket)
        if turn < 6:
            rules.advance_turn_result(state, docket, profiles, active_features)

    # Final assertions pin the resulting audit, resources, and feature mix so
    # future balance changes are intentional.
    archetypes = {feature.archetype_id for feature in active_features}
    grade, report = rules.scorecard(state, profiles, active_features, docket_history)

    assert action_counts["inspect"] >= 1
    assert action_counts["approve"] >= 1
    assert action_counts["approve_mitigated"] >= 1
    assert action_counts["deny"] >= 1
    assert generated_followup_seen is True
    assert {"vendor_market", "connector_corridor", "utility_trench", "protected_reserve"} <= archetypes
    assert grade == "CONDITIONAL"
    assert state.money == 15
    assert (state.prosperity, state.unrest, state.culture, state.risk) == (60, 21, 46, 7)
    assert "score=56" in report
    assert "4 finding(s), 0 critical" in report


def test_inspect_item_marks_item_and_adds_risk_band_hint():
    """Verify inspection mutates the item with risk and packet text."""
    item = rules.generate_docket(turn=1, seed=2026, count=1)[0]

    inspected = rules.inspect_item(item, seed=2026)

    assert inspected is item
    assert item.inspected is True
    assert item.risk_band in {"low", "medium", "high"}
    assert "Inspection:" in item.preview_text


def test_inspect_item_adds_target_population_context_when_available():
    """Verify inspections include local population support and grievance notes."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Petition Row",
        population=1200,
        prosperity=45,
        unrest=25,
        culture=40,
        risk=25,
        services=55,
        district_type="residential",
        population_mix={"families": 3, "renters": 2, "commuters": 1},
        dissatisfaction={"renters": 3},
    )
    rules.normalize_profile(profile)
    item = rules.DocketItem(
        "inspect-park",
        "child_development_park_annex",
        rules.TEMPLATES["child_development_park_annex"].title,
        "POINT",
        1,
    )

    rules.inspect_item(item, seed=2026, target_profiles=[profile])

    assert "Census review:" in item.preview_text
    assert "Strongest likely supporter: families" in item.preview_text
    assert "Highest local grievance: renters are aggrieved" in item.preview_text


def test_approve_applies_costs_district_deltas_and_city_delta():
    """Verify a normal approval spends resources and updates city/district state."""
    profiles = {p.cell_id: p for p in rules.generate_district_profiles(rows=2, cols=2, seed=2026)}
    state = rules.CityState(ap=3, money=60)
    item = rules.DocketItem(
        item_id="T01-03-street_vendor_compact",
        template_id="street_vendor_compact",
        title=rules.TEMPLATES["street_vendor_compact"].title,
        geometry_type="POINT",
        turn=1,
    )

    result = rules.resolve_decision(
        state,
        item,
        profiles,
        action="approve",
        target_cell_ids=["D0000"],
        spillover_cell_ids=["D0001", "D0100"],
        seed=2026,
    )

    assert result.ok is True
    assert item.status in {"active", "failed"}
    assert state.ap == 2
    assert state.money == 48
    assert result.affected_cell_ids == ["D0000", "D0001", "D0100"]
    assert "Approved" in result.report
    assert result.city_delta
    assert profiles["D0000"].display_state in rules.DISPLAY_STATES


def test_approval_adjusts_population_pressure_and_local_grievance():
    """Verify approval changes population mix, growth, and local grievance bands."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Applicant Yard",
        population=1000,
        prosperity=50,
        unrest=20,
        culture=35,
        risk=20,
        services=60,
        district_type="residential",
        population_mix={"families": 2, "commuters": 1},
        dissatisfaction={"families": 2},
    )
    rules.normalize_profile(profile)
    profiles = {profile.cell_id: profile}
    state = rules.CityState(ap=3, money=80)
    item = rules.DocketItem(
        "approve-park",
        "child_development_park_annex",
        rules.TEMPLATES["child_development_park_annex"].title,
        "POINT",
        1,
        risk_band="low",
    )

    result = rules.resolve_decision(state, item, profiles, "approve_mitigated", ["D0000"], seed=4, mitigated=True)

    assert result.ok is True
    assert profile.population > 1000
    assert profile.population_mix["families"] == 3
    assert profile.dissatisfaction["families"] == 1
    assert "Population file:" in result.report


def test_service_archetype_updates_services_and_land_use_overlay():
    """Verify service features improve local service gaps after approval."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Undercovered Row",
        population=1800,
        prosperity=45,
        unrest=20,
        culture=35,
        risk=55,
        services=15,
        district_type="residential",
        population_mix={"families": 3, "commuters": 1},
        dissatisfaction={"families": 1},
    )
    rules.normalize_profile(profile)
    profiles = {profile.cell_id: profile}
    state = rules.CityState(ap=3, money=80)
    item = rules.DocketItem(
        "approve-child-service",
        "child_development_park_annex",
        rules.TEMPLATES["child_development_park_annex"].title,
        "POINT",
        1,
        risk_band="low",
    )

    result = rules.resolve_decision(state, item, profiles, "approve", ["D0000"], seed=5)

    assert result.ok is True
    assert profile.services > 15
    assert result.district_deltas["D0000"]["services"] > 0
    assert profile.service_gap.get("child_services", 0) < 30


def test_land_use_overlay_is_applied_to_successful_zone_approval():
    """Verify successful zoning approvals persist their overlay on districts."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Rezoning Row",
        population=1300,
        prosperity=45,
        unrest=20,
        culture=35,
        risk=25,
        services=60,
        district_type="residential",
    )
    rules.normalize_profile(profile)
    profiles = {profile.cell_id: profile}
    state = rules.CityState(ap=3, money=80)
    item = rules.DocketItem(
        "approve-rezoning",
        "mixed_use_rezoning",
        rules.TEMPLATES["mixed_use_rezoning"].title,
        "POLYGON",
        1,
        risk_band="low",
    )

    result = rules.resolve_decision(state, item, profiles, "approve_mitigated", ["D0000"], seed=42, mitigated=True)

    assert result.ok is True
    assert item.status == "active"
    assert profile.zoning_overlay == "mixed_use"


def test_mitigation_reduces_bad_side_effects_and_costs_more():
    """Verify mitigated approvals cost more and dampen harmful deltas."""
    base_profiles = {p.cell_id: p for p in rules.generate_district_profiles(rows=2, cols=2, seed=10)}
    mitigated_profiles = copy.deepcopy(base_profiles)
    base_state = rules.CityState(ap=3, money=80)
    mitigated_state = rules.CityState(ap=3, money=80)
    base_item = rules.DocketItem("waiver-base", "contractor_renovation_waiver", rules.TEMPLATES["contractor_renovation_waiver"].title, "POINT", 1)
    mitigated_item = rules.DocketItem("waiver-mitigated", "contractor_renovation_waiver", rules.TEMPLATES["contractor_renovation_waiver"].title, "POINT", 1)

    base = rules.resolve_decision(base_state, base_item, base_profiles, "approve", ["D0000"], seed=10)
    mitigated = rules.resolve_decision(
        mitigated_state,
        mitigated_item,
        mitigated_profiles,
        "approve_mitigated",
        ["D0000"],
        seed=10,
        mitigated=True,
    )

    assert base.ok is True
    assert mitigated.ok is True
    assert mitigated_state.money < base_state.money
    assert mitigated.district_deltas["D0000"].get("risk", 0) <= base.district_deltas["D0000"].get("risk", 0)
    assert mitigated.district_deltas["D0000"].get("unrest", 0) <= base.district_deltas["D0000"].get("unrest", 0)


def test_deny_costs_ap_and_adds_small_city_friction():
    """Verify denial spends AP and applies small city and stakeholder costs."""
    profiles = {p.cell_id: p for p in rules.generate_district_profiles(rows=1, cols=1, seed=2026)}
    state = rules.CityState(ap=3, money=60, unrest=20, prosperity=50)
    item = rules.DocketItem("deny-me", "fire_budget_escalation", rules.TEMPLATES["fire_budget_escalation"].title, "POLYGON", 1)

    result = rules.resolve_decision(state, item, profiles, "deny", ["D0000"], seed=2026)

    assert result.ok is True
    assert item.status == "denied"
    assert state.ap == 2
    assert state.unrest == 21
    assert state.prosperity == 49
    assert state.stakeholder_heat["fire_department"] == 3
    assert "Denied" in result.report


def test_ignored_items_add_heat_and_heat_generates_enforcement_followup():
    """Verify ignored dockets create stakeholder heat and enforcement follow-up."""
    state = rules.CityState(turn=1, ap=0)
    items = [
        rules.DocketItem(
            "ignore-vendors",
            "street_vendor_compact",
            rules.TEMPLATES["street_vendor_compact"].title,
            "POINT",
            1,
        ),
        rules.DocketItem(
            "ignore-vendors-again",
            "street_vendor_compact",
            rules.TEMPLATES["street_vendor_compact"].title,
            "POINT",
            1,
        )
    ]

    report = rules.advance_turn(state, items)
    docket = rules.generate_docket(turn=state.turn, seed=2026, count=3, state=state)

    assert "Stakeholder heat added" in report
    assert state.stakeholder_heat["vendors"] >= rules.STAKEHOLDER_HEAT_THRESHOLD
    assert docket[0].template_id == rules.ENFORCEMENT_TEMPLATE_ID
    assert docket[0].stakeholder == "vendors"
    assert "Compliance Follow-Up" in docket[0].title


def test_enforcement_followup_can_be_settled_and_reduces_heat():
    """Verify enforcement settlement resolves the item and cools stakeholder heat."""
    profiles = {p.cell_id: p for p in rules.generate_district_profiles(rows=1, cols=1, seed=2026)}
    state = rules.CityState(ap=3, money=60, stakeholder_heat={"vendors": 4})
    item = rules.generate_docket(turn=2, seed=2026, count=1, state=state)[0]

    result = rules.resolve_decision(
        state,
        item,
        profiles,
        action="approve_mitigated",
        target_cell_ids=["D0000"],
        seed=2026,
        mitigated=True,
    )

    assert result.ok is True
    assert item.status == "settled"
    assert state.stakeholder_heat["vendors"] == 2
    assert "Settled" in result.report


def test_high_local_grievance_generates_civic_incident_followup():
    """Verify high local dissatisfaction surfaces as a civic incident docket."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Appeal Steps",
        population=1400,
        prosperity=40,
        unrest=35,
        culture=35,
        risk=30,
        services=35,
        district_type="residential",
        population_mix={"renters": 3, "families": 1},
        dissatisfaction={"renters": 4},
    )
    profiles = {profile.cell_id: profile}
    state = rules.CityState(turn=2)

    docket = rules.generate_docket(turn=2, seed=2026, count=3, state=state, districts=profiles)

    assert profiles["D0000"].incident_state == "protest"
    assert docket[0].template_id == rules.CIVIC_INCIDENT_TEMPLATE_ID
    assert docket[0].stakeholder == "renters"
    assert "Civic Incident Response" in docket[0].title


def test_civic_incident_response_lowers_dissatisfaction_and_clears_incident():
    """Verify civic incident response lowers grievance and clears incident state."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Formal Complaint Green",
        population=1400,
        prosperity=40,
        unrest=35,
        culture=35,
        risk=30,
        services=35,
        district_type="residential",
        population_mix={"renters": 3, "families": 1},
        dissatisfaction={"renters": 4},
    )
    profiles = {profile.cell_id: profile}
    state = rules.CityState(turn=2, ap=3, money=80)
    item = rules.generate_docket(turn=2, seed=2026, count=1, state=state, districts=profiles)[0]

    result = rules.resolve_decision(
        state,
        item,
        profiles,
        action="approve_mitigated",
        target_cell_ids=["D0000"],
        seed=2026,
        mitigated=True,
    )

    assert result.ok is True
    assert item.status == "settled"
    assert profile.dissatisfaction["renters"] == 1
    assert profile.incident_state == "none"
    assert "Target group: renters" in result.report


def test_high_risk_bad_fit_approval_can_fail():
    """Verify risky bad-fit approvals can trigger a failed outcome."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Low Service Reserve",
        population=1000,
        prosperity=35,
        unrest=30,
        culture=30,
        risk=90,
        services=5,
        district_type="natural",
    )
    profiles = {profile.cell_id: profile}
    state = rules.CityState(ap=3, money=80)
    item = rules.DocketItem(
        "fail-waiver",
        "contractor_renovation_waiver",
        rules.TEMPLATES["contractor_renovation_waiver"].title,
        "POINT",
        1,
        risk_band="high",
    )

    result = rules.resolve_decision(state, item, profiles, "approve", ["D0000"], seed=2026)

    assert result.ok is True
    assert result.failure_triggered is True
    assert item.status == "failed"
    assert "Outcome failed" in result.report


def test_land_use_conflict_increases_failure_chance():
    """Verify land-use conflict raises approval failure probability."""
    good = rules.DistrictProfile(
        cell_id="D0000",
        name="Market Fit",
        population=1000,
        prosperity=45,
        unrest=20,
        culture=35,
        risk=25,
        services=60,
        district_type="mercantile",
    )
    bad = rules.DistrictProfile(
        cell_id="D0001",
        name="Reserve Conflict",
        population=1000,
        prosperity=45,
        unrest=20,
        culture=35,
        risk=25,
        services=60,
        district_type="natural",
    )
    rules.normalize_profile(good)
    rules.normalize_profile(bad)
    template = rules.TEMPLATES["street_vendor_compact"]

    good_chance = rules._failure_chance(template, [good], "medium", mitigated=False)
    bad_chance = rules._failure_chance(template, [bad], "medium", mitigated=False)

    assert bad_chance > good_chance


def test_advance_turn_resets_ap_and_marks_audit_stage():
    """Verify turn advancement restores AP and updates audit stage."""
    state = rules.CityState(turn=2, ap=0, max_ap=3)
    items = rules.generate_docket(turn=2, seed=2026, count=3)

    report = rules.advance_turn(state, items)

    assert "Advanced turn" in report
    assert state.turn == 3
    assert state.ap == 3
    assert state.audit_stage == 1
    assert {item.status for item in items} <= {"carried", "expired"}


def test_advance_turn_applies_population_drift_and_unresolved_local_grievance():
    """Verify unresolved local cases and population drift apply during turn end."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Growing Annex",
        population=1200,
        prosperity=70,
        unrest=20,
        culture=40,
        risk=20,
        services=60,
        district_type="residential",
        population_mix={"families": 2, "renters": 1},
        dissatisfaction={"families": 0},
    )
    rules.normalize_profile(profile)
    profiles = {profile.cell_id: profile}
    state = rules.CityState(turn=2, ap=0, max_ap=3)
    item = rules.DocketItem(
        "ignored-park",
        "child_development_park_annex",
        rules.TEMPLATES["child_development_park_annex"].title,
        "POINT",
        2,
        target_cell_ids=["D0000"],
    )

    report = rules.advance_turn(state, [item], profiles)

    assert state.turn == 3
    assert state.ap == 3
    assert profile.population > 1200
    assert profile.dissatisfaction["families"] == 1
    assert "Local grievance files updated" in report
    assert "Population drift" in report


def test_scorecard_returns_audit_grade_and_metrics():
    """Verify scorecard reports a grade and key city metrics."""
    state = rules.CityState(prosperity=70, culture=60, unrest=20, risk=15, money=45)

    grade, report = rules.scorecard(state)

    assert grade == "PASS"
    assert "prosperity=70" in report
    assert "risk=15" in report


def test_long_term_catalogs_validate_new_city_system_records():
    """Verify long-term systems have complete catalog coverage."""
    assert rules.validate_feature_catalog() == []
    assert set(rules.HAZARD_TYPES) == {"pollution", "flood", "fire", "noise", "heat", "ecology"}
    assert {"bus_priority_link", "water_main_loop", "green_buffer_reserve", "inspection_order"} <= set(rules.FEATURE_ARCHETYPES)
    assert {"housing_mandate", "port_boom"} <= set(rules.SCENARIO_RULES)
    assert "affordable_infill_buildout" in rules.PROJECT_CHAINS


def test_generated_districts_have_adjacency_housing_and_empty_hazards():
    """Verify generated districts include adjacency, housing, and network fields."""
    profiles = {p.cell_id: p for p in rules.generate_district_profiles(rows=2, cols=2, seed=2026)}

    assert profiles["D0000"].adjacent_cell_ids == ["D0001", "D0100"]
    assert profiles["D0101"].adjacent_cell_ids == ["D0001", "D0100"]
    assert all(profile.housing_capacity >= profile.population for profile in profiles.values())
    assert all(0 <= profile.affordability <= 100 for profile in profiles.values())
    assert all(profile.hazards == {} for profile in profiles.values())
    assert all(set(profile.network_access) == set(rules.SERVICE_TYPES) for profile in profiles.values())


def test_line_network_access_affects_endpoints_and_one_hop_only():
    """Verify line networks affect endpoints and adjacent districts only."""
    profiles = {p.cell_id: p for p in rules.generate_district_profiles(rows=1, cols=4, seed=2026)}
    feature = rules.FeatureInstance(
        feature_id="bus-1",
        archetype_id="bus_priority_link",
        target_cell_ids=["D0000", "D0001"],
        intensity=3,
        status="active",
    )

    rules.recompute_network_access(profiles, [feature], turn=1)

    assert profiles["D0000"].network_access["mobility"] == 3
    assert profiles["D0001"].network_access["mobility"] == 3
    assert profiles["D0002"].network_access["mobility"] == 2
    assert profiles["D0003"].network_access["mobility"] == 0


def test_housing_effects_recompute_vacancy_and_displacement_pressure():
    """Verify housing effects recalculate vacancy and affordability fields."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Lease Row",
        population=950,
        prosperity=70,
        unrest=25,
        culture=66,
        risk=20,
        services=55,
        district_type="residential",
        population_mix={"renters": 3, "artists": 2, "families": 2},
        housing_capacity=1000,
        affordability=32,
    )
    rules.normalize_profile(profile)

    before_capacity = profile.housing_capacity
    rules.apply_template_long_term_effects(rules.TEMPLATES["occupancy_certificate"], [profile], mitigated=True)

    assert profile.housing_capacity == before_capacity + 420
    assert profile.population > 950
    assert profile.vacancy_rate > 0
    assert profile.affordability > 32


def test_hazards_accumulate_decay_and_are_reduced_by_mitigation():
    """Verify hazards accumulate, decay, and respond to mitigation features."""
    profiles = {p.cell_id: p for p in rules.generate_district_profiles(rows=1, cols=2, seed=2026)}
    source = rules.FeatureInstance("site-1", "construction_site", target_cell_ids=["D0000"], status="active", intensity=1)

    rules.apply_hazard_turn(profiles, [source], turn=1)
    assert profiles["D0000"].hazards["noise"] == 1
    assert profiles["D0001"].hazards["noise"] == 1

    rules.apply_hazard_turn(profiles, [], turn=2)
    assert profiles["D0000"].hazards.get("noise", 0) == 0

    profiles["D0000"].hazards = {"heat": 3, "ecology": 2}
    buffer = rules.FeatureInstance("buffer-1", "green_buffer_reserve", target_cell_ids=["D0000"], status="active", intensity=3)
    rules.recompute_network_access(profiles, [buffer], turn=3)
    rules.apply_hazard_turn(profiles, [buffer], turn=3)
    assert profiles["D0000"].hazards.get("heat", 0) <= 1


def test_project_chain_spawns_due_step_and_advances_on_resolution():
    """Verify project approvals create due steps and advance after resolution."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Buildout Row",
        population=1200,
        prosperity=50,
        unrest=20,
        culture=40,
        risk=20,
        services=65,
        district_type="residential",
    )
    rules.normalize_profile(profile)
    profiles = {profile.cell_id: profile}
    state = rules.CityState(ap=3, money=120)
    projects = {}
    item = rules.DocketItem("rezoning-1", "affordable_infill_rezoning", rules.TEMPLATES["affordable_infill_rezoning"].title, "POLYGON", 1, risk_band="low")

    result = rules.resolve_decision(state, item, profiles, "approve_mitigated", ["D0000"], seed=99, mitigated=True, projects=projects)

    assert result.ok is True
    assert projects
    project = next(iter(projects.values()))
    assert project.current_step_id == "construction"
    due = rules.generate_docket(turn=project.due_turn, seed=2026, count=1, state=state, districts=profiles, projects=projects)
    assert due[0].project_id == project.project_id
    assert due[0].chain_step_id == "construction"

    due[0].status = "active"
    rules.advance_project_from_item(projects, due[0], state, approved=True, failed=False)
    assert project.current_step_id == "inspection"


def test_scenario_rules_change_docket_priority_and_scorecard_text():
    """Verify scenarios alter docket priority and scorecard reporting."""
    state = rules.CityState(scenario_id="housing_mandate")
    profiles = {p.cell_id: p for p in rules.generate_district_profiles(rows=1, cols=2, seed=2026)}
    rules.apply_scenario(state, profiles)

    docket = rules.generate_docket(turn=1, seed=2026, count=3, state=state, districts=profiles)
    grade, report = rules.scorecard(state, profiles)

    assert docket[0].template_id == "affordable_infill_rezoning"
    assert grade in {"PASS", "CONDITIONAL", "FAIL"}
    assert "scenario=housing_mandate" in report


def test_governance_catalogs_cover_features_stakeholders_and_maintenance():
    """Verify governance catalogs include features, stakeholders, and inspections."""
    assert rules.validate_feature_catalog() == []
    assert rules.MAINTENANCE_TEMPLATE_ID in rules.TEMPLATES
    assert set(rules.FEATURE_ARCHETYPES) <= set(rules.FEATURE_OPERATING_RULES)
    assert rules.STAKEHOLDERS["fire_department"].influence > rules.STAKEHOLDERS["vendors"].patience
    assert rules.INSPECTION_RULES["contractor_renovation_waiver"].violation_codes == ("unsafe_work",)


def test_inspection_creates_evidence_violations_deadlines_and_compliance_outcomes():
    """Verify inspections create evidence, violations, and compliance outcomes."""
    profile = rules.DistrictProfile(
        cell_id="D0000",
        name="Inspection Row",
        population=1000,
        prosperity=35,
        unrest=35,
        culture=30,
        risk=70,
        services=20,
        district_type="residential",
        dissatisfaction={"renters": 3},
    )
    rules.normalize_profile(profile)
    item = rules.DocketItem("inspect-waiver", "contractor_renovation_waiver", rules.TEMPLATES["contractor_renovation_waiver"].title, "POINT", 2)

    rules.inspect_item(item, seed=7, target_profiles=[profile])

    inspection = item.case_json["inspection"]
    assert item.risk_band == "high"
    assert inspection["evidence"]
    assert inspection["violations"][0]["code"] == "unsafe_work"
    assert inspection["violations"][0]["deadline_turn"] == 3

    state = rules.CityState(ap=3, money=80)
    result = rules.resolve_decision(state, item, {profile.cell_id: profile}, "approve_mitigated", ["D0000"], seed=7, mitigated=True)

    assert result.ok is True
    assert item.case_json["inspection"]["violations"][0]["status"] == "complied"
    assert item.case_json["inspection"]["violations"][0]["compliance_outcome"] == "settled"


def test_feature_lifecycle_economy_and_maintenance_followup_are_deterministic():
    """Verify feature decay affects economy and generates maintenance follow-up."""
    profile = rules.DistrictProfile("D0000", "Service Yard", 1500, 55, 20, 40, 30, 45, "residential")
    rules.normalize_profile(profile)
    feature = rules.FeatureInstance(
        "F-child",
        "child_service_annex",
        item_id="permit-child",
        template_id="child_development_park_annex",
        owner_group="families",
        target_cell_ids=["D0000"],
        turn_created=1,
        condition=36,
    )
    state = rules.CityState(turn=1, money=30)

    result = rules.advance_turn_result(state, [], {profile.cell_id: profile}, [feature])
    docket = rules.generate_docket(state.turn, state=state, districts={profile.cell_id: profile}, active_features=[feature], count=3)

    assert state.last_revenue >= 0
    assert state.last_upkeep > 0
    assert state.money == 30 + state.last_net
    assert feature.status == "degraded"
    assert feature.feature_id in result.feature_updates
    assert docket[0].template_id == rules.MAINTENANCE_TEMPLATE_ID
    assert docket[0].subject_feature_id == "F-child"


def test_maintenance_decision_repairs_feature_and_reschedules_due_turn():
    """Verify maintenance decisions repair features and reschedule upkeep."""
    feature = rules.FeatureInstance("F-market", "vendor_market", owner_group="vendors", target_cell_ids=["D0000"], turn_created=1, condition=20, status="degraded")
    rules.normalize_feature_instance(feature, turn=3)
    profile = rules.DistrictProfile("D0000", "Market Row", 1000, 45, 25, 35, 25, 45, "mercantile")
    item = rules.generate_docket(3, active_features=[feature], count=1)[0]
    state = rules.CityState(turn=3, ap=3, money=50)

    result = rules.resolve_decision(state, item, {profile.cell_id: profile}, "approve_mitigated", item.target_cell_ids, mitigated=True, active_features=[feature])

    assert result.ok is True
    assert item.status == "settled"
    assert feature.condition > 20
    assert feature.status == "active"
    assert feature.maintenance_due_turn > state.turn
    assert result.feature_updates["F-market"]["condition"] == feature.condition


def test_audit_findings_include_money_features_services_and_violations():
    """Verify audits include money, feature, service, and inspection findings."""
    profile = rules.DistrictProfile("D0000", "Gap Row", 1400, 35, 25, 30, 75, 5, "residential", population_mix={"families": 3})
    rules.normalize_profile(profile)
    feature = rules.FeatureInstance("F-failed", "utility_trench", status="failed", condition=0, target_cell_ids=["D0000"])
    item = rules.DocketItem("case", "utility_expansion_trench", rules.TEMPLATES["utility_expansion_trench"].title, "LINE", 1, stakeholder="utility_board")
    item.case_json = {"inspection": {"violations": [{"code": "unsafe_work", "severity": "critical", "deadline_turn": 1, "status": "open"}]}}
    state = rules.CityState(turn=3, money=-1, last_net=-4)

    audit = rules.generate_audit_result(state, {profile.cell_id: profile}, [feature], [item])

    assert audit.grade == "FAIL"
    assert any(finding.source == "money" for finding in audit.findings)
    assert any(finding.source == "features" for finding in audit.findings)
    assert any(finding.source == "services" for finding in audit.findings)
    assert any(finding.source == "inspection" for finding in audit.findings)


def test_seeded_city_detail_descriptors_are_deterministic_and_moderate():
    """Verify New Game city texture can be planned without ArcPy."""
    profiles = {profile.cell_id: profile for profile in rules.generate_district_profiles(seed=2026)}

    first = rules.generate_city_detail_features(profiles, seed=2026)
    second = rules.generate_city_detail_features(profiles, seed=2026)

    assert first == second
    assert len(first) >= 70
    assert {feature.geometry_type for feature in first} == {"POINT", "LINE", "POLYGON"}
    assert {feature.status for feature in first} == {"active", "context"}
    assert sum(1 for feature in first if feature.status == "active") <= 5
    assert {"arterial_road", "utility_backbone", "neighborhood_park"} <= {feature.archetype_id for feature in first}
    assert {"residential_block", "commercial_block", "civic_building", "industrial_yard", "academic_block", "natural_patch"} <= {feature.archetype_id for feature in first}
    assert any(feature.capacity > 0 and feature.metadata.get("occupancy") for feature in first if feature.status == "context")
    assert any(feature.metadata.get("seed_role") == "point_of_interest" for feature in first if feature.geometry_type == "POINT")
    _assert_city_detail_rects_clear_road_lanes(first)


def _assert_city_detail_rects_clear_road_lanes(features):
    lanes_by_cell: dict[str, set[tuple[str, float]]] = {}
    for feature in features:
        if feature.geometry_type != "LINE":
            continue
        orientation = feature.geometry_hint.get("orientation")
        offset = float(feature.geometry_hint.get("offset", 0.50))
        if feature.geometry_hint.get("shape") == "corridor":
            offset = 0.50
        axis = "x" if orientation == "vertical" else "y"
        for cell_id in feature.target_cell_ids:
            lanes_by_cell.setdefault(cell_id, set()).add((axis, offset))

    for feature in features:
        if feature.geometry_type != "POLYGON" or feature.geometry_hint.get("shape") != "rect":
            continue
        hint = feature.geometry_hint
        x0 = float(hint["cx"]) - float(hint["w"]) / 2
        x1 = float(hint["cx"]) + float(hint["w"]) / 2
        y0 = float(hint["cy"]) - float(hint["h"]) / 2
        y1 = float(hint["cy"]) + float(hint["h"]) / 2
        for axis, offset in lanes_by_cell.get(feature.target_cell_ids[0], set()):
            if axis == "x":
                assert not x0 < offset < x1
            else:
                assert not y0 < offset < y1


def test_context_city_detail_does_not_participate_in_lifecycle_or_followups():
    """Verify visual-only context rows stay inert even when read as features."""
    profile = rules.DistrictProfile("D0000", "Context Row", 1800, 45, 20, 30, 25, 45, "residential", population_mix={"families": 3})
    rules.normalize_profile(profile)
    context = rules.FeatureInstance(
        "CITY-context",
        "residential_block",
        status="context",
        display_state="housing",
        condition=5,
        target_cell_ids=["D0000"],
        capacity=900,
        metadata={"occupancy": 900},
    )
    active = rules.FeatureInstance(
        "CITY-active",
        "arterial_road",
        status="active",
        display_state="road",
        condition=100,
        target_cell_ids=["D0000"],
    )
    state = rules.CityState(turn=1)

    result = rules.advance_turn_result(state, [], {profile.cell_id: profile}, [context, active])
    docket = rules.generate_docket(state.turn, active_features=[context], count=1)

    assert context.status == "context"
    assert context.display_state == "housing"
    assert context.feature_id not in result.feature_updates
    assert all(item.template_id != rules.MAINTENANCE_TEMPLATE_ID for item in docket)


def test_arcpy_toolbox_schema_declares_governance_fields_without_new_feature_classes():
    """Verify governance fields are declared without adding new map feature classes."""
    toolbox_dir = Path(__file__).parents[1] / "toolbox"
    toolbox_text = (toolbox_dir / "arcpy_permit_office.pyt").read_text()
    schema_text = (toolbox_dir / "permit_office_arcgis" / "schema.py").read_text()
    combined_text = toolbox_text + schema_text

    # Governance and city-system data rides existing feature classes, so this
    # guards against schema drift that would require new ArcGIS layers.
    for field_name in (
        "condition",
        "maintenance_due_turn",
        "last_maintained_turn",
        "state_json",
        "priority",
        "due_turn",
        "subject_feature_id",
        "case_json",
        "adjacent_cell_ids",
        "network_access_json",
        "hazard_json",
        "housing_capacity",
        "affordability",
        "vacancy_rate",
        "displacement_json",
        "project_id",
        "chain_step_id",
        "scenario_tags",
        "hazard_summary",
        "mitigation_summary",
    ):
        assert f'"{field_name}"' in combined_text
    assert '"PermitProjects"' in combined_text
    assert '"PermitPoints"' in combined_text
    assert '"PermitLines"' in combined_text
    assert '"PermitZones"' in combined_text


def test_active_permit_office_files_stay_under_line_budget():
    """Verify active source files remain below the reviewable line budget."""
    toolbox_dir = Path(__file__).parents[1] / "toolbox"
    # Keep the active ArcGIS toolbox small enough to review without counting archive files.
    active_paths = [
        toolbox_dir / "arcpy_permit_office.pyt",
        toolbox_dir / "arcpy_permit_office_rules.py",
        *sorted((toolbox_dir / "permit_office").glob("*.py")),
        *sorted((toolbox_dir / "permit_office" / "catalogs").glob("*.py")),
        *sorted((toolbox_dir / "permit_office_arcgis").glob("*.py")),
    ]

    oversized = {
        path.relative_to(toolbox_dir).as_posix(): len(path.read_text().splitlines())
        for path in active_paths
        if len(path.read_text().splitlines()) >= 1000
    }

    assert oversized == {}
