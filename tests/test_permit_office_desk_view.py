"""Pure desk-model tests for compact Permit Office impact buckets."""

from __future__ import annotations

from toolbox import arcpy_permit_office_rules as rules
from toolbox.permit_office_arcgis.desk_view import build_desk_model


def _vendor_case():
    item = rules.DocketItem(
        "T01-vendor",
        "street_vendor_compact",
        rules.TEMPLATES["street_vendor_compact"].title,
        "POINT",
        1,
        target_cell_ids=["D0000"],
    )
    profile = rules.DistrictProfile(
        "D0000",
        "Market Row",
        1200,
        48,
        24,
        38,
        27,
        44,
        "mercantile",
        population_mix={"vendors": 3, "homeowners": 2, "students": 1},
        dissatisfaction={"homeowners": 3},
    )
    rules.normalize_profile(profile)
    return item, {profile.cell_id: profile}


def test_uninspected_case_uses_qualitative_impact_buckets():
    item, districts = _vendor_case()

    model = build_desk_model(
        rules.CityState(ap=3, money=60),
        districts,
        [item],
        item.item_id,
        proposal_visible_by_item={item.item_id: True},
    )
    buckets = {bucket.label: bucket for bucket in model.case.impact_buckets}

    assert list(buckets) == ["Cost", "City", "Target", "People", "Follow-up"]
    assert model.exhibit_visible is True
    assert "1 AP / $12" in buckets["Cost"].value
    assert "vendors" in buckets["People"].value
    assert "inspect for unlicensed spillover" == buckets["Follow-up"].value
    assert "evidence" not in buckets["Follow-up"].value


def test_inspected_case_buckets_surface_evidence_and_population_context():
    item, districts = _vendor_case()
    item.inspected = True
    item.risk_band = "high"
    item.case_json = {
        "inspection": {
            "risk_band": "high",
            "evidence": [{"severity": "warning"}, {"severity": "critical"}],
            "violations": [{"code": "public_nuisance"}],
        }
    }

    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    buckets = {bucket.label: bucket for bucket in model.case.impact_buckets}

    assert buckets["Follow-up"].value == "high risk; 2 evidence; 1 violation(s)"
    assert buckets["Follow-up"].tone == "bad"
    assert "vendors support" in buckets["People"].value
    assert "homeowners object" in buckets["People"].value
    assert "homeowners aggrieved" in buckets["People"].value
