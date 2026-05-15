"""Pure Python rules for the Permit Office prototype.

This module intentionally does not import ArcPy. The Python toolbox persists
these rules into feature classes and tables, but the gameplay math is kept
testable outside ArcGIS Pro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Iterable


CORE_METRICS = ("prosperity", "unrest", "culture", "risk")
DISTRICT_METRICS = CORE_METRICS + ("services",)

DISTRICT_TYPES = ("residential", "mercantile", "industrial", "civic", "academic", "natural")
FEATURE_FAMILIES = (
    "business",
    "public_resource",
    "natural_resource",
    "infrastructure",
    "event",
    "land_use",
    "incident",
    "compliance",
)
SERVICE_TYPES = (
    "child_services",
    "fire_response",
    "utilities",
    "mobility",
    "culture_access",
    "green_buffer",
)

LAND_USE_BY_DISTRICT_TYPE = {
    "residential": "housing",
    "mercantile": "commerce",
    "industrial": "industry",
    "civic": "civic_core",
    "academic": "campus",
    "natural": "open_space",
}

CITIZEN_GROUPS = (
    "families",
    "elders",
    "students",
    "commuters",
    "workers",
    "artists",
    "vendors",
    "homeowners",
    "renters",
    "civil_servants",
    "developers",
    "conservationists",
)

GROUP_LABELS = {
    "families": "families",
    "elders": "elders",
    "students": "students",
    "commuters": "commuters",
    "workers": "workers",
    "artists": "artists",
    "vendors": "vendors",
    "homeowners": "homeowners",
    "renters": "renters",
    "civil_servants": "civil servants",
    "developers": "developers",
    "conservationists": "conservationists",
}

PRESSURE_BAND_LABELS = ("absent", "noted", "present", "prominent")
GRIEVANCE_BAND_LABELS = ("quiet", "watching", "annoyed", "aggrieved", "incident-ready")

STAKEHOLDER_HEAT_THRESHOLD = 3
ENFORCEMENT_TEMPLATE_ID = "unpermitted_followthrough"
CIVIC_INCIDENT_TEMPLATE_ID = "civic_incident_response"
DISSATISFACTION_AGGRIEVED_THRESHOLD = 3
DISSATISFACTION_INCIDENT_THRESHOLD = 4

DISPLAY_STATES = (
    "stable",
    "prosperous",
    "restless",
    "cultured",
    "at_risk",
    "strained",
    "aggrieved",
    "incident",
)


@dataclass(frozen=True)
class FeatureArchetype:
    archetype_id: str
    label: str
    family: str
    geometry_type: str
    service_type: str = ""
    coverage_radius_m: int = 125
    capacity: int = 0
    land_use: str = ""
    base_effects: dict[str, int] = field(default_factory=dict)
    coverage_effects: dict[str, int] = field(default_factory=dict)
    allowed_district_types: tuple[str, ...] = ()
    conflict_district_types: tuple[str, ...] = ()
    incident_type: str = ""
    display_state: str = "active"


@dataclass(frozen=True)
class DocketTemplate:
    template_id: str
    title: str
    category: str
    geometry_type: str
    base_effects: dict[str, int]
    spillover_effects: dict[str, int]
    ap_cost: int = 1
    money_cost: int = 10
    mitigation_cost: int = 8
    expires_after: int = 0
    preview: str = ""
    inspect_hint: str = ""
    target_rule: str = ""
    stakeholder: str = "general_public"
    denial_heat: int = 1
    ignore_heat: int = 1
    failure_mode: str = ""
    failure_effects: dict[str, int] = field(default_factory=dict)
    failure_base_chance: float = 0.18
    good_fit_types: tuple[str, ...] = ()
    bad_fit_types: tuple[str, ...] = ()
    is_enforcement: bool = False
    is_incident: bool = False
    supporter_groups: tuple[str, ...] = ()
    concerned_groups: tuple[str, ...] = ()
    growth_groups: tuple[str, ...] = ()
    decline_groups: tuple[str, ...] = ()
    contact_name: str = ""
    spawn_archetype_id: str = ""


@dataclass
class DistrictProfile:
    cell_id: str
    name: str
    population: int
    prosperity: int
    unrest: int
    culture: int
    risk: int
    services: int
    district_type: str
    display_state: str = "stable"
    population_mix: dict[str, int] = field(default_factory=dict)
    dissatisfaction: dict[str, int] = field(default_factory=dict)
    incident_state: str = "none"
    incident_group: str = ""
    public_profile: str = ""
    land_use: str = ""
    zoning_overlay: str = ""
    service_gap: dict[str, int] = field(default_factory=dict)


@dataclass
class CityState:
    turn: int = 1
    max_turns: int = 6
    ap: int = 3
    max_ap: int = 3
    money: int = 60
    audit_stage: int = 0
    status: str = "playing"
    last_report: str = ""
    prosperity: int = 50
    unrest: int = 20
    culture: int = 35
    risk: int = 25
    stakeholder_heat: dict[str, int] = field(default_factory=dict)


@dataclass
class DocketItem:
    item_id: str
    template_id: str
    title: str
    geometry_type: str
    turn: int
    status: str = "open"
    inspected: bool = False
    target_cell_ids: list[str] = field(default_factory=list)
    preview_text: str = ""
    risk_band: str = "unknown"
    carryover: str = "expire_or_return"
    stakeholder: str = ""
    origin_item_id: str = ""
    target_rule: str = ""


@dataclass
class DecisionResult:
    ok: bool
    action: str
    item_id: str
    report: str
    city_delta: dict[str, int] = field(default_factory=dict)
    affected_cell_ids: list[str] = field(default_factory=list)
    district_deltas: dict[str, dict[str, int]] = field(default_factory=dict)
    item_status: str = ""
    command_status: str = "applied"
    stakeholder_delta: dict[str, int] = field(default_factory=dict)
    failure_triggered: bool = False


TEMPLATES: dict[str, DocketTemplate] = {
    "connector_corridor": DocketTemplate(
        "connector_corridor",
        "Connector Corridor Pilot",
        "transit",
        "LINE",
        {"prosperity": 5, "risk": -2, "unrest": 2},
        {"prosperity": 2, "risk": -1, "unrest": 1},
        money_cost=24,
        mitigation_cost=10,
        preview="Improves access between two districts; construction unrest and alignment complaints are possible.",
        inspect_hint="Ridership math is favorable, but construction notices have already been pre-appealed.",
        target_rule="Select exactly two districts to connect.",
        stakeholder="transit_authority",
        failure_mode="construction delay",
        failure_effects={"unrest": 3, "risk": 2, "prosperity": -2},
        failure_base_chance=0.22,
        good_fit_types=("mercantile", "civic"),
        bad_fit_types=("residential", "natural"),
        supporter_groups=("commuters", "workers", "developers"),
        concerned_groups=("homeowners", "elders", "conservationists"),
        growth_groups=("commuters", "workers"),
        contact_name="Deputy Alignment Officer Mira Parcel",
        spawn_archetype_id="connector_corridor",
    ),
    "procession_route": DocketTemplate(
        "procession_route",
        "Licensed Procession Route",
        "event",
        "LINE",
        {"culture": 8, "prosperity": 2, "unrest": 3, "risk": 1},
        {"culture": 2, "unrest": 1},
        money_cost=10,
        mitigation_cost=8,
        expires_after=1,
        preview="Temporary culture boost along a route; crowd-control side effects are plausible.",
        inspect_hint="Route review found enthusiasm, bottlenecks, and three mutually incompatible banner standards.",
        target_rule="Select exactly two districts for the route endpoints.",
        stakeholder="celebrants",
        denial_heat=2,
        failure_mode="crowd-control miss",
        failure_effects={"unrest": 3, "risk": 3, "culture": -1},
        failure_base_chance=0.24,
        good_fit_types=("civic", "academic", "mercantile"),
        bad_fit_types=("industrial", "natural"),
        supporter_groups=("artists", "students", "vendors"),
        concerned_groups=("commuters", "elders", "civil_servants"),
        growth_groups=("artists", "vendors"),
        contact_name="Procession Marshal Lenora Queue",
        spawn_archetype_id="licensed_procession",
    ),
    "utility_expansion_trench": DocketTemplate(
        "utility_expansion_trench",
        "Utility Expansion Trench",
        "utility",
        "LINE",
        {"risk": -6, "prosperity": 2, "unrest": 2},
        {"risk": -2, "unrest": 1},
        money_cost=22,
        mitigation_cost=8,
        preview="Reduces infrastructure risk; trench timing may create outages and formal sidewalk theories.",
        inspect_hint="Maps agree on the pipe location except where the pipe is most important.",
        target_rule="Select exactly two districts crossed by the utility work.",
        stakeholder="utility_board",
        ignore_heat=2,
        failure_mode="service outage",
        failure_effects={"risk": 5, "unrest": 2, "prosperity": -1},
        failure_base_chance=0.25,
        good_fit_types=("industrial", "civic"),
        bad_fit_types=("residential", "natural"),
        supporter_groups=("families", "workers", "civil_servants"),
        concerned_groups=("commuters", "vendors", "homeowners"),
        growth_groups=("workers",),
        contact_name="Utilities Cartographer Oren Plumb",
        spawn_archetype_id="utility_trench",
    ),
    "natural_reserve_conversion": DocketTemplate(
        "natural_reserve_conversion",
        "Natural Reserve Conversion",
        "land",
        "POLYGON",
        {"culture": 5, "risk": -4, "prosperity": -2, "unrest": 1},
        {"culture": 2, "risk": -1, "prosperity": -1},
        money_cost=12,
        mitigation_cost=5,
        preview="Protects land and lowers hazard pressure; development pressure may reappear in better shoes.",
        inspect_hint="Boundary markers are persuasive, except one that appears to have legal opinions.",
        target_rule="Select one or more districts proposed for reserve status.",
        stakeholder="conservation_trust",
        denial_heat=2,
        failure_mode="boundary dispute",
        failure_effects={"unrest": 3, "risk": 2, "culture": -2},
        failure_base_chance=0.20,
        good_fit_types=("natural", "academic"),
        bad_fit_types=("industrial", "mercantile"),
        supporter_groups=("conservationists", "artists", "elders"),
        concerned_groups=("developers", "workers", "commuters"),
        growth_groups=("conservationists",),
        decline_groups=("developers",),
        contact_name="Boundary Steward Iva Reed",
        spawn_archetype_id="protected_reserve",
    ),
    "mixed_use_rezoning": DocketTemplate(
        "mixed_use_rezoning",
        "Mixed-Use Rezoning Petition",
        "development",
        "POLYGON",
        {"prosperity": 6, "unrest": 3, "risk": 2, "culture": 1},
        {"prosperity": 2, "unrest": 1},
        money_cost=16,
        mitigation_cost=9,
        preview="Adds growth pressure and tax base; neighborhood fit and service capacity are uncertain.",
        inspect_hint="Applicant submitted renderings with people smiling near loading docks.",
        target_rule="Select one or more districts to rezone.",
        stakeholder="developers",
        denial_heat=2,
        failure_mode="zoning appeal",
        failure_effects={"unrest": 4, "risk": 1, "prosperity": -2},
        failure_base_chance=0.23,
        good_fit_types=("residential", "mercantile"),
        bad_fit_types=("natural", "civic"),
        supporter_groups=("developers", "workers", "commuters"),
        concerned_groups=("renters", "homeowners", "conservationists"),
        growth_groups=("renters", "workers", "commuters"),
        decline_groups=("conservationists",),
        contact_name="Petitioner Bram Floorplate",
        spawn_archetype_id="mixed_use_overlay",
    ),
    "child_development_park_annex": DocketTemplate(
        "child_development_park_annex",
        "Child Development Park Annex",
        "education",
        "POINT",
        {"culture": 5, "risk": -3, "unrest": -1, "prosperity": 1},
        {"culture": 1, "risk": -1},
        money_cost=18,
        mitigation_cost=6,
        preview="Adds family recreation and child services; traffic and staffing risk require reading the small folder.",
        inspect_hint="Need is clear; staffing plan depends on a committee that has named itself provisional twice.",
        target_rule="Select exactly one district for the annex.",
        stakeholder="families",
        denial_heat=2,
        failure_mode="staffing shortfall",
        failure_effects={"risk": 3, "unrest": 2, "culture": -1},
        failure_base_chance=0.18,
        good_fit_types=("residential", "academic", "civic"),
        bad_fit_types=("industrial",),
        supporter_groups=("families", "elders", "civil_servants"),
        concerned_groups=("commuters", "homeowners"),
        growth_groups=("families",),
        contact_name="Acting Recreation Notary June Totlot",
        spawn_archetype_id="child_service_annex",
    ),
    "street_vendor_compact": DocketTemplate(
        "street_vendor_compact",
        "Street Vendor Compact",
        "business",
        "POINT",
        {"prosperity": 6, "culture": 4, "unrest": 2, "risk": 1},
        {"prosperity": 2, "culture": 1, "unrest": 1},
        money_cost=12,
        mitigation_cost=6,
        preview="Creates visible small commerce; nuisance, sanitation, and queue geometry are lightly veiled issues.",
        inspect_hint="Public comments mention foot traffic, late music, and unusually precise snack zoning.",
        target_rule="Select exactly one host district.",
        stakeholder="vendors",
        denial_heat=2,
        ignore_heat=2,
        failure_mode="unlicensed spillover",
        failure_effects={"unrest": 3, "risk": 2, "prosperity": -1},
        failure_base_chance=0.22,
        good_fit_types=("mercantile", "residential"),
        bad_fit_types=("civic", "natural"),
        supporter_groups=("vendors", "artists", "students"),
        concerned_groups=("homeowners", "civil_servants", "commuters"),
        growth_groups=("vendors", "artists"),
        contact_name="Compact Spokesperson Della Cart",
        spawn_archetype_id="vendor_market",
    ),
    "contractor_renovation_waiver": DocketTemplate(
        "contractor_renovation_waiver",
        "Contractor Renovation Waiver",
        "residential",
        "POINT",
        {"prosperity": 4, "risk": 3, "unrest": 1},
        {"unrest": 1, "risk": 1},
        money_cost=14,
        mitigation_cost=7,
        preview="Speeds a residential project; contractor reliability and inspection burden are only partly knowable.",
        inspect_hint="The contractor has completed many jobs, several of which are admired from a distance.",
        target_rule="Select exactly one district containing the work.",
        stakeholder="contractors",
        ignore_heat=2,
        failure_mode="inspection failure",
        failure_effects={"risk": 6, "unrest": 2, "prosperity": -2},
        failure_base_chance=0.28,
        good_fit_types=("residential", "mercantile"),
        bad_fit_types=("natural", "academic"),
        supporter_groups=("homeowners", "developers", "workers"),
        concerned_groups=("renters", "elders"),
        growth_groups=("homeowners", "developers"),
        decline_groups=("renters",),
        contact_name="Licensed Expediter Hal Permit",
        spawn_archetype_id="renovation_site",
    ),
    "fire_budget_escalation": DocketTemplate(
        "fire_budget_escalation",
        "Fire Department Budget Escalation",
        "department",
        "POLYGON",
        {"risk": -7, "unrest": -1, "prosperity": -2},
        {"risk": -2},
        money_cost=20,
        mitigation_cost=5,
        preview="Improves response capacity; denial or delay will be remembered in very formal red ink.",
        inspect_hint="The department's incident trend is real; the proposed equipment list includes ceremonial ladders.",
        target_rule="Select one or more districts covered by the budget request.",
        stakeholder="fire_department",
        denial_heat=3,
        ignore_heat=2,
        failure_mode="coverage gap",
        failure_effects={"risk": 4, "unrest": 2},
        failure_base_chance=0.16,
        good_fit_types=("industrial", "civic", "residential"),
        bad_fit_types=("natural",),
        supporter_groups=("civil_servants", "families", "workers"),
        concerned_groups=("developers", "conservationists"),
        growth_groups=("civil_servants",),
        contact_name="Battalion Budget Clerk Rhea Ladder",
        spawn_archetype_id="fire_coverage_area",
    ),
    "public_art_museum_grant": DocketTemplate(
        "public_art_museum_grant",
        "Public Art and Museum Grant",
        "culture",
        "POINT",
        {"culture": 7, "prosperity": 1, "unrest": 1},
        {"culture": 2},
        money_cost=15,
        mitigation_cost=6,
        preview="Raises cultural profile; controversy risk is filed under community interpretation.",
        inspect_hint="The museum board is solvent, passionate, and unable to agree on the word temporary.",
        target_rule="Select exactly one district for the grant site.",
        stakeholder="arts_council",
        failure_mode="procurement scandal",
        failure_effects={"unrest": 3, "culture": -3, "prosperity": -1},
        failure_base_chance=0.20,
        good_fit_types=("civic", "academic", "mercantile"),
        bad_fit_types=("industrial",),
        supporter_groups=("artists", "students", "vendors"),
        concerned_groups=("civil_servants", "homeowners"),
        growth_groups=("artists", "students"),
        contact_name="Museum Board Chair Sable Plinth",
        spawn_archetype_id="museum_grant_site",
    ),
    ENFORCEMENT_TEMPLATE_ID: DocketTemplate(
        ENFORCEMENT_TEMPLATE_ID,
        "Unpermitted Follow-Through",
        "enforcement",
        "POINT",
        {"risk": -3, "unrest": 2, "prosperity": -1},
        {"unrest": 1},
        money_cost=8,
        mitigation_cost=6,
        preview="A previously rejected or ignored request appears to have proceeded in practical terms.",
        inspect_hint="Compliance photos are persuasive but timestamped with civic optimism.",
        target_rule="Select exactly one district where the unpermitted work or event is visible.",
        stakeholder="general_public",
        denial_heat=2,
        ignore_heat=2,
        is_enforcement=True,
        supporter_groups=("civil_servants", "homeowners"),
        concerned_groups=("vendors", "renters", "workers"),
        contact_name="Compliance Inspector Niko Ledger",
        spawn_archetype_id="compliance_case",
    ),
    CIVIC_INCIDENT_TEMPLATE_ID: DocketTemplate(
        CIVIC_INCIDENT_TEMPLATE_ID,
        "Civic Incident Response",
        "incident",
        "POINT",
        {"unrest": -2, "risk": -1, "prosperity": -1},
        {"unrest": -1},
        money_cost=9,
        mitigation_cost=7,
        preview="A local grievance has become administratively visible and requests a response before it becomes policy.",
        inspect_hint="Complaint packet includes signatures, two maps, and a folder labeled previous folder.",
        target_rule="Select exactly one district where the civic incident is visible.",
        stakeholder="general_public",
        denial_heat=1,
        ignore_heat=2,
        is_incident=True,
        supporter_groups=("civil_servants",),
        concerned_groups=("families", "workers", "renters", "vendors"),
        contact_name="Incident Intake Coordinator Vera Stamp",
        spawn_archetype_id="civic_incident_marker",
    ),
}

DEMO_TEMPLATE_IDS = (
    "connector_corridor",
    "procession_route",
    "utility_expansion_trench",
    "natural_reserve_conversion",
    "mixed_use_rezoning",
    "child_development_park_annex",
    "street_vendor_compact",
    "contractor_renovation_waiver",
    "fire_budget_escalation",
    "public_art_museum_grant",
)

DEMO_SEQUENCE = {
    1: ("connector_corridor", "procession_route", "street_vendor_compact"),
    2: ("utility_expansion_trench", "contractor_renovation_waiver", "public_art_museum_grant"),
    3: ("natural_reserve_conversion", "mixed_use_rezoning", "fire_budget_escalation"),
    4: ("child_development_park_annex", "street_vendor_compact", "utility_expansion_trench"),
    5: ("connector_corridor", "mixed_use_rezoning", "public_art_museum_grant"),
    6: ("natural_reserve_conversion", "fire_budget_escalation", "procession_route"),
}


FEATURE_ARCHETYPES: dict[str, FeatureArchetype] = {
    "connector_corridor": FeatureArchetype(
        "connector_corridor",
        "Connector Corridor",
        "infrastructure",
        "LINE",
        service_type="mobility",
        coverage_radius_m=150,
        capacity=2,
        land_use="transport_corridor",
        coverage_effects={"prosperity": 1, "risk": -1, "services": 1},
        allowed_district_types=("mercantile", "civic", "industrial"),
        conflict_district_types=("natural", "residential"),
    ),
    "licensed_procession": FeatureArchetype(
        "licensed_procession",
        "Licensed Procession",
        "event",
        "LINE",
        service_type="culture_access",
        coverage_radius_m=110,
        capacity=1,
        land_use="temporary_event_route",
        coverage_effects={"culture": 1, "unrest": 1},
        allowed_district_types=("civic", "academic", "mercantile"),
        conflict_district_types=("industrial", "natural"),
        incident_type="crowd_control",
        display_state="temporary",
    ),
    "utility_trench": FeatureArchetype(
        "utility_trench",
        "Utility Trench",
        "infrastructure",
        "LINE",
        service_type="utilities",
        coverage_radius_m=125,
        capacity=3,
        land_use="utility_corridor",
        coverage_effects={"risk": -1, "services": 3},
        allowed_district_types=("industrial", "civic", "mercantile"),
        conflict_district_types=("natural", "residential"),
    ),
    "protected_reserve": FeatureArchetype(
        "protected_reserve",
        "Protected Reserve",
        "natural_resource",
        "POLYGON",
        service_type="green_buffer",
        coverage_radius_m=90,
        capacity=3,
        land_use="protected_reserve",
        coverage_effects={"culture": 1, "risk": -1, "services": 1},
        allowed_district_types=("natural", "academic"),
        conflict_district_types=("industrial", "mercantile"),
    ),
    "mixed_use_overlay": FeatureArchetype(
        "mixed_use_overlay",
        "Mixed-Use Overlay",
        "land_use",
        "POLYGON",
        coverage_radius_m=100,
        land_use="mixed_use",
        coverage_effects={"prosperity": 1, "unrest": 1},
        allowed_district_types=("residential", "mercantile"),
        conflict_district_types=("natural", "civic"),
        display_state="overlay",
    ),
    "child_service_annex": FeatureArchetype(
        "child_service_annex",
        "Child Service Annex",
        "public_resource",
        "POINT",
        service_type="child_services",
        coverage_radius_m=125,
        capacity=4,
        land_use="civic_service",
        coverage_effects={"culture": 1, "risk": -1, "services": 4},
        allowed_district_types=("residential", "academic", "civic"),
        conflict_district_types=("industrial",),
    ),
    "vendor_market": FeatureArchetype(
        "vendor_market",
        "Vendor Market",
        "business",
        "POINT",
        service_type="culture_access",
        coverage_radius_m=100,
        capacity=2,
        land_use="commerce",
        coverage_effects={"prosperity": 1, "culture": 1, "services": 1},
        allowed_district_types=("mercantile", "residential"),
        conflict_district_types=("civic", "natural"),
        incident_type="sanitation",
    ),
    "renovation_site": FeatureArchetype(
        "renovation_site",
        "Renovation Site",
        "land_use",
        "POINT",
        coverage_radius_m=80,
        land_use="residential_renewal",
        coverage_effects={"prosperity": 1},
        allowed_district_types=("residential", "mercantile"),
        conflict_district_types=("natural", "academic"),
        incident_type="inspection",
    ),
    "fire_coverage_area": FeatureArchetype(
        "fire_coverage_area",
        "Fire Coverage Area",
        "public_resource",
        "POLYGON",
        service_type="fire_response",
        coverage_radius_m=160,
        capacity=5,
        land_use="public_safety",
        coverage_effects={"risk": -3, "services": 3},
        allowed_district_types=("industrial", "civic", "residential"),
        conflict_district_types=("natural",),
    ),
    "museum_grant_site": FeatureArchetype(
        "museum_grant_site",
        "Museum Grant Site",
        "public_resource",
        "POINT",
        service_type="culture_access",
        coverage_radius_m=130,
        capacity=3,
        land_use="cultural",
        coverage_effects={"culture": 2, "services": 1},
        allowed_district_types=("civic", "academic", "mercantile"),
        conflict_district_types=("industrial",),
    ),
    "compliance_case": FeatureArchetype(
        "compliance_case",
        "Compliance Case",
        "compliance",
        "POINT",
        coverage_radius_m=75,
        land_use="compliance_case",
        coverage_effects={"unrest": 1},
        incident_type="noncompliance",
        display_state="case",
    ),
    "civic_incident_marker": FeatureArchetype(
        "civic_incident_marker",
        "Civic Incident Marker",
        "incident",
        "POINT",
        coverage_radius_m=75,
        land_use="incident_file",
        coverage_effects={"unrest": -1, "risk": -1},
        incident_type="civic_grievance",
        display_state="incident",
    ),
}


ARCHETYPE_BASE_MIX = {
    "residential": {"families": 3, "homeowners": 2, "renters": 2, "elders": 1, "commuters": 1},
    "mercantile": {"vendors": 3, "workers": 2, "commuters": 2, "renters": 1, "artists": 1},
    "industrial": {"workers": 3, "commuters": 2, "civil_servants": 1, "renters": 1, "developers": 1},
    "civic": {"civil_servants": 3, "commuters": 2, "elders": 1, "families": 1, "workers": 1},
    "academic": {"students": 3, "artists": 2, "commuters": 1, "renters": 1, "workers": 1},
    "natural": {"conservationists": 3, "elders": 1, "artists": 1, "commuters": 1, "families": 1},
}

PRESSURE_DRIFT_GROUPS = {
    "residential": ("families", "renters"),
    "mercantile": ("workers", "vendors"),
    "industrial": ("workers", "commuters"),
    "civic": ("civil_servants", "commuters"),
    "academic": ("students", "artists"),
    "natural": ("conservationists", "artists"),
}

INCIDENT_STATE_BY_GROUP = {
    "workers": "strike",
    "civil_servants": "strike",
    "vendors": "noncompliance",
    "developers": "noncompliance",
    "homeowners": "petition",
    "elders": "complaints",
    "commuters": "complaints",
}


def generate_district_profiles(rows: int = 5, cols: int = 5, seed: int = 2026) -> list[DistrictProfile]:
    rng = random.Random(seed)
    prefixes = ["North", "Old", "Canal", "Bright", "Lower", "Cinder", "Glass", "Civic"]
    suffixes = ["Ward", "Market", "Steps", "Yard", "Row", "Crossing", "Annex", "Green"]
    profiles: list[DistrictProfile] = []
    for row in range(rows):
        for col in range(cols):
            cell_id = f"D{row:02d}{col:02d}"
            dtype = DISTRICT_TYPES[(row + col + rng.randrange(len(DISTRICT_TYPES))) % len(DISTRICT_TYPES)]
            base = 30 + rng.randrange(36)
            prosperity = max(10, min(90, base + rng.randrange(-12, 13)))
            unrest = max(5, min(80, 28 + rng.randrange(-14, 15)))
            culture = max(10, min(90, 34 + rng.randrange(-14, 22)))
            risk = max(5, min(80, 26 + rng.randrange(-12, 18)))
            services = max(5, min(90, 35 + rng.randrange(-15, 16)))
            population_mix = _initial_population_mix(dtype, rng)
            dissatisfaction = _initial_dissatisfaction(population_mix, prosperity, unrest, risk, services)
            profile = DistrictProfile(
                cell_id=cell_id,
                name=f"{rng.choice(prefixes)} {rng.choice(suffixes)}",
                population=650 + rng.randrange(2200),
                prosperity=prosperity,
                unrest=unrest,
                culture=culture,
                risk=risk,
                services=services,
                district_type=dtype,
                population_mix=population_mix,
                dissatisfaction=dissatisfaction,
            )
            normalize_profile(profile)
            profiles.append(profile)
    return profiles


def generate_docket(
    turn: int,
    seed: int = 2026,
    count: int = 3,
    state: CityState | None = None,
    districts: dict[str, DistrictProfile] | None = None,
) -> list[DocketItem]:
    chosen = list(DEMO_SEQUENCE.get(turn, ()))
    if len(chosen) < count:
        rng = random.Random(seed * 1000 + turn)
        pool = [template_id for template_id in DEMO_TEMPLATE_IDS if template_id not in chosen]
        chosen.extend(rng.sample(pool, min(count - len(chosen), len(pool))))

    items: list[DocketItem] = []
    if districts:
        followup = _incident_followup_item(turn, districts)
        if followup:
            items.append(followup)

    if state:
        followup = _heat_followup_item(turn, state)
        if followup and len(items) < count:
            items.append(followup)

    for template_id in chosen:
        if len(items) >= count:
            break
        items.append(_make_docket_item(turn, len(items) + 1, template_id))
    return items


def _make_docket_item(turn: int, idx: int, template_id: str, stakeholder: str = "", origin_item_id: str = "") -> DocketItem:
    template = TEMPLATES[template_id]
    item_stakeholder = stakeholder or template.stakeholder
    item_id = f"T{turn:02d}-{idx:02d}-{template_id}"
    title = template.title
    preview = template.preview
    if template.is_enforcement and item_stakeholder != template.stakeholder:
        label = item_stakeholder.replace("_", " ").title()
        title = f"Compliance Follow-Up: {label}"
        item_id = f"T{turn:02d}-{idx:02d}-{template_id}-{item_stakeholder}"
        preview = f"{template.preview} Stakeholder heat is now focused on {label}."
    elif template.is_incident and item_stakeholder != template.stakeholder:
        label = _group_label(item_stakeholder).title()
        title = f"Civic Incident Response: {label}"
        item_id = f"T{turn:02d}-{idx:02d}-{template_id}-{item_stakeholder}"
        preview = f"{template.preview} Incident file is currently attached to {label}."
    return DocketItem(
        item_id=item_id,
        template_id=template_id,
        title=title,
        geometry_type=template.geometry_type,
        turn=turn,
        preview_text=preview,
        stakeholder=item_stakeholder,
        origin_item_id=origin_item_id,
        target_rule=template.target_rule,
    )


def _heat_followup_item(turn: int, state: CityState) -> DocketItem | None:
    hot = [(stakeholder, heat) for stakeholder, heat in state.stakeholder_heat.items() if heat >= STAKEHOLDER_HEAT_THRESHOLD]
    if not hot:
        return None
    stakeholder, _heat = sorted(hot, key=lambda pair: (-pair[1], pair[0]))[0]
    return _make_docket_item(turn, 1, ENFORCEMENT_TEMPLATE_ID, stakeholder=stakeholder, origin_item_id="stakeholder_heat")


def _incident_followup_item(turn: int, districts: dict[str, DistrictProfile]) -> DocketItem | None:
    visible = []
    for profile in districts.values():
        normalize_profile(profile)
        if profile.incident_state != "none" and profile.incident_group:
            visible.append((profile.incident_state, profile.incident_group, profile.cell_id))
    if not visible:
        return None
    incident_state, group, cell_id = sorted(visible, key=lambda row: (row[2], row[1], row[0]))[0]
    item = _make_docket_item(turn, 1, CIVIC_INCIDENT_TEMPLATE_ID, stakeholder=group, origin_item_id=f"dissatisfaction:{cell_id}:{group}")
    item.preview_text = f"{item.preview_text} Visible condition: {incident_state} in {cell_id}."
    return item


def inspect_item(item: DocketItem, seed: int = 2026, target_profiles: Iterable[DistrictProfile] | None = None) -> DocketItem:
    template = TEMPLATES[item.template_id]
    rng = random.Random(f"{seed}:{item.item_id}:inspect")
    item.inspected = True
    item.stakeholder = item.stakeholder or template.stakeholder
    item.target_rule = item.target_rule or template.target_rule
    item.risk_band = rng.choice(["low", "medium", "medium", "high"])
    failure_text = f" Failure mode on file: {template.failure_mode}." if template.failure_mode else ""
    population_text = inspection_population_note(template, list(target_profiles or ()))
    item.preview_text = (
        f"{template.preview} Inspection: {item.risk_band.upper()} side-effect risk. "
        f"{template.inspect_hint}{failure_text} {population_text}"
    ).strip()
    return item


def resolve_decision(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile],
    action: str,
    target_cell_ids: Iterable[str],
    spillover_cell_ids: Iterable[str] = (),
    seed: int = 2026,
    mitigated: bool = False,
) -> DecisionResult:
    action_key = action.lower().strip()
    targets = _unique_known(target_cell_ids, districts)
    spillovers = [cid for cid in _unique_known(spillover_cell_ids, districts) if cid not in targets]
    template = TEMPLATES[item.template_id]
    archetype = feature_archetype_for_template(template)
    item.stakeholder = item.stakeholder or template.stakeholder
    item.target_rule = item.target_rule or template.target_rule

    if action_key == "inspect":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Inspection requires 1 AP.")
        state.ap -= 1
        inspect_item(item, seed, [districts[cid] for cid in targets])
        item.status = "inspected"
        return DecisionResult(
            True,
            action,
            item.item_id,
            f"Inspection completed for {item.title}: {item.preview_text}",
            affected_cell_ids=targets,
            item_status=item.status,
        )

    if template.is_enforcement:
        return _resolve_enforcement_decision(
            state,
            item,
            districts,
            action,
            action_key,
            targets,
            spillovers,
            template,
            mitigated,
        )

    if template.is_incident:
        return _resolve_incident_decision(
            state,
            item,
            districts,
            action,
            action_key,
            targets,
            spillovers,
            template,
            mitigated,
        )

    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Denial requires 1 AP.")
        state.ap -= 1
        item.status = "denied"
        delta = {"unrest": 1, "prosperity": -1}
        _apply_city_delta(state, delta)
        district_deltas = _apply_population_reaction(template, [districts[cid] for cid in targets], "deny", mitigated)
        surfaced = _surface_new_incidents(state, [districts[cid] for cid in targets])
        if surfaced:
            delta["unrest"] = delta.get("unrest", 0) + surfaced
        heat_delta = _adjust_heat(state, item.stakeholder, template.denial_heat)
        report = (
            f"Denied {item.title}. Project risk avoided; {item.stakeholder.replace('_', ' ')} heat "
            f"{heat_delta:+d} entered the public record. {_population_report_fragment([districts[cid] for cid in targets])}"
        )
        return DecisionResult(
            True,
            action,
            item.item_id,
            report,
            delta,
            targets,
            district_deltas,
            item_status=item.status,
            stakeholder_delta={item.stakeholder: heat_delta},
        )

    if action_key not in ("approve", "approve_mitigated"):
        return _blocked(action, item.item_id, f"Unknown decision action {action!r}.")
    if not targets:
        return _blocked(action, item.item_id, "Approve requires at least one selected target district.")
    if state.ap < template.ap_cost:
        return _blocked(action, item.item_id, f"Approval requires {template.ap_cost} AP.")
    total_money = template.money_cost + (template.mitigation_cost if mitigated else 0)
    if state.money < total_money:
        return _blocked(action, item.item_id, f"Approval requires ${total_money}.")

    district_deltas: dict[str, dict[str, int]] = {}
    city_delta = {metric: 0 for metric in CORE_METRICS}
    rng = random.Random(f"{seed}:{item.item_id}:{','.join(targets)}:{mitigated}")

    state.ap -= template.ap_cost
    state.money -= total_money
    item.target_cell_ids = targets

    for cid in targets:
        delta = _district_adjusted_effects(template.base_effects, districts[cid].district_type, template.category)
        delta = _land_use_adjusted_effects(delta, districts[cid], archetype)
        _merge_delta(delta, _service_coverage_effect(archetype, districts[cid], "target"))
        if mitigated:
            delta = _mitigate(delta)
        _apply_profile_delta(districts[cid], delta)
        district_deltas[cid] = delta
        _merge_delta(city_delta, delta)

    for cid in spillovers:
        delta = dict(template.spillover_effects)
        delta = _land_use_adjusted_effects(delta, districts[cid], archetype)
        _merge_delta(delta, _service_coverage_effect(archetype, districts[cid], "spillover"))
        if mitigated:
            delta = _mitigate(delta)
        _apply_profile_delta(districts[cid], delta)
        district_deltas[cid] = delta
        _merge_delta(city_delta, delta)

    side = _context_side_effect(template, [districts[cid] for cid in targets], rng, mitigated)
    if side:
        for cid in targets:
            _apply_profile_delta(districts[cid], side)
            _merge_delta(district_deltas.setdefault(cid, {}), side)
        _merge_delta(city_delta, side)

    failure_delta = _approval_failure_effect(template, [districts[cid] for cid in targets], item.risk_band, rng, mitigated)
    failure_triggered = bool(failure_delta)
    if failure_triggered:
        item.status = "failed"
        for cid in targets:
            _apply_profile_delta(districts[cid], failure_delta)
            _merge_delta(district_deltas.setdefault(cid, {}), failure_delta)
        _merge_delta(city_delta, failure_delta)
    else:
        item.status = "active"
        for cid in targets:
            _apply_land_use_change(districts[cid], archetype)
            normalize_profile(districts[cid])

    population_deltas = _apply_population_reaction(
        template,
        [districts[cid] for cid in targets],
        "failure" if failure_triggered else "approve",
        mitigated,
    )
    for cid, delta in population_deltas.items():
        _merge_delta(district_deltas.setdefault(cid, {}), delta)
    surfaced = _surface_new_incidents(state, [districts[cid] for cid in targets])

    averaged = {metric: round(value / max(1, len(targets) + len(spillovers))) for metric, value in city_delta.items()}
    _apply_city_delta(state, averaged)
    if surfaced:
        averaged["unrest"] = averaged.get("unrest", 0) + surfaced
    affected = targets + spillovers
    mitigation_text = " with mitigation" if mitigated else ""
    failure_text = ""
    if failure_triggered:
        failure_text = f" Outcome failed: {template.failure_mode}; corrective delta {_format_delta(failure_delta)}."
    report = (
        f"Approved {item.title}{mitigation_text}. Affected {len(affected)} district(s): "
        f"{', '.join(affected)}. City delta: {_format_delta(averaged)}.{failure_text} "
        f"{_population_report_fragment([districts[cid] for cid in targets])}"
    )
    return DecisionResult(
        True,
        action,
        item.item_id,
        report,
        averaged,
        affected,
        district_deltas,
        item.status,
        failure_triggered=failure_triggered,
    )


def _resolve_enforcement_decision(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile],
    action: str,
    action_key: str,
    targets: list[str],
    spillovers: list[str],
    template: DocketTemplate,
    mitigated: bool,
) -> DecisionResult:
    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Deferring enforcement requires 1 AP.")
        state.ap -= 1
        item.status = "deferred"
        delta = {"unrest": 2, "risk": 1}
        _apply_city_delta(state, delta)
        heat_delta = _adjust_heat(state, item.stakeholder, template.denial_heat)
        report = (
            f"Deferred enforcement for {item.title}. The unpermitted condition remains useful to someone; "
            f"{item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}."
        )
        return DecisionResult(
            True,
            action,
            item.item_id,
            report,
            delta,
            targets,
            item_status=item.status,
            stakeholder_delta={item.stakeholder: heat_delta},
        )

    if action_key not in ("approve", "approve_mitigated"):
        return _blocked(action, item.item_id, f"Unknown decision action {action!r}.")
    if not targets:
        return _blocked(action, item.item_id, "Enforcement requires one selected district.")
    if state.ap < template.ap_cost:
        return _blocked(action, item.item_id, f"Enforcement requires {template.ap_cost} AP.")
    total_money = template.money_cost + (template.mitigation_cost if mitigated else 0)
    if state.money < total_money:
        return _blocked(action, item.item_id, f"Enforcement requires ${total_money}.")

    state.ap -= template.ap_cost
    state.money -= total_money
    item.target_cell_ids = targets
    item.status = "settled" if mitigated else "enforced"

    district_deltas: dict[str, dict[str, int]] = {}
    city_delta = {metric: 0 for metric in CORE_METRICS}
    base = _mitigate(template.base_effects) if mitigated else dict(template.base_effects)
    spill = _mitigate(template.spillover_effects) if mitigated else dict(template.spillover_effects)

    for cid in targets:
        _apply_profile_delta(districts[cid], base)
        district_deltas[cid] = dict(base)
        _merge_delta(city_delta, base)

    for cid in spillovers:
        delta = dict(spill)
        _apply_profile_delta(districts[cid], delta)
        district_deltas[cid] = delta
        _merge_delta(city_delta, delta)

    heat_relief = -2 if mitigated else -STAKEHOLDER_HEAT_THRESHOLD
    heat_delta = _adjust_heat(state, item.stakeholder, heat_relief)
    averaged = {metric: round(value / max(1, len(targets) + len(spillovers))) for metric, value in city_delta.items()}
    _apply_city_delta(state, averaged)
    affected = targets + spillovers
    if mitigated:
        report = (
            f"Settled {item.title} through a retroactive permit and compliance schedule. "
            f"City delta: {_format_delta(averaged)}. {item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}."
        )
    else:
        report = (
            f"Enforced {item.title}. The record is clearer and several people are louder. "
            f"City delta: {_format_delta(averaged)}. {item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}."
        )
    return DecisionResult(
        True,
        action,
        item.item_id,
        report,
        averaged,
        affected,
        district_deltas,
        item.status,
        stakeholder_delta={item.stakeholder: heat_delta},
    )


def _resolve_incident_decision(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile],
    action: str,
    action_key: str,
    targets: list[str],
    spillovers: list[str],
    template: DocketTemplate,
    mitigated: bool,
) -> DecisionResult:
    if not targets:
        return _blocked(action, item.item_id, "Incident response requires one selected district.")
    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Deferring a civic incident requires 1 AP.")
        state.ap -= 1
        item.status = "deferred"
        group = item.stakeholder if item.stakeholder in CITIZEN_GROUPS else _top_dissatisfaction(districts[targets[0]])[0]
        for cid in targets:
            _adjust_dissatisfaction(districts[cid], (group,), 1)
            normalize_profile(districts[cid])
        delta = {"unrest": 2, "risk": 1}
        _apply_city_delta(state, delta)
        heat_delta = _adjust_heat(state, group, template.denial_heat)
        report = (
            f"Deferred {item.title}. The incident remains local in form and citywide in tone. "
            f"City delta: {_format_delta(delta)}. {_group_label(group).title()} heat {heat_delta:+d}."
        )
        return DecisionResult(
            True,
            action,
            item.item_id,
            report,
            delta,
            targets,
            {cid: {"dissatisfaction": 1} for cid in targets},
            item.status,
            stakeholder_delta={group: heat_delta},
        )

    if action_key not in ("approve", "approve_mitigated"):
        return _blocked(action, item.item_id, f"Unknown decision action {action!r}.")
    if state.ap < template.ap_cost:
        return _blocked(action, item.item_id, f"Incident response requires {template.ap_cost} AP.")
    total_money = template.money_cost + (template.mitigation_cost if mitigated else 0)
    if state.money < total_money:
        return _blocked(action, item.item_id, f"Incident response requires ${total_money}.")

    state.ap -= template.ap_cost
    state.money -= total_money
    item.target_cell_ids = targets
    item.status = "settled" if mitigated else "responded"
    group = item.stakeholder if item.stakeholder in CITIZEN_GROUPS else _top_dissatisfaction(districts[targets[0]])[0]
    relief = -3 if mitigated else -2
    base = _mitigate(template.base_effects) if mitigated else dict(template.base_effects)
    spill = _mitigate(template.spillover_effects) if mitigated else dict(template.spillover_effects)
    district_deltas: dict[str, dict[str, int]] = {}
    city_delta = {metric: 0 for metric in CORE_METRICS}

    for cid in targets:
        _apply_profile_delta(districts[cid], base)
        _adjust_dissatisfaction(districts[cid], (group,), relief)
        normalize_profile(districts[cid])
        district_deltas[cid] = dict(base)
        district_deltas[cid]["dissatisfaction"] = relief
        _merge_delta(city_delta, base)

    for cid in spillovers:
        delta = dict(spill)
        _apply_profile_delta(districts[cid], delta)
        _adjust_dissatisfaction(districts[cid], (group,), -1)
        normalize_profile(districts[cid])
        district_deltas[cid] = delta
        district_deltas[cid]["dissatisfaction"] = -1
        _merge_delta(city_delta, delta)

    averaged = {metric: round(value / max(1, len(targets) + len(spillovers))) for metric, value in city_delta.items()}
    _apply_city_delta(state, averaged)
    heat_delta = _adjust_heat(state, group, -1 if mitigated else 0)
    mode_text = "settled with conditions" if mitigated else "accepted for formal response"
    report = (
        f"{item.title} {mode_text}. Target group: {_group_label(group)}. "
        f"City delta: {_format_delta(averaged)}. {_population_report_fragment([districts[cid] for cid in targets])}"
    )
    return DecisionResult(
        True,
        action,
        item.item_id,
        report,
        averaged,
        targets + spillovers,
        district_deltas,
        item.status,
        stakeholder_delta={group: heat_delta} if heat_delta else {},
    )


def advance_turn(state: CityState, open_items: Iterable[DocketItem], districts: dict[str, DistrictProfile] | None = None) -> str:
    carried = 0
    expired = 0
    heated = 0
    local_grievances = 0
    for item in open_items:
        if item.status in ("open", "inspected"):
            template = TEMPLATES[item.template_id]
            item.stakeholder = item.stakeholder or template.stakeholder
            if _adjust_heat(state, item.stakeholder, template.ignore_heat):
                heated += 1
            if districts:
                for cid in item.target_cell_ids:
                    if cid in districts:
                        _apply_population_reaction(template, [districts[cid]], "ignore", False)
                        local_grievances += 1
            if item.carryover == "expire_or_return" and (item.turn + len(item.item_id)) % 2 == 0:
                item.status = "carried"
                carried += 1
            else:
                item.status = "expired"
                expired += 1
    population_delta = 0
    new_incidents = 0
    if districts:
        for profile in districts.values():
            population_delta += _advance_population_pressure(profile)
        new_incidents = _surface_new_incidents(state, districts.values())
    state.turn += 1
    state.ap = state.max_ap
    if state.turn in (3, 6):
        state.audit_stage += 1
    if state.turn > state.max_turns:
        state.status = "complete"
    heat_text = f" Stakeholder heat added to {heated} unresolved case(s)." if heated else ""
    grievance_text = f" Local grievance files updated for {local_grievances} unresolved target(s)." if local_grievances else ""
    population_text = f" Population drift {population_delta:+d}." if population_delta else ""
    incident_text = f" New civic incident file(s): {new_incidents}." if new_incidents else ""
    return f"Advanced turn. Carried {carried} item(s), expired {expired} item(s).{heat_text}{grievance_text}{population_text}{incident_text}"


def display_state_for_profile(profile: DistrictProfile) -> str:
    if profile.incident_state != "none":
        return "incident"
    if _top_dissatisfaction(profile)[1] >= DISSATISFACTION_AGGRIEVED_THRESHOLD:
        return "aggrieved"
    if profile.unrest >= 60 and profile.risk >= 55:
        return "strained"
    if profile.unrest >= 55:
        return "restless"
    if profile.risk >= 55:
        return "at_risk"
    if profile.prosperity >= 65:
        return "prosperous"
    if profile.culture >= 60:
        return "cultured"
    return "stable"


def scorecard(state: CityState) -> tuple[str, str]:
    score = state.prosperity + state.culture - state.unrest - state.risk + state.money // 3
    if score >= 70:
        grade = "PASS"
    elif score >= 40:
        grade = "CONDITIONAL"
    else:
        grade = "FAIL"
    return grade, f"Audit {grade}: score={score}; prosperity={state.prosperity}, unrest={state.unrest}, culture={state.culture}, risk={state.risk}, money={state.money}."


def heat_summary(state: CityState) -> str:
    hot = [(stakeholder, heat) for stakeholder, heat in state.stakeholder_heat.items() if heat > 0]
    if not hot:
        return "none"
    return ", ".join(f"{stakeholder.replace('_', ' ')} {heat}" for stakeholder, heat in sorted(hot, key=lambda pair: (-pair[1], pair[0]))[:3])


def feature_archetype_for_template(template_or_id: DocketTemplate | str) -> FeatureArchetype:
    template = TEMPLATES[template_or_id] if isinstance(template_or_id, str) else template_or_id
    archetype_id = template.spawn_archetype_id or template.template_id
    try:
        return FEATURE_ARCHETYPES[archetype_id]
    except KeyError as exc:
        raise KeyError(f"Template {template.template_id!r} references unknown feature archetype {archetype_id!r}.") from exc


def feature_metadata_for_template(template_or_id: DocketTemplate | str) -> dict[str, object]:
    archetype = feature_archetype_for_template(template_or_id)
    return {
        "archetype_id": archetype.archetype_id,
        "family": archetype.family,
        "service_type": archetype.service_type,
        "coverage_radius_m": archetype.coverage_radius_m,
        "capacity": archetype.capacity,
        "land_use": archetype.land_use,
        "allowed_district_types": list(archetype.allowed_district_types),
        "conflict_district_types": list(archetype.conflict_district_types),
        "incident_type": archetype.incident_type,
    }


def validate_feature_catalog() -> list[str]:
    errors: list[str] = []
    for archetype_id, archetype in FEATURE_ARCHETYPES.items():
        if archetype.archetype_id != archetype_id:
            errors.append(f"{archetype_id}: archetype_id mismatch")
        if archetype.family not in FEATURE_FAMILIES:
            errors.append(f"{archetype_id}: invalid family {archetype.family!r}")
        if archetype.geometry_type not in {"POINT", "LINE", "POLYGON"}:
            errors.append(f"{archetype_id}: invalid geometry {archetype.geometry_type!r}")
        if archetype.service_type and archetype.service_type not in SERVICE_TYPES:
            errors.append(f"{archetype_id}: invalid service type {archetype.service_type!r}")
    for template_id, template in TEMPLATES.items():
        if not template.spawn_archetype_id:
            errors.append(f"{template_id}: missing spawn_archetype_id")
        elif template.spawn_archetype_id not in FEATURE_ARCHETYPES:
            errors.append(f"{template_id}: unknown spawn archetype {template.spawn_archetype_id!r}")
        else:
            archetype = FEATURE_ARCHETYPES[template.spawn_archetype_id]
            if archetype.geometry_type != template.geometry_type:
                errors.append(f"{template_id}: archetype geometry {archetype.geometry_type!r} != template geometry {template.geometry_type!r}")
    return errors


def total_population(districts: Iterable[DistrictProfile] | dict[str, DistrictProfile]) -> int:
    profiles = districts.values() if isinstance(districts, dict) else districts
    return sum(max(0, int(profile.population)) for profile in profiles)


def population_city_summary(districts: Iterable[DistrictProfile] | dict[str, DistrictProfile]) -> str:
    profiles = list(districts.values() if isinstance(districts, dict) else districts)
    if not profiles:
        return "population unavailable"
    incident_count = sum(1 for profile in profiles if profile.incident_state != "none")
    aggrieved_count = sum(1 for profile in profiles if profile.incident_state == "none" and _top_dissatisfaction(profile)[1] >= DISSATISFACTION_AGGRIEVED_THRESHOLD)
    suffix = []
    if incident_count:
        suffix.append(f"{incident_count} incident")
    if aggrieved_count:
        suffix.append(f"{aggrieved_count} aggrieved")
    note = f"; {', '.join(suffix)}" if suffix else ""
    return f"Pop {total_population(profiles)}{note}"


def incident_summary(districts: Iterable[DistrictProfile] | dict[str, DistrictProfile]) -> str:
    profiles = list(districts.values() if isinstance(districts, dict) else districts)
    incidents = [
        f"{profile.cell_id} {_group_label(profile.incident_group)} {profile.incident_state}"
        for profile in profiles
        if profile.incident_state != "none" and profile.incident_group
    ]
    if not incidents:
        return "none"
    return ", ".join(incidents[:3])


def target_population_hint(item: DocketItem, target_profiles: Iterable[DistrictProfile]) -> str:
    profiles = list(target_profiles)
    if not profiles:
        return ""
    template = TEMPLATES[item.template_id]
    visible_groups = _top_presence_groups(profiles, limit=3)
    supporters = _present_template_groups(profiles, template.supporter_groups)
    concerned = _present_template_groups(profiles, template.concerned_groups)
    grievance_group, grievance_band = _top_dissatisfaction_for_profiles(profiles)
    parts = [f"Target census note: strongest public mix is {_join_group_labels(visible_groups)}."]
    if supporters:
        parts.append(f"Likely affirmative comments from {_join_group_labels(supporters)}.")
    if concerned:
        parts.append(f"Likely formal objections from {_join_group_labels(concerned)}.")
    if grievance_band >= DISSATISFACTION_AGGRIEVED_THRESHOLD:
        parts.append(f"Existing grievance file: {_group_label(grievance_group)} are {GRIEVANCE_BAND_LABELS[grievance_band]}.")
    return " ".join(parts)


def inspection_population_note(template: DocketTemplate, target_profiles: Iterable[DistrictProfile]) -> str:
    profiles = list(target_profiles)
    archetype = feature_archetype_for_template(template)
    if not profiles:
        interested = template.supporter_groups[:2] + template.concerned_groups[:2]
        if not interested:
            return "Census review awaits a selected district."
        return f"Census review: likely interested parties include {_join_group_labels(interested)}."
    supporter = _strongest_template_group(profiles, template.supporter_groups)
    objector = _strongest_template_group(profiles, template.concerned_groups)
    grievance_group, grievance_band = _top_dissatisfaction_for_profiles(profiles)
    avg_services = sum(profile.services for profile in profiles) / max(1, len(profiles))
    service_text = "service capacity appears absorbent" if avg_services >= 45 else "service capacity is already using careful verbs"
    parts = [f"Census review: {service_text}."]
    if archetype.service_type:
        avg_gap = sum(profile.service_gap.get(archetype.service_type, 0) for profile in profiles) / max(1, len(profiles))
        if avg_gap:
            parts.append(f"Coverage note: {archetype.service_type.replace('_', ' ')} gap remains on the worksheet.")
        else:
            parts.append(f"Coverage note: {archetype.service_type.replace('_', ' ')} fit is administratively plausible.")
    fit_note = _land_use_note(archetype, profiles)
    if fit_note:
        parts.append(fit_note)
    if supporter:
        parts.append(f"Strongest likely supporter: {_group_label(supporter)}.")
    if objector:
        parts.append(f"Strongest likely objector: {_group_label(objector)}.")
    if grievance_band:
        parts.append(f"Highest local grievance: {_group_label(grievance_group)} are {GRIEVANCE_BAND_LABELS[grievance_band]}.")
    return " ".join(parts)


def normalize_profile(profile: DistrictProfile) -> DistrictProfile:
    if not profile.land_use:
        profile.land_use = LAND_USE_BY_DISTRICT_TYPE.get(profile.district_type, "mixed_use")
    profile.zoning_overlay = profile.zoning_overlay or ""
    profile.population_mix = _normalize_bands(profile.population_mix, 3)
    if not any(profile.population_mix.values()):
        profile.population_mix = _normalize_bands(ARCHETYPE_BASE_MIX.get(profile.district_type, {}), 3)
    profile.dissatisfaction = _normalize_bands(profile.dissatisfaction, 4)
    for group, band in profile.population_mix.items():
        if band > 0 and group not in profile.dissatisfaction:
            profile.dissatisfaction[group] = 0
    profile.service_gap = _service_gap_for_profile(profile)
    _refresh_incident(profile)
    profile.public_profile = public_profile_for(profile)
    profile.display_state = display_state_for_profile(profile)
    return profile


def public_profile_for(profile: DistrictProfile) -> str:
    groups = _top_presence_groups([profile], limit=3)
    if not groups:
        return "Public profile: no census emphasis filed."
    return f"Public profile: {_join_group_labels(groups)} noted in current census binder."


def compact_group_bands(bands: dict[str, int]) -> dict[str, int]:
    return {group: int(value) for group, value in _normalize_bands(bands, 4).items() if value > 0}


def _unique_known(values: Iterable[str], districts: dict[str, DistrictProfile]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value in districts and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _initial_population_mix(district_type: str, rng: random.Random) -> dict[str, int]:
    mix = dict(ARCHETYPE_BASE_MIX.get(district_type, {}))
    spice_pool = [group for group in CITIZEN_GROUPS if group not in mix]
    for group in rng.sample(spice_pool, k=2):
        mix[group] = max(mix.get(group, 0), 1)
    if rng.random() < 0.35:
        group = rng.choice(tuple(mix))
        mix[group] = min(3, mix[group] + 1)
    return _normalize_bands(mix, 3)


def _initial_dissatisfaction(population_mix: dict[str, int], prosperity: int, unrest: int, risk: int, services: int) -> dict[str, int]:
    dissatisfaction = {group: 0 for group, band in population_mix.items() if band > 0}
    if unrest >= 40:
        _adjust_dissatisfaction_map(dissatisfaction, ("renters", "workers", "students"), 1)
    if risk >= 45:
        _adjust_dissatisfaction_map(dissatisfaction, ("families", "elders", "workers"), 1)
    if services < 25:
        _adjust_dissatisfaction_map(dissatisfaction, ("families", "commuters", "civil_servants"), 1)
    if prosperity < 30:
        _adjust_dissatisfaction_map(dissatisfaction, ("renters", "vendors", "workers"), 1)
    return _normalize_bands(dissatisfaction, 4)


def _normalize_bands(bands: dict[str, int] | None, maximum: int) -> dict[str, int]:
    out = {group: 0 for group in CITIZEN_GROUPS}
    for group, value in (bands or {}).items():
        if group not in out:
            continue
        out[group] = max(0, min(maximum, int(value or 0)))
    return out


def _apply_population_reaction(
    template: DocketTemplate,
    target_profiles: list[DistrictProfile],
    outcome: str,
    mitigated: bool,
) -> dict[str, dict[str, int]]:
    deltas: dict[str, dict[str, int]] = {}
    for profile in target_profiles:
        before_population = profile.population
        if outcome == "approve":
            _adjust_dissatisfaction(profile, template.supporter_groups, -1)
            _adjust_dissatisfaction(profile, template.concerned_groups, 1 if not mitigated else 0)
            _shift_mix(profile, template.growth_groups, 1)
            _shift_mix(profile, template.decline_groups, -1)
            profile.population = max(100, profile.population + _population_decision_delta(profile, template, mitigated))
        elif outcome == "failure":
            _adjust_dissatisfaction(profile, template.concerned_groups or template.supporter_groups, 2 if not mitigated else 1)
            _adjust_dissatisfaction(profile, template.supporter_groups, 1)
            _shift_mix(profile, template.growth_groups, -1)
            profile.population = max(100, profile.population - max(10, profile.population // 90))
        elif outcome == "deny":
            _adjust_dissatisfaction(profile, template.supporter_groups, 1)
            _adjust_dissatisfaction(profile, template.concerned_groups, -1)
        elif outcome == "ignore":
            _adjust_dissatisfaction(profile, template.supporter_groups or (template.stakeholder,), 1)
        normalize_profile(profile)
        population_delta = profile.population - before_population
        if population_delta:
            deltas[profile.cell_id] = {"population": population_delta}
        else:
            deltas[profile.cell_id] = {}
    return deltas


def _population_decision_delta(profile: DistrictProfile, template: DocketTemplate, mitigated: bool) -> int:
    if not template.growth_groups:
        return 0
    base = max(8, profile.population // 100)
    if profile.services < 25 or profile.risk > 60:
        base = max(4, base // 2)
    if mitigated:
        base = max(4, round(base * 0.75))
    return base


def _advance_population_pressure(profile: DistrictProfile) -> int:
    before = profile.population
    delta = 0
    if profile.prosperity >= 60 and profile.risk <= 45 and profile.unrest <= 45:
        delta += max(6, profile.population // 120)
        _shift_mix(profile, PRESSURE_DRIFT_GROUPS.get(profile.district_type, ()), 1)
    if profile.risk >= 60 or profile.unrest >= 60 or profile.incident_state != "none":
        delta -= max(6, profile.population // 100)
        group, _band = _top_presence_group(profile)
        _shift_mix(profile, (group,), -1)
    if profile.services < 25 and profile.population > 1200:
        _adjust_dissatisfaction(profile, ("families", "commuters", "renters"), 1)
    profile.population = max(100, profile.population + delta)
    normalize_profile(profile)
    return profile.population - before


def _surface_new_incidents(state: CityState, profiles: Iterable[DistrictProfile]) -> int:
    surfaced = 0
    for profile in profiles:
        before = profile.incident_state
        normalize_profile(profile)
        if before == "none" and profile.incident_state != "none":
            surfaced += 1
    if surfaced:
        _apply_city_delta(state, {"unrest": surfaced})
    return surfaced


def _refresh_incident(profile: DistrictProfile) -> None:
    group, band = _top_dissatisfaction(profile)
    if band >= DISSATISFACTION_INCIDENT_THRESHOLD:
        profile.incident_group = group
        profile.incident_state = INCIDENT_STATE_BY_GROUP.get(group, "protest")
    else:
        profile.incident_group = ""
        profile.incident_state = "none"


def _adjust_dissatisfaction(profile: DistrictProfile, groups: Iterable[str], amount: int) -> None:
    profile.dissatisfaction = _normalize_bands(profile.dissatisfaction, 4)
    for group in groups:
        if group not in CITIZEN_GROUPS:
            continue
        current = profile.dissatisfaction.get(group, 0)
        if profile.population_mix.get(group, 0) == 0 and amount < 0:
            continue
        profile.dissatisfaction[group] = max(0, min(4, current + amount))


def _adjust_dissatisfaction_map(dissatisfaction: dict[str, int], groups: Iterable[str], amount: int) -> None:
    for group in groups:
        if group in dissatisfaction:
            dissatisfaction[group] = max(0, min(4, dissatisfaction.get(group, 0) + amount))


def _shift_mix(profile: DistrictProfile, groups: Iterable[str], amount: int) -> None:
    profile.population_mix = _normalize_bands(profile.population_mix, 3)
    for group in groups:
        if group not in CITIZEN_GROUPS:
            continue
        profile.population_mix[group] = max(0, min(3, profile.population_mix.get(group, 0) + amount))
        if profile.population_mix[group] > 0:
            profile.dissatisfaction.setdefault(group, 0)


def _top_presence_group(profile: DistrictProfile) -> tuple[str, int]:
    profile.population_mix = _normalize_bands(profile.population_mix, 3)
    return sorted(profile.population_mix.items(), key=lambda pair: (-pair[1], pair[0]))[0]


def _top_presence_groups(profiles: list[DistrictProfile], limit: int = 3) -> tuple[str, ...]:
    totals = {group: 0 for group in CITIZEN_GROUPS}
    for profile in profiles:
        for group, band in _normalize_bands(profile.population_mix, 3).items():
            totals[group] += band
    groups = [group for group, value in sorted(totals.items(), key=lambda pair: (-pair[1], pair[0])) if value > 0]
    return tuple(groups[:limit])


def _top_dissatisfaction(profile: DistrictProfile) -> tuple[str, int]:
    profile.dissatisfaction = _normalize_bands(profile.dissatisfaction, 4)
    return sorted(profile.dissatisfaction.items(), key=lambda pair: (-pair[1], pair[0]))[0]


def _top_dissatisfaction_for_profiles(profiles: list[DistrictProfile]) -> tuple[str, int]:
    totals = {group: 0 for group in CITIZEN_GROUPS}
    for profile in profiles:
        for group, band in _normalize_bands(profile.dissatisfaction, 4).items():
            totals[group] += band
    return sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))[0]


def _present_template_groups(profiles: list[DistrictProfile], groups: Iterable[str]) -> tuple[str, ...]:
    present = []
    for group in groups:
        if group in CITIZEN_GROUPS and any(profile.population_mix.get(group, 0) > 0 for profile in profiles):
            present.append(group)
    return tuple(present[:3])


def _strongest_template_group(profiles: list[DistrictProfile], groups: Iterable[str]) -> str:
    scores = []
    for group in groups:
        if group not in CITIZEN_GROUPS:
            continue
        scores.append((sum(profile.population_mix.get(group, 0) for profile in profiles), group))
    scores = [score for score in scores if score[0] > 0]
    if not scores:
        return ""
    return sorted(scores, key=lambda pair: (-pair[0], pair[1]))[0][1]


def _group_label(group: str) -> str:
    return GROUP_LABELS.get(group, group.replace("_", " "))


def _join_group_labels(groups: Iterable[str]) -> str:
    labels = [_group_label(group) for group in groups if group]
    if not labels:
        return "no filed group"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _population_report_fragment(target_profiles: list[DistrictProfile]) -> str:
    if not target_profiles:
        return "No local population file was attached."
    group, band = _top_dissatisfaction_for_profiles(target_profiles)
    if band >= DISSATISFACTION_INCIDENT_THRESHOLD:
        return f"Population file: {_group_label(group)} grievance is now incident-ready."
    if band >= DISSATISFACTION_AGGRIEVED_THRESHOLD:
        return f"Population file: {_group_label(group)} grievance is aggrieved but still in forms."
    groups = _top_presence_groups(target_profiles, limit=2)
    return f"Population file: {_join_group_labels(groups)} remain the principal census note."


def _service_gap_for_profile(profile: DistrictProfile) -> dict[str, int]:
    services = max(0, min(100, int(profile.services)))
    gaps: dict[str, int] = {}
    if profile.population_mix.get("families", 0) >= 2:
        gaps["child_services"] = max(0, 45 - services)
    if profile.risk >= 45 or profile.district_type in ("industrial", "civic"):
        gaps["fire_response"] = max(0, 50 - services)
    if profile.risk >= 35 or profile.district_type in ("industrial", "mercantile"):
        gaps["utilities"] = max(0, 45 - services)
    if profile.population_mix.get("commuters", 0) >= 2:
        gaps["mobility"] = max(0, 40 - services)
    if profile.population_mix.get("artists", 0) >= 2 or profile.population_mix.get("students", 0) >= 2:
        gaps["culture_access"] = max(0, 35 - services)
    if profile.district_type == "natural" or profile.risk >= 55:
        gaps["green_buffer"] = max(0, 40 - services)
    return {service: gap for service, gap in sorted(gaps.items()) if gap > 0}


def _service_coverage_effect(archetype: FeatureArchetype, profile: DistrictProfile, role: str) -> dict[str, int]:
    if not archetype.coverage_effects:
        return {}
    delta: dict[str, int] = {}
    for metric, value in archetype.coverage_effects.items():
        if role == "spillover":
            if value > 0:
                value = max(0, round(value / 2))
            elif value < 0:
                value = min(0, round(value / 2))
        if value:
            delta[metric] = value
    if archetype.service_type:
        gap = profile.service_gap.get(archetype.service_type, 0)
        if gap > 0 and archetype.capacity > 0 and role == "target":
            delta["services"] = delta.get("services", 0) + min(archetype.capacity, max(1, gap // 10))
    return delta


def _land_use_adjusted_effects(delta: dict[str, int], profile: DistrictProfile, archetype: FeatureArchetype) -> dict[str, int]:
    adjusted = dict(delta)
    if profile.district_type in archetype.allowed_district_types:
        if archetype.service_type:
            adjusted["services"] = adjusted.get("services", 0) + 1
        if adjusted.get("unrest", 0) > 0:
            adjusted["unrest"] = max(0, adjusted["unrest"] - 1)
        if adjusted.get("risk", 0) > 0:
            adjusted["risk"] = max(0, adjusted["risk"] - 1)
    if profile.district_type in archetype.conflict_district_types:
        adjusted["unrest"] = adjusted.get("unrest", 0) + 2
        adjusted["risk"] = adjusted.get("risk", 0) + 1
        if adjusted.get("prosperity", 0) > 1:
            adjusted["prosperity"] -= 1
    if profile.zoning_overlay == "protected_reserve" and archetype.family in ("business", "land_use", "infrastructure"):
        adjusted["unrest"] = adjusted.get("unrest", 0) + 1
        adjusted["risk"] = adjusted.get("risk", 0) + 1
    return adjusted


def _land_use_note(archetype: FeatureArchetype, profiles: list[DistrictProfile]) -> str:
    district_types = {profile.district_type for profile in profiles}
    if district_types & set(archetype.conflict_district_types):
        return f"Land-use note: {archetype.label} conflicts with at least one selected district archetype."
    if district_types & set(archetype.allowed_district_types):
        return f"Land-use note: {archetype.label} fits the selected district pattern."
    if archetype.land_use:
        return f"Land-use note: proposed overlay is {archetype.land_use.replace('_', ' ')}."
    return ""


def _apply_land_use_change(profile: DistrictProfile, archetype: FeatureArchetype) -> None:
    if archetype.family == "land_use":
        profile.zoning_overlay = archetype.land_use
    elif archetype.family in ("natural_resource", "infrastructure") and archetype.land_use:
        profile.zoning_overlay = archetype.land_use


def _district_adjusted_effects(base: dict[str, int], district_type: str, category: str) -> dict[str, int]:
    delta = dict(base)
    if district_type == "residential" and category in ("education", "residential"):
        delta["culture"] = delta.get("culture", 0) + 1
        delta["risk"] = delta.get("risk", 0) - 1
    elif district_type == "residential" and category in ("transit", "utility", "development"):
        delta["unrest"] = delta.get("unrest", 0) + 1
    elif district_type == "mercantile" and category in ("business", "transit", "culture"):
        delta["prosperity"] = delta.get("prosperity", 0) + 3
        delta["unrest"] = delta.get("unrest", 0) - 1
    elif district_type == "industrial" and category in ("utility", "department", "development"):
        delta["prosperity"] = delta.get("prosperity", 0) + 2
        delta["risk"] = delta.get("risk", 0) + 1
    elif district_type == "civic" and category in ("department", "education", "culture", "event"):
        delta["culture"] = delta.get("culture", 0) + 2
        delta["risk"] = delta.get("risk", 0) - 1
    elif district_type == "academic" and category in ("education", "culture", "event", "land"):
        delta["culture"] = delta.get("culture", 0) + 3
        delta["risk"] = delta.get("risk", 0) - 1
    elif district_type == "natural" and category == "land":
        delta["culture"] = delta.get("culture", 0) + 3
        delta["risk"] = delta.get("risk", 0) - 2
    elif district_type == "natural" and category in ("development", "utility", "transit", "business"):
        delta["unrest"] = delta.get("unrest", 0) + 2
        delta["risk"] = delta.get("risk", 0) + 1
    return delta


def _mitigate(delta: dict[str, int]) -> dict[str, int]:
    out = {}
    for metric, value in delta.items():
        if metric in ("unrest", "risk") and value > 0:
            out[metric] = max(0, value - 2)
        elif metric in ("prosperity", "culture") and value > 0:
            out[metric] = max(0, value - 1)
        else:
            out[metric] = value
    return out


def _context_side_effect(template: DocketTemplate, target_profiles: list[DistrictProfile], rng: random.Random, mitigated: bool) -> dict[str, int]:
    if mitigated:
        threshold = 0.12
    else:
        threshold = 0.28
    avg_unrest = sum(p.unrest for p in target_profiles) / max(1, len(target_profiles))
    avg_risk = sum(p.risk for p in target_profiles) / max(1, len(target_profiles))
    if template.category in ("event", "development", "residential", "transit", "utility", "business") and (avg_unrest > 50 or rng.random() < threshold):
        return {"unrest": 2, "risk": 1}
    if template.category in ("education", "department", "land") and avg_risk > 45:
        return {"risk": -2, "unrest": -1}
    return {}


def _approval_failure_effect(
    template: DocketTemplate,
    target_profiles: list[DistrictProfile],
    risk_band: str,
    rng: random.Random,
    mitigated: bool,
) -> dict[str, int]:
    if not template.failure_effects:
        return {}
    chance = _failure_chance(template, target_profiles, risk_band, mitigated)
    if rng.random() >= chance:
        return {}
    delta = dict(template.failure_effects)
    if mitigated:
        delta = _mitigate(delta)
    return delta


def _failure_chance(template: DocketTemplate, target_profiles: list[DistrictProfile], risk_band: str, mitigated: bool) -> float:
    avg_services = sum(p.services for p in target_profiles) / max(1, len(target_profiles))
    avg_risk = sum(p.risk for p in target_profiles) / max(1, len(target_profiles))
    chance = template.failure_base_chance
    chance += {"low": -0.12, "medium": 0.02, "high": 0.25, "unknown": 0.05}.get(risk_band, 0.05)
    if avg_services < 25:
        chance += 0.16
    elif avg_services > 55:
        chance -= 0.08
    if avg_risk > 55:
        chance += 0.10
    district_types = {profile.district_type for profile in target_profiles}
    archetype = feature_archetype_for_template(template)
    if district_types & set(template.good_fit_types):
        chance -= 0.10
    if district_types & set(template.bad_fit_types):
        chance += 0.14
    if district_types & set(archetype.allowed_district_types):
        chance -= 0.05
    if district_types & set(archetype.conflict_district_types):
        chance += 0.08
    if archetype.service_type:
        avg_gap = sum(profile.service_gap.get(archetype.service_type, 0) for profile in target_profiles) / max(1, len(target_profiles))
        if avg_gap >= 20:
            chance += 0.08
        elif avg_gap == 0 and avg_services >= 45:
            chance -= 0.04
    if any(profile.zoning_overlay == "protected_reserve" for profile in target_profiles) and archetype.family in ("business", "land_use", "infrastructure"):
        chance += 0.10
    if mitigated:
        chance -= 0.20
    if risk_band == "high" and avg_services < 20 and avg_risk > 75 and district_types & set(template.bad_fit_types):
        chance = 1.0
    return max(0.03, min(1.0, chance))


def _apply_profile_delta(profile: DistrictProfile, delta: dict[str, int]) -> None:
    for metric, value in delta.items():
        if metric in DISTRICT_METRICS:
            setattr(profile, metric, _clamp(getattr(profile, metric) + value))
    normalize_profile(profile)


def _apply_city_delta(state: CityState, delta: dict[str, int]) -> None:
    for metric, value in delta.items():
        if metric in CORE_METRICS:
            setattr(state, metric, _clamp(getattr(state, metric) + value))


def _merge_delta(target: dict[str, int], delta: dict[str, int]) -> None:
    for metric, value in delta.items():
        target[metric] = target.get(metric, 0) + value


def _adjust_heat(state: CityState, stakeholder: str, amount: int) -> int:
    if not stakeholder or amount == 0:
        return 0
    before = state.stakeholder_heat.get(stakeholder, 0)
    after = max(0, before + amount)
    if after:
        state.stakeholder_heat[stakeholder] = after
    else:
        state.stakeholder_heat.pop(stakeholder, None)
    return after - before


def _blocked(action: str, item_id: str, report: str) -> DecisionResult:
    return DecisionResult(False, action, item_id, report, command_status="error")


def _format_delta(delta: dict[str, int]) -> str:
    parts = []
    for metric in DISTRICT_METRICS:
        value = delta.get(metric, 0)
        if value:
            parts.append(f"{metric} {value:+d}")
    return ", ".join(parts) if parts else "no net citywide metric change"


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))
