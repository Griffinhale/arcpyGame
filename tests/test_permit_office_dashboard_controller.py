"""Controller tests for dashboard map-update and approval sequencing."""

from __future__ import annotations

from types import SimpleNamespace
import sys


sys.modules.setdefault(
    "arcpy",
    SimpleNamespace(
        AddMessage=lambda text: None,
        AddWarning=lambda text: None,
        AddError=lambda text: None,
    ),
)

from toolbox import arcpy_permit_office_rules as rules
from toolbox.permit_office_arcgis import dashboard


def _profile(cell_id):
    profile = rules.DistrictProfile(cell_id, cell_id, 1000, 50, 20, 35, 25, 50, "mercantile")
    return rules.normalize_profile(profile)


def test_update_from_map_replaces_selected_case_targets(monkeypatch):
    item = rules.DocketItem(
        "CASE-update",
        "connector_corridor",
        "Connector Corridor",
        "LINE",
        1,
    )
    controller = dashboard.DashboardController({}, "district_layer", 2026, object())
    controller.selected_item_id = item.item_id
    controller.status_text = ""
    controller.status_var = dashboard._StatusProxy(controller)
    controller.reload = lambda: None

    monkeypatch.setattr(dashboard, "read_docket", lambda paths: [item])
    monkeypatch.setattr(dashboard, "selected_cell_ids", lambda layer: ["D0000", "D0001"])
    monkeypatch.setattr(dashboard, "refresh_all", lambda paths, messages: None)

    def insert(paths, docket_item, target_ids, messages):
        docket_item.target_cell_ids = list(target_ids)
        return list(target_ids)

    monkeypatch.setattr(dashboard, "insert_or_replace_proposal", insert)

    controller.update_from_map()

    assert item.target_cell_ids == ["D0000", "D0001"]
    assert controller.status_text == "Updated Connector Corridor from map selection: D0000, D0001."


def test_approval_restores_missing_proposal_before_spillover(monkeypatch):
    item = rules.DocketItem(
        "CASE-approve",
        "connector_corridor",
        "Connector Corridor",
        "LINE",
        1,
        target_cell_ids=["D0000", "D0001"],
    )
    state = rules.CityState()
    districts = {"D0000": _profile("D0000"), "D0001": _profile("D0001"), "D0002": _profile("D0002")}
    controller = dashboard.DashboardController({}, "district_layer", 2026, object())
    controller.selected_item_id = item.item_id
    controller.status_text = ""
    controller.status_var = dashboard._StatusProxy(controller)
    controller.reload = lambda: None
    order = []

    monkeypatch.setattr(dashboard, "read_docket", lambda paths: [item])
    monkeypatch.setattr(dashboard, "selected_cell_ids", lambda layer: [])
    monkeypatch.setattr(dashboard, "command_insert", lambda paths, action, item_id, target_ids: "CMD-1")
    monkeypatch.setattr(dashboard, "command_finish", lambda *args, **kwargs: None)
    monkeypatch.setattr(dashboard, "read_state", lambda paths: state)
    monkeypatch.setattr(dashboard, "read_districts", lambda paths: districts)
    monkeypatch.setattr(dashboard, "read_active_features", lambda paths: [])
    monkeypatch.setattr(dashboard, "read_projects", lambda paths: {})
    monkeypatch.setattr(dashboard, "write_active_features", lambda paths, active_features: None)
    def activate(paths, docket_item, report):
        order.append("activate")
        return 1

    monkeypatch.setattr(dashboard, "activate_proposal", activate)
    monkeypatch.setattr(controller, "_finish_decision", lambda *args: order.append("finish"))

    def ensure(paths, docket_item, seed, messages, target_ids=None):
        order.append("ensure")
        assert target_ids == ["D0000", "D0001"]
        return list(target_ids)

    def spillover(paths, docket_item):
        assert order == ["ensure"]
        order.append("spillover")
        return ["D0002"]

    def resolve(state_arg, docket_item, district_arg, action, targets, spillovers, **kwargs):
        assert targets == ["D0000", "D0001"]
        assert spillovers == ["D0002"]
        docket_item.status = "active"
        return rules.DecisionResult(True, action, docket_item.item_id, "approved", affected_cell_ids=list(targets) + list(spillovers))

    monkeypatch.setattr(dashboard, "ensure_case_proposal", ensure)
    monkeypatch.setattr(dashboard, "proposal_spillover", spillover)
    monkeypatch.setattr(dashboard.rules, "resolve_decision", resolve)

    controller.apply_decision("approve", False)

    assert order == ["ensure", "spillover", "activate", "finish"]


def test_successful_decision_reapplies_map_presentation_before_refresh(monkeypatch):
    item = rules.DocketItem("CASE-finish", "procession_route", "Procession Route", "LINE", 1)
    state = rules.CityState()
    districts = {"D0000": _profile("D0000")}
    controller = dashboard.DashboardController({"districts": "districts"}, "district_layer", 2026, object())
    controller.status_text = ""
    controller.status_var = dashboard._StatusProxy(controller)
    order = []

    monkeypatch.setattr(dashboard, "write_district_updates", lambda *args, **kwargs: order.append("districts"))
    monkeypatch.setattr(dashboard, "write_state", lambda *args, **kwargs: order.append("state"))
    monkeypatch.setattr(dashboard, "write_projects", lambda *args, **kwargs: order.append("projects"))
    monkeypatch.setattr(dashboard, "write_docket_item", lambda *args, **kwargs: order.append("docket"))
    monkeypatch.setattr(dashboard, "action_log", lambda *args, **kwargs: order.append("log"))
    monkeypatch.setattr(dashboard, "command_finish", lambda *args, **kwargs: order.append("command"))
    monkeypatch.setattr(dashboard, "clear_output_selections", lambda *args, **kwargs: order.append("clear"))
    monkeypatch.setattr(dashboard, "add_outputs_to_map", lambda *args, **kwargs: order.append("map"))
    monkeypatch.setattr(dashboard, "refresh_all", lambda *args, **kwargs: order.append("refresh"))
    monkeypatch.setattr(dashboard, "open_effect_report", lambda *args, **kwargs: order.append("receipt"))

    result = rules.DecisionResult(True, "approve", item.item_id, "approved", affected_cell_ids=["D0000"])

    controller._finish_decision("CMD-1", item, state, districts, {}, result)

    assert order[-4:] == ["clear", "map", "refresh", "receipt"]
