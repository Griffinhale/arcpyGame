"""District buyout transition rules for hidden type pressure."""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Mapping

from .helpers import normalize_profile
from .models import DISTRICT_TYPES, CityState, DistrictProfile
from .type_pressure import adjust_type_ledger


@dataclass
class BuyoutRoundResult:
    """Result of one buyout bidding round."""

    started: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    report: str = ""


@dataclass
class TransitionResult:
    """Result of resolving due contested district transitions."""

    converted: list[str] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)
    report: str = ""


def resolve_buyout_round(
    state: CityState,
    districts: dict[str, DistrictProfile],
    ledger: dict[str, dict[str, int]],
    seed: int = 2026,
) -> BuyoutRoundResult:
    """Start deterministic contested transitions for weak adjacent districts."""

    if not districts:
        return BuyoutRoundResult()

    rng = random.Random(f"buyout:{seed}:{state.turn}")
    started: list[str] = []
    refused: list[str] = []
    reports: list[str] = []
    for cell_id in sorted(districts):
        target = districts[cell_id]
        if not _eligible_target(cell_id, target, districts):
            continue
        bidders = _eligible_bidders(target, districts, ledger, rng)
        if not bidders:
            continue
        bidder = bidders[0]
        if _target_refuses_buyout(target, rng):
            refused.append(cell_id)
            target.last_buyout_report = f"{target.name} refused buyout from {bidder.name} on turn {state.turn}."
            reports.append(
                f"{target.name} refused buyout from {bidder.name}; "
                f"local leverage held off {bidder.district_type.replace('_', ' ')} interests."
            )
            adjust_type_ledger(ledger, bidder.district_type, appetite_delta=-1, fatigue_delta=1)
            continue
        _start_contested_transition(state, target, bidder, ledger)
        started.append(cell_id)
        reports.append(
            f"{target.name} entered contested buyout from {bidder.name}; "
            f"{bidder.district_type.replace('_', ' ')} interests filed control papers."
        )

    return BuyoutRoundResult(started, refused, " ".join(reports))


def resolve_contested_transitions(
    state: CityState,
    districts: dict[str, DistrictProfile],
    ledger: dict[str, dict[str, int]],
) -> TransitionResult:
    """Resolve contested buyouts whose due turn has arrived."""

    if not districts:
        return TransitionResult()

    converted: list[str] = []
    cancelled: list[str] = []
    reports: list[str] = []
    for cell_id in sorted(districts):
        profile = districts[cell_id]
        if profile.identity_state != "contested":
            continue
        if int(profile.transition_due_turn or 0) > state.turn:
            continue
        if profile.prosperity >= 50 and profile.buyout_pressure <= 1:
            _cancel_transition(profile)
            cancelled.append(cell_id)
            reports.append(f"{profile.name} stabilized and cancelled its contested buyout.")
            continue
        if profile.prosperity < 50 or profile.buyout_pressure > 1:
            new_type = _contesting_type(profile, districts)
            if not new_type:
                _cancel_transition(profile)
                cancelled.append(cell_id)
                reports.append(f"{profile.name} cancelled a contested buyout with no active sponsor.")
                continue
            old_type = profile.district_type
            _convert_transition(profile, new_type, ledger)
            converted.append(cell_id)
            reports.append(
                f"{profile.name} converted from {old_type} to {new_type} after contested buyout pressure held."
            )

    return TransitionResult(converted, cancelled, " ".join(reports))


def reduce_buyout_pressure(profile: DistrictProfile, amount: int = 2) -> DistrictProfile:
    """Reduce hidden buyout pressure on a district after successful attention."""

    current = max(0, min(100, int(profile.buyout_pressure or 0)))
    if current == 0:
        return profile
    try:
        reduction = int(amount or 0)
    except (TypeError, ValueError):
        reduction = 0
    profile.buyout_pressure = max(0, current - max(0, reduction))
    if profile.identity_state == "vulnerable" and profile.buyout_pressure == 0:
        profile.identity_state = "stable"
    normalize_profile(profile)
    return profile


def _eligible_target(
    cell_id: str,
    target: DistrictProfile,
    districts: Mapping[str, DistrictProfile],
) -> bool:
    """Return whether a district can be targeted by a buyout bid."""

    if target.prosperity >= 50:
        return False
    if target.identity_state == "contested":
        return False
    if target.incident_state != "none":
        return False
    return any(adjacent_id in districts and adjacent_id != cell_id for adjacent_id in target.adjacent_cell_ids)


def _eligible_bidders(
    target: DistrictProfile,
    districts: Mapping[str, DistrictProfile],
    ledger: Mapping[str, Mapping[str, int]],
    rng: random.Random,
) -> list[DistrictProfile]:
    """Return adjacent bidders ordered by hidden pressure strength."""

    bidders: list[DistrictProfile] = []
    for adjacent_id in sorted(target.adjacent_cell_ids):
        bidder = districts.get(adjacent_id)
        if bidder is None:
            continue
        if bidder.identity_state == "contested":
            continue
        if bidder.district_type == target.district_type:
            continue
        if bidder.prosperity < target.prosperity + 8:
            continue
        entry = ledger.get(bidder.district_type, {})
        if int(entry.get("capital", 0) or 0) <= 0 or int(entry.get("appetite", 0) or 0) <= 0:
            continue
        bidders.append(bidder)

    rng.shuffle(bidders)
    return sorted(bidders, key=lambda bidder: _bidder_score(bidder, ledger), reverse=True)


def _target_refuses_buyout(target: DistrictProfile, rng: random.Random) -> bool:
    """Return whether target leverage blocks the current buyout bid."""

    prosperity = max(0, min(100, int(target.prosperity or 0)))
    pressure = max(0, min(100, int(target.buyout_pressure or 0)))
    refusal_chance = max(0.0, min(0.65, (prosperity - 30) * 0.025 - pressure * 0.06))
    return rng.random() < refusal_chance


def _bidder_score(
    bidder: DistrictProfile,
    ledger: Mapping[str, Mapping[str, int]],
) -> int:
    """Score one bidder using visible prosperity and hidden type pressure."""

    entry = ledger.get(bidder.district_type, {})
    return (
        bidder.prosperity
        + int(entry.get("capital", 0) or 0)
        + int(entry.get("appetite", 0) or 0) * 3
        - int(entry.get("fatigue", 0) or 0) * 2
        - int(entry.get("overextension", 0) or 0) * 3
    )


def _start_contested_transition(
    state: CityState,
    target: DistrictProfile,
    bidder: DistrictProfile,
    ledger: dict[str, dict[str, int]],
) -> None:
    """Mutate target and ledger for a newly filed contested transition."""

    target.identity_state = "contested"
    target.contesting_cell_id = bidder.cell_id
    target.contesting_type = bidder.district_type
    target.transition_due_turn = state.turn + 1
    target.last_buyout_report = (
        f"{target.name} entered contested buyout from {bidder.name} on turn {state.turn}."
    )
    adjust_type_ledger(
        ledger,
        bidder.district_type,
        capital_delta=-10,
        appetite_delta=-3,
        fatigue_delta=2,
        overextension_delta=1,
    )
    adjust_type_ledger(ledger, target.district_type, fatigue_delta=1)
    normalize_profile(target)


def _contesting_type(profile: DistrictProfile, districts: Mapping[str, DistrictProfile]) -> str:
    """Return the active contesting type for a due transition, if valid."""

    if profile.contesting_type in DISTRICT_TYPES and profile.contesting_type != profile.district_type:
        return profile.contesting_type
    bidder = districts.get(profile.contesting_cell_id)
    if bidder and bidder.district_type in DISTRICT_TYPES and bidder.district_type != profile.district_type:
        return bidder.district_type
    return ""


def _convert_transition(
    profile: DistrictProfile,
    new_type: str,
    ledger: dict[str, dict[str, int]],
) -> None:
    """Convert a contested district to its bidder type and update pressure."""

    old_type = profile.district_type
    profile.prior_district_type = old_type
    profile.district_type = new_type
    profile.land_use = ""
    profile.identity_state = "converted"
    profile.contesting_cell_id = ""
    profile.contesting_type = ""
    profile.transition_due_turn = 0
    profile.buyout_pressure = max(0, int(profile.buyout_pressure or 0) - 2)
    profile.prosperity = max(0, min(100, int(profile.prosperity or 0) + 4))
    profile.unrest = max(0, min(100, int(profile.unrest or 0) + 4))
    profile.last_buyout_report = f"{profile.name} converted from {old_type} to {new_type}."
    adjust_type_ledger(ledger, old_type, holdings_delta=-1, fatigue_delta=1)
    adjust_type_ledger(
        ledger,
        new_type,
        capital_delta=-5,
        holdings_delta=1,
        fatigue_delta=2,
        overextension_delta=1,
    )
    normalize_profile(profile)


def _cancel_transition(profile: DistrictProfile) -> None:
    """Clear contested transition fields after successful stabilization."""

    profile.identity_state = "stable"
    profile.contesting_cell_id = ""
    profile.contesting_type = ""
    profile.transition_due_turn = 0
    profile.buyout_pressure = max(0, min(1, int(profile.buyout_pressure or 0)))
    profile.last_buyout_report = f"{profile.name} cancelled a contested buyout."
    normalize_profile(profile)


__all__ = [name for name in globals() if not name.startswith("__")]
