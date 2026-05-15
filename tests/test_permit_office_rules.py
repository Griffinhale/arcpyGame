import copy

from toolbox import arcpy_permit_office_rules as rules


def test_generate_district_profiles_is_deterministic_and_named():
    first = rules.generate_district_profiles(rows=2, cols=2, seed=2026)
    second = rules.generate_district_profiles(rows=2, cols=2, seed=2026)

    assert first == second
    assert [profile.cell_id for profile in first] == ["D0000", "D0001", "D0100", "D0101"]
    assert all(profile.name for profile in first)
    assert {profile.district_type for profile in first} <= set(rules.DISTRICT_TYPES)
    assert set(rules.DISTRICT_TYPES) == {"residential", "mercantile", "industrial", "civic", "academic", "natural"}
    assert {profile.display_state for profile in first} <= set(rules.DISPLAY_STATES)


def test_demo_template_catalog_has_case_file_metadata():
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


def test_generate_docket_has_three_seeded_items_with_templates():
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
    seen = set()
    for turn in range(1, 7):
        docket = rules.generate_docket(turn=turn, seed=2026, count=3)
        assert len(docket) == 3
        seen.update(item.template_id for item in docket)

    assert set(rules.DEMO_TEMPLATE_IDS) <= seen


def test_inspect_item_marks_item_and_adds_risk_band_hint():
    item = rules.generate_docket(turn=1, seed=2026, count=1)[0]

    inspected = rules.inspect_item(item, seed=2026)

    assert inspected is item
    assert item.inspected is True
    assert item.risk_band in {"low", "medium", "high"}
    assert "Inspection:" in item.preview_text


def test_approve_applies_costs_district_deltas_and_city_delta():
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


def test_mitigation_reduces_bad_side_effects_and_costs_more():
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


def test_high_risk_bad_fit_approval_can_fail():
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


def test_advance_turn_resets_ap_and_marks_audit_stage():
    state = rules.CityState(turn=2, ap=0, max_ap=3)
    items = rules.generate_docket(turn=2, seed=2026, count=3)

    report = rules.advance_turn(state, items)

    assert "Advanced turn" in report
    assert state.turn == 3
    assert state.ap == 3
    assert state.audit_stage == 1
    assert {item.status for item in items} <= {"carried", "expired"}


def test_scorecard_returns_audit_grade_and_metrics():
    state = rules.CityState(prosperity=70, culture=60, unrest=20, risk=15, money=45)

    grade, report = rules.scorecard(state)

    assert grade == "PASS"
    assert "prosperity=70" in report
    assert "risk=15" in report
