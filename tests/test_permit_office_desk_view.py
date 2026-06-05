"""Pure desk-model tests for compact Permit Office impact buckets."""

from __future__ import annotations

from toolbox import arcpy_permit_office_rules as rules
from toolbox.permit_office_arcgis.desk_view import (
    HEADLINE_METRICS,
    Palette,
    PermitDeskView,
    ReceiptModel,
    ReportTab,
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

    assert list(buckets) == ["Cost", "City", "Local", "People", "Services", "Budget"]
    assert model.exhibit_visible is True
    assert model.deadline_text == "MON INTAKE 1:00"
    assert model.deadline_running is True
    assert "Issue 1AP/$12" in buckets["Cost"].value
    assert "conditions +$6" in buckets["Cost"].value
    assert "deny 0AP" in buckets["Cost"].value
    assert "activity" in buckets["City"].value
    assert "district(s)" in buckets["Local"].value
    assert "fit" in buckets["Local"].value
    assert "grievance" in buckets["Local"].value
    assert "vendors" in buckets["People"].value
    assert "homeowners" in buckets["People"].value
    assert "gap" in buckets["Services"].value
    assert "rev $4/week" in buckets["Budget"].value
    assert "upkeep $1/week" in buckets["Budget"].value
    assert "inspect for unlicensed spillover" in buckets["Budget"].value
    assert "evidence" not in buckets["Budget"].value


def test_empty_target_copy_uses_retarget_map_language():
    """Verify fallback targeting copy matches the current button label."""

    item = rules.DocketItem("T01-vendor", "street_vendor_compact", rules.TEMPLATES["street_vendor_compact"].title, "POINT", 1)

    model = build_desk_model(rules.CityState(), {}, [item], item.item_id)

    assert "Retarget Map" in model.case.districts
    assert "Retarget Map" in model.status_text


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

    assert "high risk; 2/2 flagged evidence; 1 violation(s)" in buckets["Budget"].value
    assert "rev $4/week" in buckets["Budget"].value
    assert "upkeep $1/week" in buckets["Budget"].value
    assert "net +$3" in buckets["Budget"].value
    assert buckets["Budget"].tone == "bad"
    assert "homeowners aggrieved" in buckets["People"].value


def test_heat_ticker_explains_future_followup_pressure():
    """Verify stakeholder heat is framed as future docket pressure."""

    item, districts = _vendor_case()
    state = rules.CityState()
    state.stakeholder_heat["vendors"] = 3

    model = build_desk_model(state, districts, [item], item.item_id)

    heat_line = model.ticker_items[0]
    assert heat_line.startswith("Heat desk: vendors 3")
    for phrase in ("incident", "enforcement", "follow-up filing"):
        assert phrase in heat_line


def test_ticker_surfaces_contested_buyout_for_legibility():
    """Verify a contested district shows up on the city news ticker."""

    item, districts = _vendor_case()
    target = districts["D0000"]
    target.name = "Cinder Yard"
    target.identity_state = "contested"
    target.contesting_type = "mercantile"

    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)

    assert any("Boundary desk:" in line and "Cinder Yard" in line for line in model.ticker_items)


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


def test_ledger_rows_use_renamed_city_health_vitals():
    """Verify the desk model surfaces renamed city-health vitals."""

    item, districts = _vendor_case()

    model = build_desk_model(
        rules.CityState(activity=63, friction=28, trust=47, exposure=19),
        districts,
        [item],
        item.item_id,
    )
    ledger = {row.label: row for row in model.ledger_rows}

    assert ledger["Activity"].value == "63"
    assert ledger["Friction"].value == "28"
    assert ledger["Trust"].value == "47"
    assert ledger["Exposure"].value == "19"
    for legacy in ("Prosperity", "Unrest", "Culture", "Risk"):
        assert legacy not in ledger


def test_player_facing_vitals_are_exactly_the_four_audit_goals():
    """Lock the 5A model (ADR-10): the rail vitals are the four the audit scores.

    Player-facing goals = Activity/Friction/Trust/Exposure, mirroring state and the
    audit report; the granular support systems are detail, not part of this set.
    """

    item, districts = _vendor_case()
    state = rules.CityState(activity=63, friction=28, trust=47, exposure=19)

    model = build_desk_model(state, districts, [item], item.item_id)
    ledger = {row.label: row for row in model.ledger_rows}

    assert ledger["Activity"].value == "63"
    assert ledger["Friction"].value == "28"
    assert ledger["Trust"].value == "47"
    assert ledger["Exposure"].value == "19"

    # The audit scores and reports those same four vitals by the same names.
    _grade, report = rules.scorecard(state, districts, None, [item])
    for vital in ("activity", "friction", "trust", "exposure"):
        assert vital in report

    # Heat is a distinct stakeholder-pressure signal, not one of the four vitals.
    assert "Heat" in ledger
    assert ledger["Heat"].label not in ("Activity", "Friction", "Trust", "Exposure")


def test_headline_metrics_hide_generic_city_builder_stats():
    """Verify headline banner focuses on desk triage signals."""

    labels = [label for label, _display in HEADLINE_METRICS]

    assert labels == ["Week", "AP", "Money", "Heat", "Audit", "Pressure"]
    assert "Activity" not in labels
    assert "Friction" not in labels
    assert "Trust" not in labels
    assert "Exposure" not in labels


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
    assert model.report_tabs[0].title == "Street Vendor"
    assert model.selected_report_id == "latest"


def test_build_desk_model_defaults_receipt_to_none():
    """Verify the receipt defaults to None until a decision is filed."""

    item, districts = _vendor_case()

    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)

    assert model.receipt is None
    assert model.report_tabs == ()


def test_build_desk_model_selects_report_tabs_and_builds_ticker():
    """Verify report tabs and ticker text are deterministic view-model inputs."""

    item, districts = _vendor_case()
    districts["D0000"].display_state = "grievance"
    tabs = (
        ReportTab("r1", "Inspection", "report", "inspected", False, "Inspected file."),
        ReportTab("r2", "Scorecard", "scorecard", "scorecard", False, "Audit PASS."),
    )

    first = build_desk_model(rules.CityState(ap=1), districts, [item], item.item_id, report_tabs=tabs, selected_report_id="r1")
    second = build_desk_model(rules.CityState(ap=1), districts, [item], item.item_id, report_tabs=tabs, selected_report_id="r1")

    assert first.selected_report_id == "r1"
    assert first.selected_desk_tab == "applications"
    assert [tab.selected for tab in first.report_tabs] == [True, False]
    assert first.ticker_items == second.ticker_items
    assert any("Street wire" in text for text in first.ticker_items)


def test_build_desk_model_can_select_reports_primary_tab():
    """Verify the combined lower tabbox can switch to filed reports."""

    item, districts = _vendor_case()
    tabs = (ReportTab("r1", "Inspection", "report", "inspected", True, "Inspected file."),)

    model = build_desk_model(rules.CityState(), districts, [item], item.item_id, report_tabs=tabs, selected_desk_tab="reports")

    assert model.selected_desk_tab == "reports"
    assert model.selected_report_id == "r1"


def test_build_desk_model_adds_decision_lanes_for_selected_case():
    """Verify selected applications expose consequence lanes for triage."""

    item, districts = _vendor_case()

    model = build_desk_model(rules.CityState(ap=2, money=60), districts, [item], item.item_id)

    lanes = {lane.action_id: lane for lane in model.action_lanes}
    assert list(lanes) == ["approve", "approve_mitigated", "deny"]
    assert lanes["approve"].label == "Issue Permit"
    assert "1 AP" in lanes["approve"].cost
    assert "$12" in lanes["approve"].cost
    assert "activity" in lanes["approve"].city_effect
    assert lanes["approve_mitigated"].label == "Add Conditions"
    assert "conditions" in lanes["approve_mitigated"].cost.lower()
    assert lanes["deny"].label == "Deny"
    assert "0 AP" in lanes["deny"].cost


def test_incident_decision_lanes_disable_ap_gated_actions_when_ap_empty():
    """Verify AP-gated incident actions are visibly unavailable at 0 AP."""

    item = rules.DocketItem("incident", rules.CIVIC_INCIDENT_TEMPLATE_ID, "Civic Incident", "POINT", 1, target_cell_ids=["D0000"])
    profile = rules.DistrictProfile("D0000", "D0000", 1000, 50, 20, 35, 25, 50, "mercantile")
    districts = {profile.cell_id: rules.normalize_profile(profile)}

    model = build_desk_model(rules.CityState(ap=0, money=60), districts, [item], item.item_id)

    lanes = {lane.action_id: lane for lane in model.action_lanes}
    assert lanes["approve"].enabled is False
    assert lanes["approve_mitigated"].enabled is False
    assert lanes["deny"].enabled is False
    assert lanes["deny"].cost.startswith("1 AP")
    assert lanes["deny"].disabled_reason == "Needs 1 AP"


def test_permit_deny_stays_enabled_when_ap_empty():
    """Verify ordinary permit denial remains available with 0 AP."""

    item, districts = _vendor_case()

    model = build_desk_model(rules.CityState(ap=0, money=60), districts, [item], item.item_id)

    lanes = {lane.action_id: lane for lane in model.action_lanes}
    assert lanes["approve"].enabled is False
    assert lanes["deny"].enabled is True
    assert lanes["deny"].cost.startswith("0 AP")


def test_maintenance_case_uses_repair_action_family():
    """Verify maintenance follow-ups read as Fund Repair / Patch / Defer (#2)."""

    item = rules.DocketItem(
        "maint",
        rules.MAINTENANCE_TEMPLATE_ID,
        "Feature Maintenance Order",
        "POINT",
        1,
        target_cell_ids=["D0000"],
    )
    profile = rules.DistrictProfile("D0000", "Market Row", 1000, 50, 20, 35, 25, 50, "mercantile")
    districts = {profile.cell_id: rules.normalize_profile(profile)}

    model = build_desk_model(rules.CityState(ap=3, money=60), districts, [item], item.item_id)
    lanes = {lane.action_id: lane for lane in model.action_lanes}

    assert lanes["approve"].label == "Fund Repair"
    assert lanes["approve_mitigated"].label == "Patch"
    assert lanes["deny"].label == "Defer"
    assert "maintenance" in lanes["deny"].city_effect


def test_build_desk_model_marks_queue_cleared_when_no_active_items():
    """Verify empty active dockets expose the queue-cleared state."""

    model = build_desk_model(
        rules.CityState(),
        {},
        [rules.DocketItem("done", "street_vendor_compact", "Done", "POINT", 1, status="approved")],
    )

    assert model.queue_cleared is True
    assert model.action_lanes == ()


class _FakeCanvas:
    """Headless canvas stand-in: records draw calls, never measures real text."""

    def __init__(self):
        """Start an empty record of created canvas items."""

        self.created = []

    def _record(self, kind, args, kwargs=None):
        """Record one create_* call and return a synthetic item id."""

        self.created.append((kind, args, kwargs or {}))
        return len(self.created)

    def create_rectangle(self, *args, **kwargs):
        """Record a rectangle and return its synthetic id."""

        return self._record("rect", args, kwargs)

    def create_text(self, *args, **kwargs):
        """Record a text item and return its synthetic id."""

        return self._record("text", args, kwargs)

    def create_line(self, *args, **kwargs):
        """Record a line and return its synthetic id."""

        return self._record("line", args, kwargs)

    def delete(self, *_args):
        """Record canvas clearing for full-draw tests."""

        self.created.clear()

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


class _Callbacks:
    """Callable bundle for headless desk view tests."""

    def __init__(self):
        """Record invoked callbacks by name."""

        self.calls = []

    def __getattr__(self, name):
        """Return a recorder function for any callback field."""

        def _callback(*args):
            self.calls.append((name, args))

        return _callback


def _view_for_drawing(model):
    """Return a PermitDeskView shell without creating a Tk widget."""

    callbacks = _Callbacks()
    view = object.__new__(PermitDeskView)
    view.callbacks = callbacks
    view.on_select_item = lambda item_id: callbacks.calls.append(("select_item", (item_id,)))
    view.model = model
    view._click_targets = []
    view._hover_key = ""
    view._font_cache = {}
    view._fit_cache = {}
    view._lookup_model = None
    view._ledger_by_label = {}
    view._lane_by_action = {}
    view._menu_open = False
    view.root = None
    view._font = lambda size, weight="normal": ("Segoe UI", size, weight)
    view._px_measurer = lambda _size, _weight: None
    return view, callbacks


def _text_values(canvas):
    """Return all text values written to the fake canvas."""

    return [kwargs.get("text") for kind, _args, kwargs in canvas.created if kind == "text"]


def test_application_workspace_stacks_queued_cases_under_active_case():
    """Verify the active case expands while queued cases collapse vertically beneath it."""

    item, districts = _vendor_case()
    rows = [
        item,
        rules.DocketItem("T02", "street_vendor_compact", "Business License Fee Sweep", "POINT", 1),
        rules.DocketItem("T03", "street_vendor_compact", "Public Art and Museum Grant", "POINT", 1),
        rules.DocketItem("T04", "street_vendor_compact", "Street Vendor Compact", "POINT", 1),
    ]
    model = build_desk_model(rules.CityState(), districts, rows, "T03")
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_application_tab_content(canvas, (0, 0, 760, 700))

    # The active case (T03) is the expanded brief, not a collapsed queued row.
    target_ids = [ident for kind, ident, _bbox, _callback in view._click_targets if kind == "docket"]
    assert target_ids == ["T01-vendor", "T02", "T04"]
    assert "QUEUED (3)" in _text_values(canvas)
    assert not any(text.startswith("+") and "queued" in text for text in _text_values(canvas))


def test_application_workspace_caps_queued_stack_and_reports_overflow():
    """Verify a short workspace caps the collapsed queue and flags overflow."""

    item, districts = _vendor_case()
    rows = [item] + [
        rules.DocketItem(f"T{n:02d}", "street_vendor_compact", f"Case {n}", "POINT", 1)
        for n in range(2, 12)
    ]
    model = build_desk_model(rules.CityState(), districts, rows, item.item_id)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    # A short box forces the collapsed stack to cap below the 10 queued cases.
    view._draw_application_tab_content(canvas, (0, 0, 760, 460))

    target_ids = [ident for kind, ident, _bbox, _callback in view._click_targets if kind == "docket"]
    assert 0 < len(target_ids) < 10
    assert any(text.startswith("+") and "queued" in text for text in _text_values(canvas))


def test_fit_px_memoizes_so_repeated_draws_skip_recompute():
    """Verify _fit_px caches per (text, size, weight, max_px) across redraws.

    The hover/redraw path re-fits every label string each frame; _fit_px is a pure
    function of its args (font metrics are fixed at runtime), so repeated calls
    must reuse the cached result instead of re-running the fit each time.
    """

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view, _callbacks = _view_for_drawing(model)

    calls = []
    real_compute = view._fit_px_compute
    view._fit_px_compute = lambda *args: (calls.append(args), real_compute(*args))[1]

    first = view._fit_px("A district label that may need clipping", 9, "bold", 70)
    second = view._fit_px("A district label that may need clipping", 9, "bold", 70)

    assert first == second
    assert len(calls) == 1  # second call served from the memo
    assert ("A district label that may need clipping", 9, "bold", 70) in view._fit_cache


def test_draw_lookups_rebuild_only_on_model_swap():
    """Verify ledger/lane lookup dicts are cached and rebuilt only when the model changes.

    The banner and ledger rail both index ledger rows by label, and case controls
    index action lanes by action_id, every redraw. Those maps are a pure function
    of the current model, so they are built once per model swap and reused across
    hover/deadline redraws instead of rebuilt each frame.
    """

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view, _callbacks = _view_for_drawing(model)

    view._ensure_lookups()
    first_ledger = view._ledger_by_label
    first_lanes = view._lane_by_action
    assert first_ledger["Audit"].label == "Audit"
    assert {lane.action_id for lane in model.action_lanes} == set(first_lanes)

    view._ensure_lookups()
    # Same model object -> the cached dicts are reused, not rebuilt.
    assert view._ledger_by_label is first_ledger
    assert view._lane_by_action is first_lanes

    # A new model object invalidates the cache and rebuilds the maps.
    model2 = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view.model = model2
    view._ensure_lookups()
    assert view._ledger_by_label is not first_ledger


def test_build_desk_model_game_active_defaults_true_and_can_be_false():
    """Verify the model carries a game_active flag (True by default)."""

    assert build_desk_model(rules.CityState(), {}, []).game_active is True
    assert build_desk_model(rules.CityState(), {}, [], game_active=False).game_active is False


def test_empty_docket_before_a_game_shows_start_prompt_not_queue_cleared():
    """Verify a not-started session prompts New Game, not 'all applications filed'."""

    model = build_desk_model(rules.CityState(), {}, [], game_active=False)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_application_tab_content(canvas, (0, 0, 760, 700))
    texts = _text_values(canvas)

    assert any("No game" in (text or "") for text in texts)
    assert any("New Game" in (text or "") for text in texts)
    assert not any("have been filed" in (text or "") for text in texts)
    assert not any((text or "") == "End Week" for text in texts)


def test_empty_docket_mid_game_still_shows_queue_cleared():
    """Verify an active game with an empty docket keeps the queue-cleared panel."""

    model = build_desk_model(rules.CityState(), {}, [], game_active=True)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_application_tab_content(canvas, (0, 0, 760, 700))
    texts = _text_values(canvas)

    assert any("Queue cleared" in (text or "") for text in texts)
    assert any("have been filed" in (text or "") for text in texts)


def test_utility_menu_button_is_compact_hamburger_without_text_label():
    """Verify utility actions are collapsed behind a small menu affordance."""

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_menu_button(canvas, 100, 10, 136, 34)

    assert "MENU" not in _text_values(canvas)
    assert any(kind == "line" for kind, _args, _kwargs in canvas.created)
    assert [target[:2] for target in view._click_targets] == [("session", "Menu")]


def test_session_menu_anchors_to_hamburger_button():
    """Verify the utility menu opens under the hamburger, not at window edge."""

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_menu_button(canvas, 720, 20, 760, 48)
    view._draw_session_menu(canvas, 1300)

    menu_rects = [
        args
        for kind, args, kwargs in canvas.created
        if kind == "rect" and kwargs.get("fill") == Palette.PAPER and len(args) == 4 and args[3] - args[1] > 100
    ]
    assert menu_rects
    x0, y0, _x1, _y1 = menu_rects[-1]
    assert x0 == 584
    assert y0 == 48


def test_full_draw_has_no_global_case_action_bar_targets():
    """Verify case actions are not registered in the old global toolbar zone."""

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()
    view.canvas = canvas

    view._draw(1120, 900)

    early_actions = [
        ident
        for kind, ident, bbox, _callback in view._click_targets
        if kind == "action" and bbox[1] < 230
    ]
    assert early_actions == []


def test_selected_application_draws_decision_brief_lanes():
    """Verify the active application renders modern decision-lane content."""

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_active_card(canvas, (0, 0, 760, 620))

    texts = _text_values(canvas)
    assert "DECISION BRIEF" in texts
    assert "Issue Permit" in texts
    assert "Add Conditions" in texts
    assert "Deny" in texts


def test_selected_application_uses_explicit_proposed_feature_copy():
    """Verify exhibit controls name the proposed feature, not a generic exhibit."""

    item, districts = _vendor_case()
    hidden = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    visible = build_desk_model(
        rules.CityState(),
        districts,
        [item],
        item.item_id,
        proposal_visible_by_item={item.item_id: True},
    )

    for model, expected in ((hidden, "Show Proposed Feature"), (visible, "Hide Proposed Feature")):
        view, _callbacks = _view_for_drawing(model)
        canvas = _FakeCanvas()

        view._draw_active_card(canvas, (0, 0, 760, 620))

        assert expected in _text_values(canvas)


def test_decision_brief_uses_vertical_lane_rows_for_breathing_room():
    """Verify action consequences use stacked rows instead of cramped columns."""

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_active_card(canvas, (0, 0, 760, 620))

    lane_rects = [
        args
        for kind, args, kwargs in canvas.created
        if kind == "rect" and kwargs.get("fill") == Palette.PAPER_ALT and len(args) == 4 and args[3] - args[1] >= 58
    ]
    assert len(lane_rects) >= 3
    assert lane_rects[1][1] > lane_rects[0][1]
    assert lane_rects[2][1] > lane_rects[1][1]


def test_city_health_rail_draws_only_slim_pulse_signals():
    """Verify City Health defaults to pulse signals, not the full ledger."""

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_ledger_rail(canvas, (0, 0, 260, 620))

    texts = _text_values(canvas)
    assert "CITY PULSE" in texts
    assert "ACTIVITY" in texts
    assert "TRUST" in texts
    assert "EXPOSURE" in texts
    assert "PRESSURE" in texts
    assert "SERVICES" not in texts
    assert "HOUSING" not in texts
    assert "MAINTENANCE" not in texts


def test_build_desk_model_does_not_mutate_districts_argument():
    """Verify scoring the Audit row leaves the caller's district profiles intact.

    `_ledger_rows` scores the live audit for the Audit row. It must not mutate the
    districts passed in — we rely on `normalize_profile` being idempotent instead
    of a defensive `deepcopy`, so a normalized profile must round-trip unchanged.
    """

    import copy

    item, districts = _vendor_case()
    before = copy.deepcopy(districts)

    model = build_desk_model(
        rules.CityState(activity=70, trust=55, friction=15, exposure=20),
        districts,
        [item],
        item.item_id,
    )

    assert districts == before
    assert "Audit" in {row.label for row in model.ledger_rows}


def test_city_health_index_folds_core_metrics():
    """Verify the City Health headline summarizes the four core metrics."""

    from toolbox.permit_office_arcgis.desk_model import _city_health_index

    # Activity/Trust positive, Friction/Exposure negative: (80 + 60 + (100-10) + (100-20)) / 4 = 77.5 -> 78
    healthy = rules.CityState(activity=80, trust=60, friction=10, exposure=20)
    assert _city_health_index(healthy) == 78
    # A struggling city reads lower.
    failing = rules.CityState(activity=20, trust=15, friction=70, exposure=65)
    assert _city_health_index(failing) < _city_health_index(healthy)
    assert 0 <= _city_health_index(failing) <= 100


def test_ledger_surfaces_city_health_headline_and_heat():
    """Verify the ledger leads with a Health row and keeps Heat visible."""

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(activity=70, trust=55, friction=15, exposure=20), districts, [item], item.item_id)
    ledger = {row.label: row for row in model.ledger_rows}

    assert "Health" in ledger
    assert ledger["Health"].meter is not None
    assert "Heat" in ledger


def test_city_health_rail_draws_health_and_heat_headline():
    """Verify the pulse rail renders the City Health gauge and Heat indicator."""

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_ledger_rail(canvas, (0, 0, 260, 620))

    texts = _text_values(canvas)
    assert "CITY HEALTH" in texts
    assert "HEAT" in texts


def test_selected_case_renders_economy_and_action_note():
    """Verify the decision brief carries a recurring budget line and action note."""

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(), districts, [item], item.item_id)

    assert model.case.economy
    assert "Issue=" in model.case.action_note


def test_queue_cleared_state_draws_end_week_and_cancel_autoclose():
    """Verify the application workspace exposes the queue-cleared controls."""

    model = build_desk_model(rules.CityState(), {}, [], auto_close_active=True, auto_close_seconds=3)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_application_tab_content(canvas, (0, 0, 760, 620))

    texts = _text_values(canvas)
    assert "Queue cleared" in texts
    assert "End Week" in texts
    assert "Cancel Auto Close" in texts
    targets = [(kind, ident) for kind, ident, _bbox, _callback in view._click_targets]
    assert ("case-action", "End Week") in targets
    assert ("case-action", "Cancel Auto Close") in targets


def test_session_menu_offers_manual_end_week_when_out_of_ap():
    """Verify the utility menu always exposes a manual End Week control.

    When the player is out of AP with cases still queued (especially incidents,
    whose Deny lane also costs AP), no in-card lane is affordable and the
    queue-cleared End Week button never appears. The session menu must offer a
    manual way to close the week regardless of AP.
    """

    item, districts = _vendor_case()
    model = build_desk_model(rules.CityState(ap=0, money=0), districts, [item], item.item_id)
    view, callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_menu_button(canvas, 720, 20, 760, 48)
    view._draw_session_menu(canvas, 1300)

    assert "END WEEK" in _text_values(canvas)
    end_week = [cb for kind, ident, _bbox, cb in view._click_targets if (kind, ident) == ("session", "End Week")]
    assert end_week
    end_week[0]()
    assert ("advance_turn", ()) in callbacks.calls


def test_start_help_overlay_explains_score_exhibits_and_resume():
    """Verify the help overlay covers score optimization, exhibits, and resume behavior."""

    model = build_desk_model(rules.CityState(), {}, [], show_start_help=True)
    view, _callbacks = _view_for_drawing(model)
    canvas = _FakeCanvas()

    view._draw_start_help_overlay(canvas, 1120, 860)

    body = " ".join(str(text) for text in _text_values(canvas))
    for phrase in ("Activity", "Trust", "Services", "money", "Friction", "Exposure"):
        assert phrase in body
    for phrase in ("Show Proposed Feature", "selected application's map exhibit", "Retarget Map"):
        assert phrase in body
    for phrase in ("End Game", "geodatabase", "resume"):
        assert phrase in body


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
