"""Hidden per-district-type pressure ledger rules."""

from __future__ import annotations

from typing import Mapping

from .models import CityState, DISTRICT_TYPES, DistrictProfile


LEDGER_FIELDS = ("capital", "appetite", "fatigue", "holdings", "overextension")


def rebuild_type_ledger(districts: Mapping[str, DistrictProfile] | None) -> dict[str, dict[str, int]]:
    """Build a complete hidden type ledger from current district holdings."""

    profiles = list((districts or {}).values())
    # Bucket per-type sums in a single pass instead of filtering the profile
    # list once per district type (was O(types * profiles) with repeated sums).
    holdings_by_type = {dtype: 0 for dtype in DISTRICT_TYPES}
    capital_sum = {dtype: 0 for dtype in DISTRICT_TYPES}
    appetite_sum = {dtype: 0 for dtype in DISTRICT_TYPES}
    fatigue_sum = {dtype: 0 for dtype in DISTRICT_TYPES}
    for profile in profiles:
        dtype = getattr(profile, "district_type", "")
        if dtype not in holdings_by_type:
            continue
        activity = int(getattr(profile, "activity", 0) or 0)
        services = int(getattr(profile, "services", 0) or 0)
        friction = int(getattr(profile, "friction", 0) or 0)
        exposure = int(getattr(profile, "exposure", 0) or 0)
        holdings_by_type[dtype] += 1
        capital_sum[dtype] += max(0, activity)
        appetite_sum[dtype] += max(0, activity + services - friction)
        fatigue_sum[dtype] += max(0, friction + exposure)

    ledger: dict[str, dict[str, int]] = {}
    for dtype in DISTRICT_TYPES:
        holdings = holdings_by_type[dtype]
        if holdings:
            capital = capital_sum[dtype] // holdings
            appetite = appetite_sum[dtype] // max(1, holdings * 10)
            fatigue = fatigue_sum[dtype] // max(1, holdings * 12)
        else:
            capital = 0
            appetite = 0
            fatigue = 0
        overextension = max(0, holdings - max(1, capital // 25))
        ledger[dtype] = _normalize_entry(
            {
                "capital": capital,
                "appetite": appetite,
                "fatigue": fatigue,
                "holdings": holdings,
                "overextension": overextension,
            }
        )
    return ledger


def read_type_ledger(
    state: CityState,
    districts: Mapping[str, DistrictProfile] | None,
) -> dict[str, dict[str, int]]:
    """Return normalized city type pressure memory, rebuilding it when absent."""

    if not state.type_ledger and districts is None:
        return _empty_ledger()
    if districts is not None and _is_zero_ledger(state.type_ledger):
        return write_type_ledger(state, rebuild_type_ledger(districts))
    if not state.type_ledger:
        return write_type_ledger(state, rebuild_type_ledger(districts))
    return write_type_ledger(state, _normalize_ledger(state.type_ledger, districts))


def write_type_ledger(state: CityState, ledger: object) -> dict[str, dict[str, int]]:
    """Normalize and persist hidden type pressure memory on city state."""

    normalized = _normalize_ledger(ledger, None)
    state.type_ledger = normalized
    return normalized


def adjust_type_ledger(
    ledger: object,
    dtype: str,
    capital_delta: int = 0,
    appetite_delta: int = 0,
    fatigue_delta: int = 0,
    holdings_delta: int = 0,
    overextension_delta: int = 0,
) -> dict[str, dict[str, int]]:
    """Apply bounded deltas to one district type entry and return the ledger."""

    normalized = _normalize_ledger(ledger, None)
    if isinstance(ledger, dict):
        ledger.clear()
        ledger.update(normalized)
        normalized = ledger
    if dtype not in DISTRICT_TYPES:
        return normalized
    entry = normalized[dtype]
    entry["capital"] = _bounded(entry["capital"] + _coerce_int(capital_delta))
    entry["appetite"] = _bounded(entry["appetite"] + _coerce_int(appetite_delta))
    entry["fatigue"] = _bounded(entry["fatigue"] + _coerce_int(fatigue_delta))
    entry["holdings"] = max(0, entry["holdings"] + _coerce_int(holdings_delta))
    entry["overextension"] = _bounded(entry["overextension"] + _coerce_int(overextension_delta))
    return normalized


def type_pressure_summary(ledger: object) -> str:
    """Format one qualitative sentence about hidden district-type momentum."""

    normalized = _normalize_ledger(ledger, None)
    ranked = sorted(
        (
            (
                entry["capital"] + entry["appetite"] - entry["fatigue"] - entry["overextension"],
                dtype,
                entry,
            )
            for dtype, entry in normalized.items()
            if any(entry[field] for field in LEDGER_FIELDS)
        ),
        key=lambda row: (-row[0], row[1]),
    )
    if not ranked:
        return "District type pressure is quiet across the city."

    _score, dtype, entry = ranked[0]
    label = dtype.replace("_", " ").title()
    if entry["overextension"] >= entry["appetite"] and entry["overextension"] > 0:
        mood = "shows overextension strain"
    elif entry["fatigue"] >= entry["appetite"] and entry["fatigue"] > 0:
        mood = "is tiring under recent pressure"
    elif entry["capital"] >= 60 or entry["appetite"] >= 8:
        mood = "is carrying expansion pressure"
    else:
        mood = "is building quiet influence"
    return f"{label} {mood} while other district interests remain mostly hidden."


def _normalize_ledger(
    ledger: object,
    districts: Mapping[str, DistrictProfile] | None,
) -> dict[str, dict[str, int]]:
    """Return a complete, known-type-only ledger with integer fields."""

    rebuilt = rebuild_type_ledger(districts) if districts is not None else _empty_ledger()
    if not isinstance(ledger, Mapping):
        return rebuilt
    normalized: dict[str, dict[str, int]] = {}
    for dtype in DISTRICT_TYPES:
        entry = ledger.get(dtype, {})
        if isinstance(entry, Mapping):
            base = dict(rebuilt[dtype])
            base.update({field: entry.get(field, base[field]) for field in LEDGER_FIELDS})
            normalized[dtype] = _normalize_entry(base)
        else:
            normalized[dtype] = dict(rebuilt[dtype])
    return normalized


def _empty_ledger() -> dict[str, dict[str, int]]:
    """Build the empty default ledger without district-derived holdings."""

    return {dtype: _normalize_entry({}) for dtype in DISTRICT_TYPES}


def _is_zero_ledger(ledger: object) -> bool:
    """Return True when a ledger carries no authoritative pressure or holdings."""

    if not isinstance(ledger, Mapping):
        return False
    normalized = _normalize_ledger(ledger, None)
    return all(entry[field] == 0 for entry in normalized.values() for field in LEDGER_FIELDS)


def _normalize_entry(entry: Mapping[str, object]) -> dict[str, int]:
    """Coerce one ledger entry into bounded integer fields."""

    return {
        "capital": _bounded(entry.get("capital", 0)),
        "appetite": _bounded(entry.get("appetite", 0)),
        "fatigue": _bounded(entry.get("fatigue", 0)),
        "holdings": max(0, _coerce_int(entry.get("holdings", 0))),
        "overextension": _bounded(entry.get("overextension", 0)),
    }


def _bounded(value: object) -> int:
    """Clamp hidden pressure values to the same broad 0-100 gameplay band."""

    return max(0, min(100, _coerce_int(value)))


def _coerce_int(value: object) -> int:
    """Convert malformed numeric ledger values to deterministic integers."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [name for name in globals() if not name.startswith("__")]
