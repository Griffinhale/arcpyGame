"""Tests for hydrated redraw planning."""

from __future__ import annotations

from toolbox import arcpy_permit_office_rules as rules
from toolbox.permit_office import cache_keys, dirty, futures
from toolbox.permit_office_arcgis import redraw_plan


def test_hydrated_redraw_plan_uses_actual_result_with_cache_hints():
    generation = cache_keys.GenerationToken("game-1", 1, 0, 1)
    delta = futures.DecisionDelta(
        "parent",
        "result",
        district_deltas={"D0000": {"activity": 2}},
        affected_cell_ids=("D0000",),
    )
    hint = futures.DecisionFutureNode(
        "parent",
        "approve",
        "CASE-1",
        "result",
        generation,
        delta=delta,
        affected_district_bits=1,
        dirty_layer_bits=dirty.DISTRICTS | dirty.POINTS,
        target_cell_ids=("D0000",),
        redraw_plan={"feature_layer_key": "points"},
    )
    actual = rules.DecisionResult(
        True,
        "approve",
        "CASE-1",
        "approved",
        affected_cell_ids=["D0001"],
        district_deltas={"D0001": {"trust": 1}},
        feature_updates={"F-1": {"status": "active"}},
    )

    plan = redraw_plan.hydrate_decision_redraw_plan(actual, hint)

    assert plan.feature_layer_key == "points"
    assert plan.feature_ids == ("F-1",)
    assert plan.affected_cell_ids == ("D0001",)
    assert plan.affected_district_bits == 0
    assert plan.dirty_layer_bits & dirty.DISTRICTS
    assert plan.dirty_layer_bits & dirty.POINTS
    assert plan.refresh_names == frozenset({"PermitPoints"})
    assert plan.remove_readd_names == frozenset({"PermitDistricts", "PermitPoints"})


def test_hydrated_redraw_plan_routes_line_and_zone_feature_layers():
    line = redraw_plan.hydrate_decision_redraw_plan(
        rules.DecisionResult(True, "approve", "L", "ok", affected_cell_ids=["D0000"]),
        feature_layer_key="lines",
    )
    zone = redraw_plan.hydrate_decision_redraw_plan(
        rules.DecisionResult(True, "approve", "Z", "ok", affected_cell_ids=["D0000"]),
        feature_layer_key="zones",
    )

    assert line.refresh_names == frozenset({"PermitLines"})
    assert zone.refresh_names == frozenset({"PermitZones"})
    assert line.remove_readd_names == frozenset({"PermitDistricts", "PermitLines"})
    assert zone.remove_readd_names == frozenset({"PermitDistricts", "PermitZones"})
