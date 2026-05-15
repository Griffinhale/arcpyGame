import copy

from toolbox import arcpy_permit_office_rules as rules


def test_generate_district_profiles_is_deterministic_and_named():
    first = rules.generate_district_profiles(rows=2, cols=2, seed=2026)
    second = rules.generate_district_profiles(rows=2, cols=2, seed=2026)

    assert first == second
    assert [profile.cell_id for profile in first] == ["D0000", "D0001", "D0100", "D0101"]
    assert all(profile.name for profile in first)
    assert {profile.district_type for profile in first} <= set(rules.DISTRICT_TYPES)
    assert {profile.display_state for profile in first} <= set(rules.DISPLAY_STATES)


def test_generate_docket_has_three_seeded_items_with_templates():
    docket = rules.generate_docket(turn=1, seed=2026, count=3)

    assert len(docket) == 3
    assert len({item.item_id for item in docket}) == 3
    assert all(item.template_id in rules.TEMPLATES for item in docket)
    assert all(item.preview_text for item in docket)
    assert {item.geometry_type for item in docket} <= {"POINT", "LINE", "POLYGON"}


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
        item_id="T01-01-night_market",
        template_id="night_market",
        title=rules.TEMPLATES["night_market"].title,
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
    assert item.status == "active"
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
    base_item = rules.DocketItem("factory-base", "factory", rules.TEMPLATES["factory"].title, "POLYGON", 1)
    mitigated_item = rules.DocketItem("factory-mitigated", "factory", rules.TEMPLATES["factory"].title, "POLYGON", 1)

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
    item = rules.DocketItem("deny-me", "clinic", rules.TEMPLATES["clinic"].title, "POINT", 1)

    result = rules.resolve_decision(state, item, profiles, "deny", ["D0000"], seed=2026)

    assert result.ok is True
    assert item.status == "denied"
    assert state.ap == 2
    assert state.unrest == 21
    assert state.prosperity == 49
    assert "Denied" in result.report


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

