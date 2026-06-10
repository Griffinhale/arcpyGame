"""Stable cache keys for pure Permit Office speculative data."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class CacheLifetime(Enum):
    """Cache invalidation granularity for generation tokens."""

    COMMAND = "command"
    DOCKET = "docket"
    TURN = "turn"
    GAME = "game"


@dataclass(frozen=True)
class GenerationToken:
    """Identifies the game, turn, command, and docket generation for a cache entry."""

    game_id: str
    turn: int
    command_index: int
    docket_generation: int

    def matches(self, other: "GenerationToken", lifetime: CacheLifetime = CacheLifetime.COMMAND) -> bool:
        """Return True when ``other`` is valid for this token at ``lifetime``."""

        if self.game_id != other.game_id:
            return False
        if lifetime is CacheLifetime.GAME:
            return True
        if self.turn != other.turn:
            return False
        if lifetime is CacheLifetime.TURN:
            return True
        if self.docket_generation != other.docket_generation:
            return False
        if lifetime is CacheLifetime.DOCKET:
            return True
        return self.command_index == other.command_index


@dataclass(frozen=True)
class StateFingerprint:
    """Separated hashes for rules, display, and docket/week dependencies."""

    rules_hash: str
    display_hash: str
    week_hash: str


def state_fingerprint(
    state,
    districts: Mapping[str, object],
    docket: Iterable[object],
    active_features: Iterable[object] | None = None,
    projects: Mapping[str, object] | None = None,
    *,
    game_id: str = "",
) -> StateFingerprint:
    """Return deterministic fingerprints for cache dependency categories."""

    docket_rows = sorted([_docket_row(item) for item in docket or ()], key=lambda row: row["item_id"])
    district_rows = [_district_rules_row(profile) for _cid, profile in _sorted_items(districts)]
    feature_rows = [_feature_rules_row(feature) for feature in active_features or ()]
    project_rows = [_project_row(project) for _pid, project in _sorted_items(projects or {})]

    rules_payload = {
        "game_id": game_id,
        "state": _state_rules_row(state),
        "districts": district_rows,
        "docket": docket_rows,
        "features": sorted(feature_rows, key=lambda row: row["feature_id"]),
        "projects": project_rows,
    }
    display_payload = {
        "game_id": game_id,
        "turn": int(getattr(state, "turn", 0) or 0),
        "districts": [_district_display_row(profile) for _cid, profile in _sorted_items(districts)],
        "features": sorted([_feature_display_row(feature) for feature in active_features or ()], key=lambda row: row["feature_id"]),
    }
    week_payload = {
        "game_id": game_id,
        "turn": int(getattr(state, "turn", 0) or 0),
        "week_day": int(getattr(state, "week_day", 0) or 0),
        "docket": docket_rows,
    }
    return StateFingerprint(
        rules_hash=stable_hash(rules_payload),
        display_hash=stable_hash(display_payload),
        week_hash=stable_hash(week_payload),
    )


def stable_hash(value) -> str:
    """Hash JSON-compatible or dataclass-like values deterministically."""

    encoded = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical(item) for item in value]
    if hasattr(value, "__dict__"):
        return _canonical(vars(value))
    return repr(value)


def _sorted_items(mapping: Mapping[str, object]):
    return sorted((mapping or {}).items(), key=lambda item: str(item[0]))


def _state_rules_row(state):
    return {
        "turn": int(getattr(state, "turn", 0) or 0),
        "ap": int(getattr(state, "ap", 0) or 0),
        "money": int(getattr(state, "money", 0) or 0),
        "status": getattr(state, "status", ""),
        "activity": int(getattr(state, "activity", 0) or 0),
        "friction": int(getattr(state, "friction", 0) or 0),
        "trust": int(getattr(state, "trust", 0) or 0),
        "exposure": int(getattr(state, "exposure", 0) or 0),
        "stakeholder_heat": dict(getattr(state, "stakeholder_heat", {}) or {}),
        "stakeholder_memory": dict(getattr(state, "stakeholder_memory", {}) or {}),
        "maintenance_backlog": int(getattr(state, "maintenance_backlog", 0) or 0),
        "pending_followups": dict(getattr(state, "pending_followups", {}) or {}),
    }


def _district_rules_row(profile):
    return {
        "cell_id": getattr(profile, "cell_id", ""),
        "population": int(getattr(profile, "population", 0) or 0),
        "activity": int(getattr(profile, "activity", 0) or 0),
        "friction": int(getattr(profile, "friction", 0) or 0),
        "trust": int(getattr(profile, "trust", 0) or 0),
        "exposure": int(getattr(profile, "exposure", 0) or 0),
        "services": int(getattr(profile, "services", 0) or 0),
        "district_type": getattr(profile, "district_type", ""),
        "land_use": getattr(profile, "land_use", ""),
        "dissatisfaction": dict(getattr(profile, "dissatisfaction", {}) or {}),
        "hazards": dict(getattr(profile, "hazards", {}) or {}),
        "network_access": dict(getattr(profile, "network_access", {}) or {}),
        "service_gap": dict(getattr(profile, "service_gap", {}) or {}),
        "housing_capacity": int(getattr(profile, "housing_capacity", 0) or 0),
        "affordability": int(getattr(profile, "affordability", 0) or 0),
    }


def _district_display_row(profile):
    return {
        "cell_id": getattr(profile, "cell_id", ""),
        "display_state": getattr(profile, "display_state", ""),
        "identity_state": getattr(profile, "identity_state", ""),
        "prosperity_band": getattr(profile, "prosperity_band", ""),
        "incident_state": getattr(profile, "incident_state", ""),
        "district_type": getattr(profile, "district_type", ""),
        "zoning_overlay": getattr(profile, "zoning_overlay", ""),
    }


def _docket_row(item):
    return {
        "item_id": getattr(item, "item_id", ""),
        "template_id": getattr(item, "template_id", ""),
        "status": getattr(item, "status", ""),
        "target_cell_ids": list(getattr(item, "target_cell_ids", []) or []),
        "turn": int(getattr(item, "turn", 0) or 0),
        "due_turn": int(getattr(item, "due_turn", 0) or 0),
        "project_id": getattr(item, "project_id", ""),
        "chain_step_id": getattr(item, "chain_step_id", ""),
        "subject_feature_id": getattr(item, "subject_feature_id", ""),
    }


def _feature_rules_row(feature):
    return {
        "feature_id": getattr(feature, "feature_id", ""),
        "archetype_id": getattr(feature, "archetype_id", ""),
        "status": getattr(feature, "status", ""),
        "target_cell_ids": list(getattr(feature, "target_cell_ids", []) or []),
        "condition": int(getattr(feature, "condition", 0) or 0),
        "maintenance_due_turn": int(getattr(feature, "maintenance_due_turn", 0) or 0),
        "project_id": getattr(feature, "project_id", ""),
        "item_id": getattr(feature, "item_id", ""),
        "display_state": getattr(feature, "display_state", ""),
    }


def _feature_display_row(feature):
    return {
        "feature_id": getattr(feature, "feature_id", ""),
        "status": getattr(feature, "status", ""),
        "display_state": getattr(feature, "display_state", ""),
        "condition": int(getattr(feature, "condition", 0) or 0),
    }


def _project_row(project):
    return {
        "project_id": getattr(project, "project_id", ""),
        "chain_template_id": getattr(project, "chain_template_id", ""),
        "current_step_id": getattr(project, "current_step_id", ""),
        "status": getattr(project, "status", ""),
        "due_turn": int(getattr(project, "due_turn", 0) or 0),
        "target_cell_ids": list(getattr(project, "target_cell_ids", []) or []),
    }
