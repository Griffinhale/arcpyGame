"""Tests for pure one-ply Permit Office future cache behavior."""

from __future__ import annotations

from toolbox.permit_office import cache_keys, dirty, futures
from toolbox import arcpy_permit_office_rules as rules


def _district(cell_id: str):
    profile = rules.DistrictProfile(cell_id, cell_id, 1000, 50, 20, 35, 25, 50, "mercantile")
    return rules.normalize_profile(profile)


def test_one_ply_cache_generates_legal_futures_with_redraw_hints():
    state = rules.CityState(ap=2, money=60)
    districts = {"D0000": _district("D0000"), "D0001": _district("D0001")}
    item = rules.DocketItem("CASE-1", "street_vendor_compact", "Street Vendor Compact", "POINT", 1, target_cell_ids=["D0000"])
    generation = cache_keys.GenerationToken("game-1", 1, 0, 1)
    cache = futures.DecisionFutureCache(generation)

    nodes = cache.build_one_ply(state, districts, [item], spillover_provider=lambda docket_item: ["D0001"])

    keys = {(node.item_id, node.action_key) for node in nodes if node.legal}
    approve = next(node for node in nodes if node.action_key == "approve")
    assert keys == {("CASE-1", "approve"), ("CASE-1", "approve_mitigated"), ("CASE-1", "deny")}
    assert approve.target_cell_ids == ("D0000",)
    assert approve.spillover_cell_ids == ("D0001",)
    assert approve.affected_district_bits
    assert approve.dirty_layer_bits & dirty.DISTRICTS
    assert approve.dirty_layer_bits & dirty.POINTS
    assert approve.delta.parent_hash == approve.parent_hash
    assert approve.delta.resulting_state_hash == approve.resulting_state_hash
    assert approve.delta.district_deltas
    assert approve.redraw_plan["feature_layer_key"] == "points"


def test_one_ply_cache_rejects_unaffordable_approval_but_keeps_deny_legal():
    state = rules.CityState(ap=0, money=0)
    districts = {"D0000": _district("D0000")}
    item = rules.DocketItem("CASE-1", "street_vendor_compact", "Street Vendor Compact", "POINT", 1, target_cell_ids=["D0000"])
    cache = futures.DecisionFutureCache(cache_keys.GenerationToken("game-1", 1, 0, 1))

    nodes = cache.build_one_ply(state, districts, [item])

    legal = {(node.item_id, node.action_key) for node in nodes if node.legal}
    assert legal == {("CASE-1", "deny")}
    assert any(node.action_key == "approve" and not node.legal for node in nodes)


def test_one_ply_cache_does_not_mutate_authoritative_objects():
    state = rules.CityState(ap=2, money=60)
    districts = {"D0000": _district("D0000")}
    item = rules.DocketItem("CASE-1", "street_vendor_compact", "Street Vendor Compact", "POINT", 1, target_cell_ids=["D0000"])
    cache = futures.DecisionFutureCache(cache_keys.GenerationToken("game-1", 1, 0, 1))

    cache.build_one_ply(state, districts, [item])

    assert state.ap == 2
    assert state.money == 60
    assert item.status == "open"
    assert districts["D0000"].activity == 50


def test_promoting_chosen_future_evicts_impossible_siblings():
    state = rules.CityState(ap=2, money=60)
    districts = {"D0000": _district("D0000")}
    item = rules.DocketItem("CASE-1", "street_vendor_compact", "Street Vendor Compact", "POINT", 1, target_cell_ids=["D0000"])
    cache = futures.DecisionFutureCache(cache_keys.GenerationToken("game-1", 1, 0, 1))
    nodes = cache.build_one_ply(state, districts, [item])
    chosen = next(node for node in nodes if node.action_key == "deny")

    cache.promote_chosen(chosen)

    assert cache.current_state_hash == chosen.resulting_state_hash
    assert cache.lookup(chosen.parent_hash, item.item_id, "approve") is None
    assert cache.lookup(chosen.parent_hash, item.item_id, "deny") is chosen


def test_one_ply_cache_handles_maintenance_features_without_hashing_instances():
    """Verify maintenance futures do not use FeatureInstance objects as dict keys."""

    feature = rules.FeatureInstance(
        "F-market",
        "vendor_market",
        owner_group="vendors",
        target_cell_ids=["D0000"],
        turn_created=1,
        condition=20,
        status="degraded",
    )
    rules.normalize_feature_instance(feature, turn=3)
    districts = {"D0000": _district("D0000")}
    item = rules.generate_docket(3, active_features=[feature], count=1)[0]
    state = rules.CityState(turn=3, ap=3, money=50)
    cache = futures.DecisionFutureCache(cache_keys.GenerationToken("game-1", 3, 0, 3))

    nodes = cache.build_one_ply(state, districts, [item], active_features=[feature])

    mitigated = next(node for node in nodes if node.action_key == "approve_mitigated")
    assert mitigated.legal is True
    assert mitigated.feature_updates["F-market"]["condition"] > 20


def test_one_ply_cache_skips_malformed_unhashable_target_values():
    """Verify speculative expansion cannot crash on malformed live target rows."""

    feature = rules.FeatureInstance(
        "F-market",
        "vendor_market",
        owner_group="vendors",
        target_cell_ids=["D0000"],
        turn_created=1,
        condition=20,
        status="degraded",
    )
    rules.normalize_feature_instance(feature, turn=3)
    districts = {"D0000": _district("D0000")}
    item = rules.generate_docket(3, active_features=[feature], count=1)[0]
    item.target_cell_ids = [feature, "D0000"]
    state = rules.CityState(turn=3, ap=3, money=50)
    cache = futures.DecisionFutureCache(cache_keys.GenerationToken("game-1", 3, 0, 3))

    nodes = cache.build_one_ply(state, districts, [item], active_features=[feature])

    approve = next(node for node in nodes if node.action_key == "approve")
    assert approve.legal is True
    assert approve.target_cell_ids == ("D0000",)
    assert approve.affected_district_bits


def test_one_ply_cache_skips_malformed_unhashable_spillover_values():
    """Verify speculative spillover sanitization cannot hash feature instances."""

    feature = rules.FeatureInstance(
        "F-market",
        "vendor_market",
        owner_group="vendors",
        target_cell_ids=["D0000"],
        turn_created=1,
        condition=20,
        status="degraded",
    )
    rules.normalize_feature_instance(feature, turn=3)
    districts = {"D0000": _district("D0000"), "D0001": _district("D0001")}
    item = rules.generate_docket(3, active_features=[feature], count=1)[0]
    item.target_cell_ids = ["D0000"]
    state = rules.CityState(turn=3, ap=3, money=50)
    cache = futures.DecisionFutureCache(cache_keys.GenerationToken("game-1", 3, 0, 3))

    nodes = cache.build_one_ply(
        state,
        districts,
        [item],
        active_features=[feature],
        spillover_provider=lambda _item: [feature, "D0001"],
    )

    approve = next(node for node in nodes if node.action_key == "approve")
    assert approve.legal is True
    assert approve.spillover_cell_ids == ("D0001",)
