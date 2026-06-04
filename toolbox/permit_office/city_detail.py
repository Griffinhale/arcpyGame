"""Deterministic city-detail planning for seeded Permit Office maps.

This module is ArcPy-free. It describes the roads, blocks, anchors, and parks
that the ArcGIS adapter materializes into the existing support feature classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Iterable

from .models import DistrictProfile


@dataclass(frozen=True)
class CityDetailFeature:
    """A planned support-layer feature with geometry hints for ArcGIS."""

    feature_id: str
    archetype_id: str
    geometry_type: str
    target_cell_ids: tuple[str, ...]
    status: str
    display_state: str
    name: str
    capacity: int = 0
    intensity: int = 1
    owner_group: str = "city"
    metadata: dict[str, object] = field(default_factory=dict)
    state: dict[str, object] = field(default_factory=dict)
    geometry_hint: dict[str, object] = field(default_factory=dict)


def generate_city_detail_features(
    districts: Iterable[DistrictProfile] | dict[str, DistrictProfile],
    seed: int = 2026,
) -> list[CityDetailFeature]:
    """Return deterministic support-feature descriptors for city texture."""

    profiles = list(districts.values() if isinstance(districts, dict) else districts)
    profiles = sorted(profiles, key=lambda profile: profile.cell_id)
    if not profiles:
        return []
    rng = random.Random(f"{seed}:city-detail")
    by_id = {profile.cell_id: profile for profile in profiles}
    row_values = sorted({int(profile.cell_id[1:3]) for profile in profiles})
    col_values = sorted({int(profile.cell_id[3:5]) for profile in profiles})
    rows = len(row_values)
    cols = len(col_values)

    out: list[CityDetailFeature] = []
    horizontal_row = row_values[rng.randrange(rows)]
    vertical_col = col_values[(rng.randrange(cols) + 1) % cols]
    horizontal = [f"D{horizontal_row:02d}{col:02d}" for col in col_values if f"D{horizontal_row:02d}{col:02d}" in by_id]
    vertical = [f"D{row:02d}{vertical_col:02d}" for row in row_values if f"D{row:02d}{vertical_col:02d}" in by_id]
    if len(horizontal) >= 2:
        out.append(_line_feature(seed, "arterial-ew", "arterial_road", horizontal, "road", "Cross-Town Arterial", "horizontal", active=True))
    if len(vertical) >= 2:
        out.append(_line_feature(seed, "arterial-ns", "arterial_road", vertical, "road", "Market Spine Arterial", "vertical", active=True))

    utility_targets = _best_corridor(vertical, horizontal, by_id, prefer=("industrial", "civic", "mercantile"))
    if len(utility_targets) >= 2:
        orientation = "vertical" if utility_targets == vertical else "horizontal"
        out.append(_line_feature(seed, "utility", "utility_backbone", utility_targets, "utility", "Existing Utility Backbone", orientation, active=True))

    park_profiles = _park_profiles(profiles, rng)
    park_slots = {profile.cell_id: _park_slot(idx) for idx, profile in enumerate(park_profiles, start=1)}
    for profile in profiles:
        out.extend(_district_block_features(profile, seed, rng, reserved_slots={park_slots.get(profile.cell_id)}))
        if profile.cell_id not in set(horizontal + vertical):
            out.append(_local_street_stub(profile, seed, rng))

    for idx, profile in enumerate(park_profiles, start=1):
        cx, cy = park_slots[profile.cell_id]
        out.append(
            _zone_feature(
                seed,
                f"park-{idx}-{profile.cell_id}",
                "neighborhood_park",
                profile,
                "park",
                f"{profile.name} Neighborhood Park",
                status="active",
                capacity=2,
                geometry_hint={"shape": "rect", "cx": cx, "cy": cy, "w": 0.30, "h": 0.24},
                metadata={"seed_role": "neighborhood_park"},
            )
        )

    for idx, profile in enumerate(_anchor_profiles(profiles), start=1):
        out.append(_anchor_point(profile, seed, idx))

    return sorted(out, key=lambda feature: feature.feature_id)


def _line_feature(seed, suffix, archetype_id, targets, display_state, name, orientation, active=False):
    """Build a deterministic line descriptor for seeded map context."""

    return CityDetailFeature(
        feature_id=f"CITY-{seed}-{suffix}",
        archetype_id=archetype_id,
        geometry_type="LINE",
        target_cell_ids=tuple(targets),
        status="active" if active else "context",
        display_state=display_state,
        name=name,
        capacity=3 if archetype_id == "utility_backbone" else 2 if active else 0,
        intensity=3 if archetype_id == "utility_backbone" else 2 if active else 1,
        metadata={"seed_role": suffix, "generated_subtype": archetype_id},
        state={"seeded_city_detail": True},
        geometry_hint={"shape": "corridor", "orientation": orientation},
    )


def _best_corridor(vertical, horizontal, by_id, prefer):
    """Choose the corridor with the strongest preferred district-type fit."""

    def score(targets):
        """Score one candidate corridor by preferred district membership."""

        return sum(2 if by_id[cid].district_type in prefer else 0 for cid in targets)

    return vertical if score(vertical) >= score(horizontal) else horizontal


def _district_block_features(profile: DistrictProfile, seed: int, rng: random.Random, reserved_slots=None) -> list[CityDetailFeature]:
    """Create context block polygons for one district."""

    block_count = {"natural": 1, "industrial": 2, "civic": 2, "academic": 3, "mercantile": 4, "residential": 4}.get(profile.district_type, 3)
    archetype_id = {
        "residential": "residential_block",
        "mercantile": "commercial_block",
        "industrial": "industrial_yard",
        "civic": "civic_building",
        "academic": "academic_block",
        "natural": "natural_patch",
    }.get(profile.district_type, "commercial_block")
    display_state = {
        "residential": "housing",
        "mercantile": "commerce",
        "industrial": "industry",
        "civic": "civic",
        "academic": "campus",
        "natural": "park",
    }.get(profile.district_type, "building")
    features = []
    occupancy_budget = _occupancy_budget(profile, block_count)
    # Building slots are relative to the district polygon. Reserved slots keep
    # seeded parks from being covered by context building rectangles.
    positions = [slot for slot in _BUILDING_SLOTS if slot not in set(reserved_slots or ())]
    for idx, (cx, cy) in enumerate(positions[:block_count]):
        jitter = rng.randrange(-2, 3) / 100.0
        occupancy = occupancy_budget[idx] if idx < len(occupancy_budget) else 0
        # Footprint tracks land-use intensity: denser residential/commercial
        # blocks render larger than sparse industrial/civic ones. Bounded so the
        # rectangle stays inside the district and clear of the central road lane.
        scale = _block_size_scale(occupancy)
        features.append(
            _zone_feature(
                seed,
                f"{profile.cell_id}-block-{idx + 1}",
                archetype_id,
                profile,
                display_state,
                f"{profile.name} Block {idx + 1}",
                status="context",
                capacity=occupancy,
                geometry_hint={"shape": "rect", "cx": cx + jitter, "cy": cy - jitter, "w": round(0.19 * scale, 3), "h": round(0.17 * scale, 3)},
                metadata={
                    "seed_role": "city_block",
                    "generated_subtype": archetype_id,
                    "occupancy": occupancy,
                    "top_population_groups": _top_groups(profile, limit=3),
                },
            )
        )
    return features


def _zone_feature(seed, suffix, archetype_id, profile, display_state, name, status, capacity, geometry_hint, metadata):
    """Build a polygon descriptor with district metadata and geometry hints."""

    payload = {
        "district_id": profile.cell_id,
        "district_type": profile.district_type,
        **metadata,
    }
    return CityDetailFeature(
        feature_id=f"CITY-{seed}-{suffix}",
        archetype_id=archetype_id,
        geometry_type="POLYGON",
        target_cell_ids=(profile.cell_id,),
        status=status,
        display_state=display_state,
        name=name,
        capacity=capacity,
        intensity=max(1, min(4, capacity // 250 if capacity else 1)),
        metadata=payload,
        state={"seeded_city_detail": True},
        geometry_hint=geometry_hint,
    )


def _local_street_stub(profile, seed, rng):
    """Create a short local street hint inside a district without a corridor."""

    orientation = "horizontal" if rng.random() < 0.5 else "vertical"
    return CityDetailFeature(
        feature_id=f"CITY-{seed}-{profile.cell_id}-street",
        archetype_id="local_street_hint",
        geometry_type="LINE",
        target_cell_ids=(profile.cell_id,),
        status="context",
        display_state="road",
        name=f"{profile.name} Local Street",
        metadata={"district_id": profile.cell_id, "seed_role": "local_street_hint", "generated_subtype": orientation},
        state={"seeded_city_detail": True},
        geometry_hint={"shape": "stub", "orientation": orientation, "offset": 0.50},
    )


def _park_profiles(profiles, rng):
    """Select deterministic districts that should receive seeded parks."""

    candidates = [profile for profile in profiles if profile.district_type in ("natural", "residential", "academic")]
    if not candidates:
        candidates = profiles
    count = 2 if len(candidates) >= 8 else 1
    return sorted(rng.sample(candidates, k=min(count, len(candidates))), key=lambda profile: profile.cell_id)


def _anchor_profiles(profiles):
    """Pick one visible civic/commerce/campus anchor per preferred type."""

    preferred = [profile for profile in profiles if profile.district_type in ("civic", "mercantile", "academic")]
    selected = []
    seen_types = set()
    for profile in preferred:
        if profile.district_type not in seen_types:
            selected.append(profile)
            seen_types.add(profile.district_type)
        if len(selected) >= 6:
            break
    return selected


def _anchor_point(profile, seed, idx):
    """Create a point-of-interest descriptor for a prominent district anchor."""

    archetype_id = {
        "civic": "civic_building",
        "academic": "academic_block",
        "mercantile": "commercial_block",
    }.get(profile.district_type, "civic_building")
    # Anchor POIs are the prominent special-interest dots placed away from the
    # context blocks; they render larger than ordinary context points. The
    # district family stays in archetype_id/metadata for inspection.
    display_state = "special_interest"
    x, y = _POI_SLOTS[(idx - 1) % len(_POI_SLOTS)]
    return CityDetailFeature(
        feature_id=f"CITY-{seed}-anchor-{idx}-{profile.cell_id}",
        archetype_id=archetype_id,
        geometry_type="POINT",
        target_cell_ids=(profile.cell_id,),
        status="context",
        display_state=display_state,
        name=f"{profile.name} Anchor",
        capacity=max(1, profile.population // 12),
        metadata={
            "district_id": profile.cell_id,
            "seed_role": "point_of_interest",
            "generated_subtype": archetype_id,
            "occupancy": max(1, profile.population // 12),
            "top_population_groups": _top_groups(profile, limit=2),
        },
        state={"seeded_city_detail": True},
        geometry_hint={"shape": "point", "x": x, "y": y},
    )


_BUILDING_SLOTS = ((0.24, 0.24), (0.76, 0.24), (0.24, 0.76), (0.76, 0.76))
_POI_SLOTS = ((0.38, 0.24), (0.76, 0.38), (0.62, 0.76), (0.24, 0.62))


def _park_slot(idx):
    """Return a repeating relative slot for seeded park placement."""

    return _BUILDING_SLOTS[(idx - 1) % len(_BUILDING_SLOTS)]


def _block_size_scale(occupancy: int) -> float:
    """Scale a context block footprint by its occupancy (land-use intensity).

    Bounded to [0.8, 1.5] so blocks stay inside the district extent and never
    reach the central road lane at offset 0.50.
    """
    return max(0.8, min(1.5, 0.8 + max(0, int(occupancy or 0)) / 500.0))


def _occupancy_budget(profile, block_count):
    """Split district population into visible context-block occupancy."""

    if profile.district_type == "natural":
        return [0] * block_count
    share = 0.70 if profile.district_type in ("residential", "mercantile", "academic") else 0.35
    total = max(0, round(profile.population * share))
    if not total:
        return [0] * block_count
    base = total // block_count
    values = [base] * block_count
    for idx in range(total - base * block_count):
        values[idx % block_count] += 1
    return values


def _top_groups(profile, limit=3):
    """Return the highest-band population groups for context metadata."""

    return [
        group
        for group, band in sorted((profile.population_mix or {}).items(), key=lambda pair: (-int(pair[1] or 0), pair[0]))
        if band
    ][:limit]


__all__ = [name for name in globals() if not name.startswith("__")]
