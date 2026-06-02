"""Pure desk-model tests for compact Permit Office impact buckets."""

from __future__ import annotations

from toolbox import arcpy_permit_office_rules as rules
from toolbox.permit_office_arcgis.desk_view import (
    HEADLINE_METRICS,
    ReceiptModel,
    _Stacker,
    _hazard_summary,
    _maintenance_summary,
    _service_gap_summary,
    build_desk_model,
)


def _vendor_case():
    """Return a vendor docket item with a local target district."""

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
    """Verify uninspected cases show qualitative impact buckets."""

    item, districts = _vendor_case()

    model = build_desk_model(
        rules.CityState(ap=3, money=60),
        districts,
        [item],
        item.item_id,
        proposal_visible_by_item={item.item_id: True},
        deadline_text="MON INTAKE 1:00",
        deadline_meter=0,
        deadline_running=True,
    )
    buckets = {bucket.label: bucket for bucket in model.case.impact_buckets}

    assert list(buckets) == ["Cost", "City", "Local", "People", "Services", "Aftermath"]
    assert model.exhibit_visible is True
    assert model.deadline_text == "MON INTAKE 1:00"
    assert model.deadline_running is True
    assert "Issue 1AP/$12" in buckets["Cost"].value
    assert "conditions +$6" in buckets["Cost"].value
    assert "activity" in buckets["City"].value
    assert "district(s)" in buckets["Local"].value
    assert "fit" in buckets["Local"].value
    assert "grievance" in buckets["Local"].value
    assert "vendors" in buckets["People"].value
    assert "homeowners" in buckets["People"].value
    assert "gap" in buckets["Services"].value
    assert "rev $4/week" in buckets["Aftermath"].value
    assert "upkeep $1/week" in buckets["Aftermath"].value
    assert "inspect for unlicensed spillover" in buckets["Aftermath"].value
    assert "evidence" not in buckets["Aftermath"].value


def test_inspected_case_buckets_surface_evidence_and_population_context():
    """Verify inspected cases surface evidence and population context."""

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

    assert "high risk; 2/2 flagged evidence; 1 violation(s)" in buckets["Aftermath"].value
    assert buckets["Aftermath"].tone == "bad"
    assert "homeowners aggrieved" in buckets["People"].value


def test_ledger_rows_surface_non_money_city_health():
    """Verify desk ledger rows expose non-money city systems."""

    item, districts = _vendor_case()
    profile = districts["D0000"]
    profile.service_gap["child_services"] = 21
    profile.hazards = {"noise": 2}
    profile.affordability = 28

    model = build_desk_model(
        rules.CityState(last_revenue=4, last_upkeep=7, last_net=-3, maintenance_backlog=2),
        districts,
        [item],
        item.item_id,
    )
    ledger = {row.label: row for row in model.ledger_rows}

    assert ledger["Audit"].value == "FAIL"
    assert ledger["Economy"].value == "rev $4; up $7; net -3"
    assert "grievance" in ledger["Pressure"].value
    assert "worst mobility" in ledger["Services"].value
    assert ledger["Hazards"].value == "noise band 2 x1"
    assert ledger["Housing"].value == "D0000 affordability 28"
    assert ledger["Maintenance"].value == "2 active"


def test_headline_metrics_hide_generic_city_builder_stats():
    """Verify headline banner focuses on desk triage signals."""

    labels = [label for label, _display in HEADLINE_METRICS]

    assert labels == ["Week", "AP", "Money", "Heat", "Audit", "Pressure"]
    assert "Prosperity" not in labels
    assert "Unrest" not in labels
    assert "Culture" not in labels
    assert "Risk" not in labels


def test_ledger_derives_maintenance_from_active_features_when_available():
    """Verify feature rows override the compatibility backlog count."""

    item, districts = _vendor_case()
    feature = rules.FeatureInstance("F-market", "vendor_market", status="degraded", condition=22)

    model = build_desk_model(
        rules.CityState(maintenance_backlog=4),
        districts,
        [item],
        item.item_id,
        active_features=[feature],
    )
    ledger = {row.label: row for row in model.ledger_rows}

    assert ledger["Maintenance"].value == "1 due; lowest condition 22"


def test_build_desk_model_threads_receipt_into_view_model():
    """Verify the inline filed-report receipt is carried into the view model."""

    item, districts = _vendor_case()
    receipt = ReceiptModel(
        title="Street Vendor",
        report="approved",
        affected=("D0000",),
        metrics=(("$", "12"),),
    )

    model = build_desk_model(rules.CityState(), districts, [item], item.item_id, receipt=receipt)

    assert model.receipt is receipt


def test_build_desk_model_defaults_receipt_to_none():
    """Verify the receipt defaults to None until a decision is filed."""

    item, districts = _vendor_case()

    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)

    assert model.receipt is None


class _FakeCanvas:
    """Headless canvas stand-in: records draw calls, never measures real text."""

    def __init__(self):
        """Start an empty record of created canvas items."""

        self.created = []

    def _record(self, kind, args):
        """Record one create_* call and return a synthetic item id."""

        self.created.append((kind, args))
        return len(self.created)

    def create_rectangle(self, *args, **kwargs):
        """Record a rectangle and return its synthetic id."""

        return self._record("rect", args)

    def create_text(self, *args, **kwargs):
        """Record a text item and return its synthetic id."""

        return self._record("text", args)

    def create_line(self, *args, **kwargs):
        """Record a line and return its synthetic id."""

        return self._record("line", args)

    def bbox(self, _item):
        """Report no measurable box, exercising the conservative fallback."""

        return None


def test_stacker_blocks_never_overlap_or_exceed_bottom():
    """Verify stacked blocks advance past each other and never cross the hard bottom."""

    canvas = _FakeCanvas()
    stack = _Stacker(canvas, 0, 100, top=0, bottom=200, pad=10)
    tops = []
    bottoms = []

    def block(height):
        """Return a draw_fn that records its top and returns a clamped bottom."""

        def draw(_canvas, _x0, _x1, y, max_y):
            tops.append(y)
            return min(y + height, max_y)

        return draw

    for height in (30, 40, 500):  # the last block intentionally overflows
        bottom = stack.add(block(height))
        assert bottom is not None
        assert bottom <= stack.bottom
        bottoms.append(bottom)

    assert tops == sorted(tops)
    for idx in range(1, len(tops)):
        assert tops[idx] >= bottoms[idx - 1]  # next block starts at/after prior bottom

    # No room left, so a further block is skipped instead of overlapping.
    assert stack.add(block(20)) is None


def test_summary_helpers_report_service_hazard_and_maintenance_backlog():
    """Verify compact summary helpers report services, hazards, and upkeep."""

    _item, districts = _vendor_case()
    profile = districts["D0000"]
    profile.service_gap["child_services"] = 21
    profile.hazards = {"fire": 3, "noise": 1}
    feature = rules.FeatureInstance("F-market", "vendor_market", status="degraded", condition=22)

    assert _service_gap_summary([profile], "child_services") == "mobility gap 40 in D0000"
    assert _hazard_summary([profile]) == "fire band 3 x1"
    assert _maintenance_summary([feature]) == "1 due; lowest condition 22"
