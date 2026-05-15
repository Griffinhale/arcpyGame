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
NETWORK_TYPES = ("utilities", "mobility", "fire_response", "green_buffer")
HAZARD_TYPES = ("pollution", "flood", "fire", "noise", "heat", "ecology")

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
MAINTENANCE_TEMPLATE_ID = "feature_maintenance_order"
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
    network_type: str = ""
    network_strength: int = 0
    hazard_effects: dict[str, int] = field(default_factory=dict)
    mitigation_effects: dict[str, int] = field(default_factory=dict)
    housing_effects: dict[str, int] = field(default_factory=dict)
    starts_chain_id: str = ""
    allowed_district_types: tuple[str, ...] = ()
    conflict_district_types: tuple[str, ...] = ()
    incident_type: str = ""
    display_state: str = "active"


@dataclass
class FeatureInstance:
    feature_id: str
    archetype_id: str
    family: str = ""
    service_type: str = ""
    network_type: str = ""
    target_cell_ids: list[str] = field(default_factory=list)
    capacity: int = 0
    intensity: int = 1
    status: str = "active"
    turn_created: int = 0
    expires_turn: int = -1
    project_id: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    item_id: str = ""
    template_id: str = ""
    owner_group: str = ""
    condition: int = 100
    maintenance_due_turn: int = -1
    last_maintained_turn: int = 0
    display_state: str = "active"
    chain_step_id: str = ""
    state_json: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class HazardRule:
    hazard_type: str
    affected_groups: tuple[str, ...]
    risk_threshold: int = 2
    unrest_threshold: int = 3
    decay: int = 1
    source_effects: dict[str, int] = field(default_factory=dict)
    mitigation_service_types: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectStepTemplate:
    step_id: str
    title: str
    template_id: str
    due_after: int = 1
    next_step_id: str = ""
    failure_step_id: str = ""
    status_on_approval: str = "advanced"
    status_on_failure: str = "failed"
    stakeholder: str = ""
    payload_effects: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectChainTemplate:
    chain_id: str
    label: str
    initial_step_id: str
    steps: tuple[ProjectStepTemplate, ...]


@dataclass
class ProjectRecord:
    project_id: str
    chain_template_id: str
    current_step_id: str
    status: str = "active"
    turn_started: int = 1
    due_turn: int = 1
    stakeholder: str = ""
    target_cell_ids: list[str] = field(default_factory=list)
    payload: dict[str, object] = field(default_factory=dict)
    last_report: str = ""


@dataclass(frozen=True)
class ScenarioRule:
    scenario_id: str
    label: str
    starting_city_effects: dict[str, int] = field(default_factory=dict)
    starting_district_effects: dict[str, int] = field(default_factory=dict)
    docket_priority: tuple[str, ...] = ()
    score_weights: dict[str, int] = field(default_factory=dict)
    audit_priorities: tuple[str, ...] = ()
    district_biases: dict[str, int] = field(default_factory=dict)
    hazard_bias: dict[str, int] = field(default_factory=dict)
    housing_bias: dict[str, int] = field(default_factory=dict)


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
    housing_effects: dict[str, int] = field(default_factory=dict)
    hazard_effects: dict[str, int] = field(default_factory=dict)
    starts_chain_id: str = ""
    project_step_id: str = ""
    scenario_tags: tuple[str, ...] = ()
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
    adjacent_cell_ids: list[str] = field(default_factory=list)
    network_access: dict[str, int] = field(default_factory=dict)
    hazards: dict[str, int] = field(default_factory=dict)
    housing_capacity: int = 0
    affordability: int = 0
    vacancy_rate: int = 0
    displacement: dict[str, int] = field(default_factory=dict)


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
    scenario_id: str = "default"
    stakeholder_heat: dict[str, int] = field(default_factory=dict)
    last_revenue: int = 0
    last_upkeep: int = 0
    last_net: int = 0
    maintenance_backlog: int = 0
    stakeholder_memory: dict[str, int] = field(default_factory=dict)


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
    project_id: str = ""
    chain_step_id: str = ""
    priority: int = 0
    due_turn: int = 0
    subject_feature_id: str = ""
    case_json: dict[str, object] = field(default_factory=dict)


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
    feature_updates: dict[str, dict[str, object]] = field(default_factory=dict)


ActiveFeature = FeatureInstance


@dataclass(frozen=True)
class FeatureOperatingRule:
    archetype_id: str
    revenue_per_turn: int = 0
    upkeep_per_turn: int = 0
    lifespan_turns: int = 0
    decay_per_turn: int = 0
    maintenance_interval: int = 0
    maintenance_cost: int = 0
    repair_amount: int = 40
    degrade_threshold: int = 35
    failure_threshold: int = 0
    failure_effects: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class InspectionRule:
    rule_id: str
    evidence_codes: tuple[str, ...]
    violation_codes: tuple[str, ...] = ()
    deadline_turns: int = 2


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    label: str
    severity: str
    source: str
    note: str = ""


@dataclass(frozen=True)
class ViolationRecord:
    violation_id: str
    code: str
    severity: str
    deadline_turn: int
    status: str = "open"
    compliance_outcome: str = "pending"
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class StakeholderProfile:
    stakeholder_id: str
    influence: int = 2
    patience: int = 2
    interests: tuple[str, ...] = ()
    allies: tuple[str, ...] = ()
    rivals: tuple[str, ...] = ()
    escalation_threshold: int = STAKEHOLDER_HEAT_THRESHOLD
    cooldown_turns: int = 1
    followup_template_id: str = ENFORCEMENT_TEMPLATE_ID


@dataclass(frozen=True)
class AuditFinding:
    finding_id: str
    severity: str
    source: str
    message: str
    score_delta: int = 0


@dataclass(frozen=True)
class AuditResult:
    grade: str
    score: int
    findings: tuple[AuditFinding, ...]
    report: str


@dataclass
class TurnAdvanceResult:
    report: str
    city_delta: dict[str, int] = field(default_factory=dict)
    district_deltas: dict[str, dict[str, int]] = field(default_factory=dict)
    feature_updates: dict[str, dict[str, object]] = field(default_factory=dict)
    generated_followups: list[str] = field(default_factory=list)
    revenue: int = 0
    upkeep: int = 0
    net: int = 0
    audit: AuditResult | None = None


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
    "bus_priority_link": DocketTemplate(
        "bus_priority_link",
        "Bus Priority Link",
        "transit",
        "LINE",
        {"prosperity": 3, "risk": -1, "unrest": 1},
        {"prosperity": 1, "risk": -1},
        money_cost=18,
        mitigation_cost=6,
        preview="Adds a bus-priority segment; curb access objections are likely but mobility math is favorable.",
        inspect_hint="Transit staff can explain the signal priority but not the diagram colors.",
        target_rule="Select exactly two districts for link endpoints.",
        stakeholder="transit_authority",
        failure_mode="curb-management dispute",
        failure_effects={"unrest": 2, "prosperity": -1},
        failure_base_chance=0.16,
        good_fit_types=("mercantile", "civic", "academic"),
        bad_fit_types=("natural",),
        supporter_groups=("commuters", "workers", "students"),
        concerned_groups=("homeowners", "vendors"),
        growth_groups=("commuters", "workers"),
        contact_name="Signal Priority Clerk Asa Lane",
        spawn_archetype_id="bus_priority_link",
        scenario_tags=("port_boom",),
    ),
    "water_main_loop": DocketTemplate(
        "water_main_loop",
        "Water Main Loop",
        "utility",
        "LINE",
        {"risk": -5, "prosperity": 1, "unrest": 1},
        {"risk": -2},
        money_cost=24,
        mitigation_cost=8,
        preview="Loops water service between districts; it lowers flood and fire fragility if the trenching behaves.",
        inspect_hint="Hydraulic notes are clean, and every clean note has a page two.",
        target_rule="Select exactly two districts for the loop endpoints.",
        stakeholder="utility_board",
        failure_mode="valve coordination miss",
        failure_effects={"risk": 4, "unrest": 2},
        failure_base_chance=0.18,
        good_fit_types=("industrial", "civic", "residential"),
        bad_fit_types=("natural",),
        supporter_groups=("families", "workers", "civil_servants"),
        concerned_groups=("commuters", "homeowners"),
        growth_groups=("workers",),
        contact_name="Loop Engineer Mara Gauge",
        spawn_archetype_id="water_main_loop",
        scenario_tags=("port_boom",),
    ),
    "green_buffer_reserve": DocketTemplate(
        "green_buffer_reserve",
        "Green Buffer Reserve",
        "land",
        "POLYGON",
        {"culture": 4, "risk": -4, "prosperity": -1},
        {"culture": 1, "risk": -1},
        money_cost=14,
        mitigation_cost=5,
        preview="Creates a planted buffer that absorbs heat, noise, and ecological pressure.",
        inspect_hint="Planting plan is plausible; maintenance plan is written in future tense.",
        target_rule="Select one or more districts for the reserve boundary.",
        stakeholder="conservation_trust",
        failure_mode="maintenance shortfall",
        failure_effects={"risk": 2, "unrest": 1, "culture": -1},
        failure_base_chance=0.14,
        good_fit_types=("natural", "residential", "academic"),
        bad_fit_types=("industrial",),
        supporter_groups=("conservationists", "families", "elders", "artists"),
        concerned_groups=("developers", "workers"),
        growth_groups=("conservationists", "artists"),
        decline_groups=("developers",),
        contact_name="Buffer Steward Nela Canopy",
        spawn_archetype_id="green_buffer_reserve",
        scenario_tags=("garden_city",),
    ),
    "inspection_order": DocketTemplate(
        "inspection_order",
        "Inspection Order",
        "compliance",
        "POINT",
        {"risk": -3, "unrest": 1},
        {"risk": -1},
        money_cost=8,
        mitigation_cost=4,
        preview="Orders a compliance inspection; pollution, fire, and noise risks can drop after paperwork becomes physical.",
        inspect_hint="The inspector is available, which is a rare and meaningful sentence.",
        target_rule="Select exactly one district for the inspection order.",
        stakeholder="compliance_office",
        failure_mode="missed inspection window",
        failure_effects={"risk": 2, "unrest": 1},
        failure_base_chance=0.12,
        supporter_groups=("families", "elders", "civil_servants"),
        concerned_groups=("vendors", "developers", "workers"),
        contact_name="Inspector Sol Form",
        spawn_archetype_id="inspection_order",
    ),
    "affordable_infill_rezoning": DocketTemplate(
        "affordable_infill_rezoning",
        "Affordable Infill Rezoning",
        "development",
        "POLYGON",
        {"prosperity": 3, "unrest": 2, "risk": 1, "culture": 1},
        {"prosperity": 1, "unrest": 1},
        money_cost=18,
        mitigation_cost=9,
        preview="Starts an affordable infill buildout; capacity arrives only after construction, inspection, and occupancy.",
        inspect_hint="The covenant packet is legible, which makes everyone suspicious in a useful way.",
        target_rule="Select one or more districts to rezone for affordable infill.",
        stakeholder="housing_authority",
        denial_heat=2,
        failure_mode="zoning appeal",
        failure_effects={"unrest": 4, "risk": 1, "prosperity": -1},
        failure_base_chance=0.20,
        housing_effects={"affordability": 4},
        starts_chain_id="affordable_infill_buildout",
        project_step_id="rezoning",
        good_fit_types=("residential", "mercantile"),
        bad_fit_types=("natural", "industrial"),
        supporter_groups=("renters", "families", "workers", "developers"),
        concerned_groups=("homeowners", "commuters"),
        growth_groups=("renters", "families", "workers"),
        decline_groups=("homeowners",),
        contact_name="Housing Planner Mina Ledger",
        spawn_archetype_id="affordable_infill_rezoning",
        scenario_tags=("housing_mandate",),
    ),
    "infill_construction_site": DocketTemplate(
        "infill_construction_site",
        "Infill Construction Mobilization",
        "development",
        "POINT",
        {"prosperity": 2, "unrest": 2, "risk": 2},
        {"unrest": 1, "risk": 1},
        money_cost=16,
        mitigation_cost=8,
        expires_after=2,
        preview="Mobilizes the approved infill site; temporary noise and fire exposure enter the ledger.",
        inspect_hint="Construction schedule is complete except for the part involving weather and subcontractors.",
        target_rule="Select exactly one district inside the approved infill project.",
        stakeholder="housing_authority",
        failure_mode="construction safety violation",
        failure_effects={"risk": 5, "unrest": 2, "prosperity": -1},
        failure_base_chance=0.24,
        hazard_effects={"noise": 1, "fire": 1},
        project_step_id="construction",
        supporter_groups=("developers", "workers", "renters"),
        concerned_groups=("elders", "homeowners", "families"),
        growth_groups=("workers", "developers"),
        contact_name="Site Coordinator Pavi Brace",
        spawn_archetype_id="construction_site",
        scenario_tags=("housing_mandate",),
    ),
    "infill_inspection_order": DocketTemplate(
        "infill_inspection_order",
        "Infill Final Inspection",
        "compliance",
        "POINT",
        {"risk": -4, "unrest": -1},
        {"risk": -1},
        money_cost=9,
        mitigation_cost=5,
        preview="Runs the final inspection that clears or stalls the infill project.",
        inspect_hint="The checklist has boxes, and several boxes have opinions.",
        target_rule="Select exactly one district containing the infill project.",
        stakeholder="compliance_office",
        failure_mode="failed inspection",
        failure_effects={"risk": 4, "unrest": 3, "prosperity": -1},
        failure_base_chance=0.22,
        project_step_id="inspection",
        supporter_groups=("families", "renters", "civil_servants"),
        concerned_groups=("developers", "workers"),
        contact_name="Final Inspector Theo Stamp",
        spawn_archetype_id="inspection_order",
        scenario_tags=("housing_mandate",),
    ),
    "occupancy_certificate": DocketTemplate(
        "occupancy_certificate",
        "Occupancy Certificate",
        "compliance",
        "POINT",
        {"prosperity": 2, "culture": 1, "risk": -1},
        {"prosperity": 1},
        money_cost=7,
        mitigation_cost=4,
        preview="Certifies occupancy; housing capacity and population become real enough to complain about services.",
        inspect_hint="Addressing is complete, and that is more dramatic than expected.",
        target_rule="Select exactly one district receiving occupancy.",
        stakeholder="housing_authority",
        failure_mode="delayed occupancy",
        failure_effects={"unrest": 2, "risk": 1, "prosperity": -1},
        failure_base_chance=0.12,
        housing_effects={"housing_capacity": 420, "population": 180, "affordability": 6},
        project_step_id="occupancy",
        supporter_groups=("renters", "families", "workers"),
        concerned_groups=("commuters", "homeowners"),
        growth_groups=("renters", "families", "workers"),
        contact_name="Occupancy Clerk Neve Key",
        spawn_archetype_id="occupancy_certificate",
        scenario_tags=("housing_mandate",),
    ),
    "vendor_sanitation_complaint": DocketTemplate(
        "vendor_sanitation_complaint",
        "Vendor Sanitation Complaint",
        "incident",
        "POINT",
        {"unrest": -1, "risk": -2, "prosperity": -1},
        {"unrest": -1},
        money_cost=7,
        mitigation_cost=5,
        preview="A vendor-market nuisance file has matured into a sanitation complaint.",
        inspect_hint="Complaint photos show queues, wrappers, and one very organized clipboard.",
        target_rule="Select exactly one district hosting the vendor market.",
        stakeholder="public_health",
        denial_heat=2,
        ignore_heat=2,
        failure_mode="complaint escalation",
        failure_effects={"unrest": 3, "risk": 2},
        failure_base_chance=0.18,
        project_step_id="vendor_complaint",
        is_incident=True,
        supporter_groups=("families", "elders", "civil_servants"),
        concerned_groups=("vendors", "artists", "students"),
        contact_name="Sanitation Intake Lead Ora Carton",
        spawn_archetype_id="vendor_sanitation_complaint",
    ),
}

TEMPLATES[MAINTENANCE_TEMPLATE_ID] = DocketTemplate(
    MAINTENANCE_TEMPLATE_ID,
    "Feature Maintenance Order",
    "maintenance",
    "POINT",
    {"risk": -1, "unrest": -1},
    {},
    money_cost=6,
    mitigation_cost=4,
    preview="An active support feature is due for maintenance before condition becomes an audit finding.",
    inspect_hint="The maintenance ledger is concise, which is how it signals danger.",
    target_rule="Select the affected district or process the referenced support feature.",
    stakeholder="maintenance_office",
    denial_heat=1,
    ignore_heat=1,
    failure_mode="deferred maintenance",
    failure_effects={"risk": 2, "unrest": 1},
    failure_base_chance=0.08,
    is_enforcement=True,
    supporter_groups=("civil_servants", "families", "workers"),
    concerned_groups=("developers", "vendors"),
    contact_name="Maintenance Clerk Sera Wrench",
    spawn_archetype_id="compliance_case",
)

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
        network_type="mobility",
        network_strength=2,
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
        network_type="utilities",
        network_strength=3,
        mitigation_effects={"flood": 1, "fire": 1},
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
        network_type="green_buffer",
        network_strength=2,
        mitigation_effects={"heat": 1, "noise": 1, "ecology": 1},
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
        network_type="green_buffer",
        network_strength=1,
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
        hazard_effects={"noise": 1, "pollution": 1},
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
        network_type="fire_response",
        network_strength=5,
        mitigation_effects={"fire": 2},
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
    "bus_priority_link": FeatureArchetype(
        "bus_priority_link",
        "Bus Priority Link",
        "infrastructure",
        "LINE",
        service_type="mobility",
        coverage_radius_m=150,
        capacity=3,
        land_use="bus_priority",
        coverage_effects={"prosperity": 1, "services": 1},
        network_type="mobility",
        network_strength=3,
        allowed_district_types=("mercantile", "civic", "academic", "industrial"),
        conflict_district_types=("natural",),
    ),
    "water_main_loop": FeatureArchetype(
        "water_main_loop",
        "Water Main Loop",
        "infrastructure",
        "LINE",
        service_type="utilities",
        coverage_radius_m=150,
        capacity=3,
        land_use="water_loop",
        coverage_effects={"risk": -2, "services": 3},
        network_type="utilities",
        network_strength=3,
        mitigation_effects={"flood": 1, "fire": 1},
        allowed_district_types=("industrial", "civic", "residential", "mercantile"),
        conflict_district_types=("natural",),
    ),
    "green_buffer_reserve": FeatureArchetype(
        "green_buffer_reserve",
        "Green Buffer Reserve",
        "natural_resource",
        "POLYGON",
        service_type="green_buffer",
        coverage_radius_m=120,
        capacity=3,
        land_use="green_buffer",
        coverage_effects={"culture": 1, "risk": -2, "services": 1},
        network_type="green_buffer",
        network_strength=3,
        mitigation_effects={"heat": 2, "noise": 1, "ecology": 2},
        allowed_district_types=("natural", "residential", "academic"),
        conflict_district_types=("industrial",),
    ),
    "inspection_order": FeatureArchetype(
        "inspection_order",
        "Inspection Order",
        "compliance",
        "POINT",
        coverage_radius_m=75,
        capacity=1,
        land_use="inspection_order",
        coverage_effects={"risk": -1, "unrest": 1},
        mitigation_effects={"pollution": 1, "fire": 1, "noise": 1},
        incident_type="inspection",
        display_state="case",
    ),
    "affordable_infill_rezoning": FeatureArchetype(
        "affordable_infill_rezoning",
        "Affordable Infill Rezoning",
        "land_use",
        "POLYGON",
        coverage_radius_m=100,
        capacity=1,
        land_use="affordable_infill",
        coverage_effects={"prosperity": 1, "unrest": 1},
        housing_effects={"affordability": 4},
        starts_chain_id="affordable_infill_buildout",
        allowed_district_types=("residential", "mercantile"),
        conflict_district_types=("natural", "industrial"),
        display_state="overlay",
    ),
    "construction_site": FeatureArchetype(
        "construction_site",
        "Construction Site",
        "land_use",
        "POINT",
        coverage_radius_m=90,
        capacity=1,
        land_use="construction_site",
        coverage_effects={"prosperity": 1, "unrest": 1, "risk": 1},
        hazard_effects={"noise": 1, "fire": 1},
        allowed_district_types=("residential", "mercantile", "industrial"),
        conflict_district_types=("natural",),
        incident_type="construction",
        display_state="temporary",
    ),
    "occupancy_certificate": FeatureArchetype(
        "occupancy_certificate",
        "Occupancy Certificate",
        "compliance",
        "POINT",
        service_type="utilities",
        coverage_radius_m=80,
        capacity=1,
        land_use="occupied_infill",
        coverage_effects={"prosperity": 1, "services": -1},
        housing_effects={"housing_capacity": 420, "population": 180, "affordability": 6},
        allowed_district_types=("residential", "mercantile"),
        conflict_district_types=("natural",),
        display_state="active",
    ),
    "vendor_sanitation_complaint": FeatureArchetype(
        "vendor_sanitation_complaint",
        "Vendor Sanitation Complaint",
        "incident",
        "POINT",
        coverage_radius_m=75,
        capacity=1,
        land_use="sanitation_complaint",
        coverage_effects={"unrest": -1, "risk": -1},
        hazard_effects={"pollution": 1, "noise": 1},
        incident_type="sanitation",
        display_state="incident",
    ),
}


HAZARD_RULES: dict[str, HazardRule] = {
    "pollution": HazardRule(
        "pollution",
        ("families", "elders", "workers", "renters", "conservationists"),
        source_effects={"industrial": 1, "business": 1},
        mitigation_service_types={"utilities": 1},
    ),
    "flood": HazardRule(
        "flood",
        ("families", "elders", "homeowners", "workers"),
        source_effects={"natural": 1},
        mitigation_service_types={"utilities": 1, "green_buffer": 1},
    ),
    "fire": HazardRule(
        "fire",
        ("families", "elders", "workers", "civil_servants"),
        source_effects={"industrial": 1, "land_use": 1},
        mitigation_service_types={"fire_response": 2, "utilities": 1},
    ),
    "noise": HazardRule(
        "noise",
        ("elders", "homeowners", "students", "artists", "families"),
        risk_threshold=3,
        source_effects={"event": 1, "business": 1, "land_use": 1},
        mitigation_service_types={"green_buffer": 1},
    ),
    "heat": HazardRule(
        "heat",
        ("elders", "families", "workers", "renters"),
        source_effects={"industrial": 1},
        mitigation_service_types={"green_buffer": 2},
    ),
    "ecology": HazardRule(
        "ecology",
        ("conservationists", "artists", "elders", "families"),
        source_effects={"development": 1, "industrial": 1},
        mitigation_service_types={"green_buffer": 2},
    ),
}


PROJECT_CHAINS: dict[str, ProjectChainTemplate] = {
    "affordable_infill_buildout": ProjectChainTemplate(
        "affordable_infill_buildout",
        "Affordable Infill Buildout",
        "rezoning",
        (
            ProjectStepTemplate("rezoning", "Rezoning Approval", "affordable_infill_rezoning", due_after=1, next_step_id="construction", stakeholder="housing_authority"),
            ProjectStepTemplate("construction", "Construction Mobilization", "infill_construction_site", due_after=1, next_step_id="inspection", failure_step_id="inspection", stakeholder="housing_authority"),
            ProjectStepTemplate("inspection", "Final Inspection", "infill_inspection_order", due_after=1, next_step_id="occupancy", status_on_failure="delayed", stakeholder="compliance_office"),
            ProjectStepTemplate("occupancy", "Occupancy Certificate", "occupancy_certificate", due_after=1, status_on_approval="settled", stakeholder="housing_authority"),
        ),
    ),
    "vendor_compliance_chain": ProjectChainTemplate(
        "vendor_compliance_chain",
        "Vendor Complaint Escalation",
        "vendor_complaint",
        (
            ProjectStepTemplate("vendor_complaint", "Sanitation Complaint", "vendor_sanitation_complaint", due_after=1, next_step_id="vendor_enforcement", stakeholder="public_health"),
            ProjectStepTemplate("vendor_enforcement", "Vendor Enforcement", ENFORCEMENT_TEMPLATE_ID, due_after=1, status_on_approval="settled", stakeholder="public_health"),
        ),
    ),
}


SCENARIO_RULES: dict[str, ScenarioRule] = {
    "default": ScenarioRule(
        "default",
        "Default Audit",
        score_weights={"prosperity": 1, "culture": 1, "unrest": -1, "risk": -1, "money": 1},
        audit_priorities=("prosperity", "culture", "unrest", "risk"),
    ),
    "housing_mandate": ScenarioRule(
        "housing_mandate",
        "Housing Mandate",
        starting_city_effects={"prosperity": -2, "unrest": 3},
        starting_district_effects={"housing_capacity": 180, "affordability": -4},
        docket_priority=("affordable_infill_rezoning", "water_main_loop", "child_development_park_annex"),
        score_weights={"prosperity": 1, "culture": 1, "unrest": -1, "risk": -1, "money": 1, "housing_capacity": 1, "affordability": 2, "vacancy_rate": 1, "displacement": -3, "renter_dissatisfaction": -2},
        audit_priorities=("capacity", "affordability", "vacancy", "displacement", "renters"),
        housing_bias={"housing_capacity": 180, "affordability": -4},
    ),
    "port_boom": ScenarioRule(
        "port_boom",
        "Port Boom",
        starting_city_effects={"prosperity": 5, "risk": 3},
        starting_district_effects={"prosperity": 2},
        docket_priority=("water_main_loop", "bus_priority_link", "utility_expansion_trench"),
        score_weights={"prosperity": 2, "culture": 1, "unrest": -1, "risk": -1, "money": 1, "mobility": 1, "pollution": -3, "ecology": -2},
        audit_priorities=("prosperity", "mobility", "pollution", "ecology"),
        hazard_bias={"pollution": 1, "ecology": 1},
    ),
    "garden_city": ScenarioRule(
        "garden_city",
        "Garden City",
        starting_city_effects={"culture": 3, "prosperity": -1},
        docket_priority=("green_buffer_reserve", "natural_reserve_conversion", "child_development_park_annex"),
        score_weights={"prosperity": 1, "culture": 2, "unrest": -1, "risk": -1, "money": 1, "green_buffer": 2, "heat": -2, "ecology": -2, "displacement": -2},
        audit_priorities=("green buffer", "heat", "ecology", "displacement"),
        hazard_bias={"heat": -1, "ecology": -1},
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

FEATURE_OPERATING_RULES: dict[str, FeatureOperatingRule] = {
    "connector_corridor": FeatureOperatingRule("connector_corridor", revenue_per_turn=1, upkeep_per_turn=3, decay_per_turn=4, maintenance_interval=3, maintenance_cost=9, repair_amount=45, failure_effects={"risk": 4, "unrest": 2}),
    "licensed_procession": FeatureOperatingRule("licensed_procession", revenue_per_turn=2, upkeep_per_turn=1, lifespan_turns=1, decay_per_turn=100, failure_effects={"unrest": 2, "risk": 1}),
    "utility_trench": FeatureOperatingRule("utility_trench", upkeep_per_turn=4, decay_per_turn=5, maintenance_interval=3, maintenance_cost=10, repair_amount=50, failure_effects={"risk": 5, "unrest": 2}),
    "protected_reserve": FeatureOperatingRule("protected_reserve", upkeep_per_turn=2, decay_per_turn=2, maintenance_interval=4, maintenance_cost=6, repair_amount=40, failure_effects={"risk": 3, "culture": -2}),
    "mixed_use_overlay": FeatureOperatingRule("mixed_use_overlay", revenue_per_turn=5, upkeep_per_turn=1, decay_per_turn=1, maintenance_interval=4, maintenance_cost=7, repair_amount=35, failure_effects={"prosperity": -3, "unrest": 2}),
    "child_service_annex": FeatureOperatingRule("child_service_annex", upkeep_per_turn=4, decay_per_turn=3, maintenance_interval=3, maintenance_cost=8, repair_amount=55, failure_effects={"risk": 4, "unrest": 2, "culture": -2}),
    "vendor_market": FeatureOperatingRule("vendor_market", revenue_per_turn=4, upkeep_per_turn=1, decay_per_turn=5, maintenance_interval=2, maintenance_cost=5, repair_amount=35, failure_effects={"unrest": 3, "risk": 2, "prosperity": -1}),
    "renovation_site": FeatureOperatingRule("renovation_site", revenue_per_turn=3, lifespan_turns=3, decay_per_turn=15, failure_effects={"risk": 3, "unrest": 1}),
    "fire_coverage_area": FeatureOperatingRule("fire_coverage_area", upkeep_per_turn=5, decay_per_turn=3, maintenance_interval=3, maintenance_cost=12, repair_amount=55, failure_effects={"risk": 6, "unrest": 2}),
    "museum_grant_site": FeatureOperatingRule("museum_grant_site", revenue_per_turn=2, upkeep_per_turn=2, decay_per_turn=2, maintenance_interval=4, maintenance_cost=7, repair_amount=40, failure_effects={"culture": -3, "unrest": 2}),
    "compliance_case": FeatureOperatingRule("compliance_case", upkeep_per_turn=1, lifespan_turns=2, decay_per_turn=20, failure_effects={"unrest": 2}),
    "civic_incident_marker": FeatureOperatingRule("civic_incident_marker", upkeep_per_turn=1, lifespan_turns=2, decay_per_turn=20, failure_effects={"unrest": 2, "risk": 1}),
    "bus_priority_link": FeatureOperatingRule("bus_priority_link", revenue_per_turn=1, upkeep_per_turn=2, decay_per_turn=4, maintenance_interval=3, maintenance_cost=8, repair_amount=45, failure_effects={"unrest": 2, "prosperity": -1}),
    "water_main_loop": FeatureOperatingRule("water_main_loop", upkeep_per_turn=4, decay_per_turn=4, maintenance_interval=3, maintenance_cost=10, repair_amount=50, failure_effects={"risk": 5, "unrest": 1}),
    "green_buffer_reserve": FeatureOperatingRule("green_buffer_reserve", upkeep_per_turn=1, decay_per_turn=2, maintenance_interval=4, maintenance_cost=5, repair_amount=35, failure_effects={"risk": 3, "culture": -1}),
    "affordable_infill_rezoning": FeatureOperatingRule("affordable_infill_rezoning", revenue_per_turn=3, upkeep_per_turn=2, decay_per_turn=2, maintenance_interval=4, maintenance_cost=7, repair_amount=35, failure_effects={"unrest": 3, "prosperity": -2}),
    "construction_site": FeatureOperatingRule("construction_site", revenue_per_turn=1, upkeep_per_turn=1, lifespan_turns=2, decay_per_turn=25, failure_effects={"risk": 3, "unrest": 2}),
    "inspection_order": FeatureOperatingRule("inspection_order", upkeep_per_turn=1, lifespan_turns=1, decay_per_turn=100, failure_effects={"risk": 2, "unrest": 1}),
    "occupancy_certificate": FeatureOperatingRule("occupancy_certificate", revenue_per_turn=4, decay_per_turn=1, maintenance_interval=5, maintenance_cost=6, repair_amount=30, failure_effects={"unrest": 2, "risk": 1}),
    "vendor_sanitation_complaint": FeatureOperatingRule("vendor_sanitation_complaint", upkeep_per_turn=1, lifespan_turns=2, decay_per_turn=30, failure_effects={"unrest": 3, "risk": 2}),
}

VIOLATION_CODES = {
    "paperwork_gap": {"label": "Paperwork Gap", "severity": "watch"},
    "service_gap": {"label": "Service Capacity Gap", "severity": "warning"},
    "unsafe_work": {"label": "Unsafe Work Condition", "severity": "warning"},
    "public_nuisance": {"label": "Public Nuisance", "severity": "watch"},
    "maintenance_overdue": {"label": "Maintenance Overdue", "severity": "warning"},
}

INSPECTION_RULES: dict[str, InspectionRule] = {
    "default": InspectionRule("default", ("paperwork_gap", "service_gap"), ("paperwork_gap",), deadline_turns=2),
    "contractor_renovation_waiver": InspectionRule("contractor_renovation_waiver", ("paperwork_gap", "unsafe_work", "public_nuisance"), ("unsafe_work",), deadline_turns=2),
    "street_vendor_compact": InspectionRule("street_vendor_compact", ("public_nuisance", "service_gap", "paperwork_gap"), ("public_nuisance",), deadline_turns=1),
    "utility_expansion_trench": InspectionRule("utility_expansion_trench", ("service_gap", "unsafe_work"), ("unsafe_work",), deadline_turns=2),
    "fire_budget_escalation": InspectionRule("fire_budget_escalation", ("service_gap", "paperwork_gap"), ("service_gap",), deadline_turns=2),
    MAINTENANCE_TEMPLATE_ID: InspectionRule(MAINTENANCE_TEMPLATE_ID, ("maintenance_overdue", "service_gap"), ("maintenance_overdue",), deadline_turns=1),
}

STAKEHOLDERS: dict[str, StakeholderProfile] = {
    "general_public": StakeholderProfile("general_public", influence=2, patience=2, interests=("unrest", "risk")),
    "transit_authority": StakeholderProfile("transit_authority", influence=3, patience=3, interests=("mobility", "prosperity"), allies=("commuters",), rivals=("homeowners",)),
    "celebrants": StakeholderProfile("celebrants", influence=2, patience=1, interests=("culture",), allies=("artists", "vendors")),
    "utility_board": StakeholderProfile("utility_board", influence=4, patience=2, interests=("utilities", "risk"), allies=("civil_servants",)),
    "conservation_trust": StakeholderProfile("conservation_trust", influence=3, patience=3, interests=("green_buffer", "culture"), allies=("conservationists",), rivals=("developers",)),
    "developers": StakeholderProfile("developers", influence=4, patience=1, interests=("prosperity", "land_use"), allies=("contractors",), rivals=("conservationists", "renters")),
    "families": StakeholderProfile("families", influence=3, patience=2, interests=("child_services", "risk"), allies=("elders",), followup_template_id=CIVIC_INCIDENT_TEMPLATE_ID),
    "vendors": StakeholderProfile("vendors", influence=3, patience=1, interests=("prosperity", "culture_access"), allies=("artists",), rivals=("homeowners",)),
    "contractors": StakeholderProfile("contractors", influence=3, patience=1, interests=("prosperity", "inspection"), allies=("developers",)),
    "fire_department": StakeholderProfile("fire_department", influence=5, patience=2, interests=("risk", "fire_response"), allies=("civil_servants",), escalation_threshold=3),
    "arts_council": StakeholderProfile("arts_council", influence=2, patience=3, interests=("culture",), allies=("artists", "students")),
    "maintenance_office": StakeholderProfile("maintenance_office", influence=3, patience=2, interests=("risk", "services"), allies=("civil_servants",)),
    "public_health": StakeholderProfile("public_health", influence=4, patience=2, interests=("risk", "vendors"), allies=("elders", "families"), followup_template_id=CIVIC_INCIDENT_TEMPLATE_ID),
    "compliance_office": StakeholderProfile("compliance_office", influence=4, patience=2, interests=("inspection", "risk")),
    "housing_authority": StakeholderProfile("housing_authority", influence=4, patience=2, interests=("housing", "affordability"), allies=("renters", "families")),
    "renters": StakeholderProfile("renters", influence=3, patience=1, interests=("housing", "affordability"), allies=("workers", "students"), rivals=("homeowners",), followup_template_id=CIVIC_INCIDENT_TEMPLATE_ID),
    "homeowners": StakeholderProfile("homeowners", influence=3, patience=2, interests=("risk", "unrest"), rivals=("developers", "renters"), followup_template_id=CIVIC_INCIDENT_TEMPLATE_ID),
    "civil_servants": StakeholderProfile("civil_servants", influence=3, patience=2, interests=("services", "risk"), followup_template_id=CIVIC_INCIDENT_TEMPLATE_ID),
    "workers": StakeholderProfile("workers", influence=3, patience=1, interests=("prosperity", "risk"), allies=("commuters",), followup_template_id=CIVIC_INCIDENT_TEMPLATE_ID),
}

AUDIT_THRESHOLDS = {
    "service_gap_warning": 25,
    "service_gap_critical": 40,
    "feature_condition_warning": 35,
    "feature_condition_critical": 10,
}


def _scenario_score(
    state: CityState,
    profiles: list[DistrictProfile],
    features: list[FeatureInstance],
    scenario: ScenarioRule,
) -> int:
    if scenario.scenario_id == "default":
        return state.prosperity + state.culture - state.unrest - state.risk + state.money // 3
    weights = scenario.score_weights or SCENARIO_RULES["default"].score_weights
    score = 0
    metric_values = {
        "prosperity": state.prosperity,
        "culture": state.culture,
        "unrest": state.unrest,
        "risk": state.risk,
        "money": state.money // 3,
    }
    if profiles:
        metric_values["housing_capacity"] = sum(profile.housing_capacity for profile in profiles) // max(1, len(profiles) * 100)
        metric_values["affordability"] = sum(profile.affordability for profile in profiles) // max(1, len(profiles))
        metric_values["vacancy_rate"] = sum(profile.vacancy_rate for profile in profiles) // max(1, len(profiles))
        metric_values["displacement"] = sum(max(profile.displacement.values(), default=0) for profile in profiles)
        metric_values["renter_dissatisfaction"] = sum(profile.dissatisfaction.get("renters", 0) for profile in profiles)
        for service in SERVICE_TYPES:
            metric_values[service] = sum(profile.network_access.get(service, 0) for profile in profiles)
        for hazard in HAZARD_TYPES:
            metric_values[hazard] = sum(profile.hazards.get(hazard, 0) for profile in profiles)
    for metric, weight in weights.items():
        score += metric_values.get(metric, 0) * int(weight)
    return score


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
    assign_grid_adjacency(profiles, rows, cols)
    for profile in profiles:
        normalize_profile(profile)
    return profiles


def generate_docket(
    turn: int,
    seed: int = 2026,
    count: int = 3,
    state: CityState | None = None,
    districts: dict[str, DistrictProfile] | None = None,
    projects: Iterable[ProjectRecord] | dict[str, ProjectRecord] | None = None,
    active_features: Iterable[FeatureInstance] | None = None,
) -> list[DocketItem]:
    scenario = SCENARIO_RULES.get(state.scenario_id if state else "default", SCENARIO_RULES["default"])
    chosen = _scenario_ordered_templates(turn, scenario)
    if len(chosen) < count:
        rng = random.Random(seed * 1000 + turn)
        pool = [template_id for template_id in DEMO_TEMPLATE_IDS if template_id not in chosen]
        chosen.extend(rng.sample(pool, min(count - len(chosen), len(pool))))

    items: list[DocketItem] = []
    for due in _project_due_items(turn, projects):
        if len(items) >= count:
            break
        items.append(due)

    if active_features:
        followup = _maintenance_followup_item(turn, active_features)
        if followup and len(items) < count:
            items.append(followup)

    if districts:
        followup = _incident_followup_item(turn, districts)
        if followup and len(items) < count:
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


def _scenario_ordered_templates(turn: int, scenario: ScenarioRule) -> list[str]:
    chosen: list[str] = []
    for template_id in scenario.docket_priority:
        if template_id in TEMPLATES and template_id not in chosen:
            chosen.append(template_id)
    for template_id in DEMO_SEQUENCE.get(turn, ()):
        if template_id not in chosen:
            chosen.append(template_id)
    return chosen


def _project_due_items(turn: int, projects: Iterable[ProjectRecord] | dict[str, ProjectRecord] | None) -> list[DocketItem]:
    if not projects:
        return []
    records = projects.values() if isinstance(projects, dict) else projects
    due: list[tuple[int, str, ProjectRecord, ProjectStepTemplate]] = []
    for project in records:
        if project.status not in ("active", "delayed", "overdue"):
            continue
        if project.due_turn > turn:
            continue
        step = project_step_template(project.chain_template_id, project.current_step_id)
        if step:
            due.append((project.due_turn, project.project_id, project, step))
    out: list[DocketItem] = []
    for idx, (_due_turn, _project_id, project, step) in enumerate(sorted(due, key=lambda row: (row[0], row[1])), start=1):
        item = _make_docket_item(turn, idx, step.template_id, stakeholder=step.stakeholder or project.stakeholder, origin_item_id=f"project:{project.project_id}")
        item.project_id = project.project_id
        item.chain_step_id = step.step_id
        item.target_cell_ids = list(project.target_cell_ids)
        if project.due_turn < turn:
            item.preview_text = f"{item.preview_text} Project step is overdue from turn {project.due_turn}."
        else:
            item.preview_text = f"{item.preview_text} Project step due this turn."
        out.append(item)
    return out


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
        chain_step_id=template.project_step_id,
    )


def _heat_followup_item(turn: int, state: CityState) -> DocketItem | None:
    hot = []
    for stakeholder, heat in state.stakeholder_heat.items():
        profile = _stakeholder_profile(stakeholder)
        if heat >= profile.escalation_threshold and turn >= state.stakeholder_memory.get(stakeholder, 0):
            hot.append((stakeholder, heat, _stakeholder_escalation_score(stakeholder, heat)))
    if not hot:
        return None
    stakeholder, _heat, _score = sorted(hot, key=lambda row: (-row[2], row[0]))[0]
    template_id = _stakeholder_profile(stakeholder).followup_template_id
    if template_id not in TEMPLATES:
        template_id = ENFORCEMENT_TEMPLATE_ID
    return _make_docket_item(turn, 1, template_id, stakeholder=stakeholder, origin_item_id="stakeholder_heat")


def _maintenance_followup_item(turn: int, active_features: Iterable[FeatureInstance]) -> DocketItem | None:
    candidates = []
    for feature in active_features:
        normalize_feature_instance(feature, turn)
        if feature.status in ("maintenance_due", "degraded", "failed"):
            candidates.append((feature.condition, feature.feature_id, feature))
    if not candidates:
        return None
    _condition, _feature_id, feature = sorted(candidates, key=lambda row: (row[0], row[1]))[0]
    item = _make_docket_item(turn, 1, MAINTENANCE_TEMPLATE_ID, stakeholder=feature.owner_group or "maintenance_office", origin_item_id=f"feature:{feature.feature_id}")
    item.title = f"Maintenance Order: {feature.archetype_id.replace('_', ' ').title()}"
    item.subject_feature_id = feature.feature_id
    item.target_cell_ids = list(feature.target_cell_ids)
    item.priority = 3 if feature.status == "failed" else 2 if feature.status == "degraded" else 1
    item.due_turn = turn + 1
    item.case_json = {
        "maintenance": {
            "feature_id": feature.feature_id,
            "archetype_id": feature.archetype_id,
            "condition": feature.condition,
            "status": feature.status,
        }
    }
    item.preview_text = f"{item.preview_text} Feature {feature.feature_id} is {feature.status} at condition {feature.condition}."
    return item


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
    profiles = list(target_profiles or ())
    item.inspected = True
    item.stakeholder = item.stakeholder or template.stakeholder
    item.target_rule = item.target_rule or template.target_rule
    item.risk_band = rng.choice(["low", "medium", "medium", "high"])
    inspection_case = inspection_case_for_item(item, profiles, seed=seed, fallback_risk_band=item.risk_band)
    item.risk_band = str(inspection_case["risk_band"])
    item.case_json = dict(item.case_json or {})
    item.case_json["inspection"] = inspection_case
    failure_text = f" Failure mode on file: {template.failure_mode}." if template.failure_mode else ""
    population_text = inspection_population_note(template, profiles)
    evidence_text = _inspection_summary_text(inspection_case)
    item.preview_text = (
        f"{template.preview} Inspection: {item.risk_band.upper()} side-effect risk. "
        f"{template.inspect_hint}{failure_text} {population_text} {evidence_text}"
    ).strip()
    return item


def inspection_case_for_item(
    item: DocketItem,
    target_profiles: Iterable[DistrictProfile],
    seed: int = 2026,
    fallback_risk_band: str = "medium",
) -> dict[str, object]:
    template = TEMPLATES[item.template_id]
    rule = INSPECTION_RULES.get(template.template_id, INSPECTION_RULES["default"])
    profiles = list(target_profiles)
    rng = random.Random(f"{seed}:{item.item_id}:evidence")
    avg_risk = sum(profile.risk for profile in profiles) / max(1, len(profiles))
    avg_services = sum(profile.services for profile in profiles) / max(1, len(profiles))
    max_grievance = max((_top_dissatisfaction(profile)[1] for profile in profiles), default=0)

    evidence: list[EvidenceRecord] = []
    for code in rule.evidence_codes:
        severity = "watch"
        note = "Routine file check."
        if code == "service_gap":
            if avg_services < 25:
                severity = "critical"
                note = "Service capacity is already below the operating floor."
            elif avg_services < 40:
                severity = "warning"
                note = "Service capacity is thin enough to affect compliance."
            else:
                note = "Service capacity can absorb the request."
        elif code == "unsafe_work":
            if avg_risk >= 65:
                severity = "critical"
                note = "Site risk is high enough to require follow-through."
            elif avg_risk >= 45:
                severity = "warning"
                note = "Site risk is visible in the inspection worksheet."
            else:
                note = "No acute site safety concern is visible."
        elif code == "public_nuisance":
            if max_grievance >= DISSATISFACTION_INCIDENT_THRESHOLD:
                severity = "critical"
                note = "Local grievance is already incident-ready."
            elif max_grievance >= DISSATISFACTION_AGGRIEVED_THRESHOLD:
                severity = "warning"
                note = "Local grievance is aggrieved."
            elif rng.random() < 0.35:
                severity = "watch"
                note = "Public comment is noisy but not decisive."
        elif code == "maintenance_overdue":
            severity = "warning"
            note = "Referenced support feature has an open maintenance condition."
        elif rng.random() < 0.2:
            severity = "warning"
            note = "The file is internally consistent after one heroic assumption."
        label = VIOLATION_CODES.get(code, {}).get("label", code.replace("_", " ").title())
        evidence.append(EvidenceRecord(f"{item.item_id}:{code}", label, severity, code, note))

    severity_score = sum({"watch": 1, "warning": 2, "critical": 4}.get(record.severity, 1) for record in evidence)
    if any(record.severity == "critical" for record in evidence) or severity_score >= 6:
        risk_band = "high"
    elif any(record.severity == "warning" for record in evidence) or severity_score >= 3:
        risk_band = "medium"
    else:
        risk_band = fallback_risk_band if fallback_risk_band in {"low", "medium", "high"} else "low"

    violations: list[ViolationRecord] = []
    if risk_band in {"medium", "high"}:
        severity = "critical" if risk_band == "high" else "warning"
        deadline = item.turn + (1 if severity == "critical" else rule.deadline_turns)
        for code in rule.violation_codes:
            evidence_ids = tuple(record.evidence_id for record in evidence if record.source == code)
            violations.append(
                ViolationRecord(
                    f"{item.item_id}:{code}",
                    code,
                    severity,
                    deadline,
                    evidence_ids=evidence_ids,
                )
            )

    return {
        "rule_id": rule.rule_id,
        "risk_band": risk_band,
        "evidence": [record.__dict__ for record in evidence],
        "violations": [record.__dict__ | {"evidence_ids": list(record.evidence_ids)} for record in violations],
    }


def _inspection_summary_text(inspection_case: dict[str, object]) -> str:
    evidence = inspection_case.get("evidence", [])
    violations = inspection_case.get("violations", [])
    if not evidence:
        return ""
    worst = "watch"
    for record in evidence:
        if isinstance(record, dict) and record.get("severity") == "critical":
            worst = "critical"
            break
        if isinstance(record, dict) and record.get("severity") == "warning":
            worst = "warning"
    violation_text = f" Violations opened: {len(violations)}." if violations else ""
    return f"Evidence filed: {len(evidence)} item(s), highest severity {worst}.{violation_text}"


def resolve_decision(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile],
    action: str,
    target_cell_ids: Iterable[str],
    spillover_cell_ids: Iterable[str] = (),
    seed: int = 2026,
    mitigated: bool = False,
    active_features: Iterable[FeatureInstance] | None = None,
    projects: dict[str, ProjectRecord] | None = None,
) -> DecisionResult:
    action_key = action.lower().strip()
    targets = _unique_known(target_cell_ids, districts)
    spillovers = [cid for cid in _unique_known(spillover_cell_ids, districts) if cid not in targets]
    template = TEMPLATES[item.template_id]
    archetype = feature_archetype_for_template(template)
    item.stakeholder = item.stakeholder or template.stakeholder
    item.target_rule = item.target_rule or template.target_rule

    if template.template_id == MAINTENANCE_TEMPLATE_ID:
        return _resolve_maintenance_decision(
            state,
            item,
            action,
            action_key,
            targets,
            template,
            mitigated,
            active_features,
        )

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
            projects,
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
            projects,
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
        project_note = ""
        if projects and item.project_id:
            project = advance_project_from_item(projects, item, state, approved=False)
            if project:
                project_note = f" Project {project.project_id} delayed."
        report = (
            f"Denied {item.title}. Project risk avoided; {item.stakeholder.replace('_', ' ')} heat "
            f"{heat_delta:+d} entered the public record.{project_note} {_population_report_fragment([districts[cid] for cid in targets])}"
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
    if not failure_triggered:
        long_term_deltas = apply_template_long_term_effects(template, [districts[cid] for cid in targets], mitigated)
        for cid, delta in long_term_deltas.items():
            _merge_delta(district_deltas.setdefault(cid, {}), delta)
    surfaced = _surface_new_incidents(state, [districts[cid] for cid in targets])

    averaged = {metric: round(value / max(1, len(targets) + len(spillovers))) for metric, value in city_delta.items()}
    _apply_city_delta(state, averaged)
    if surfaced:
        averaged["unrest"] = averaged.get("unrest", 0) + surfaced
    affected = targets + spillovers
    _settle_item_violations(item, mitigated)
    mitigation_text = " with mitigation" if mitigated else ""
    failure_text = ""
    if failure_triggered:
        failure_text = f" Outcome failed: {template.failure_mode}; corrective delta {_format_delta(failure_delta)}."
    project_text = ""
    if projects is not None and not failure_triggered:
        if template.starts_chain_id:
            project = start_project_from_approval(state, item, template, targets)
            if project:
                projects[project.project_id] = project
                project_text = f" Project {project.project_id} opened; next step {project.current_step_id} due turn {project.due_turn}."
        elif item.project_id:
            project = advance_project_from_item(projects, item, state, approved=True, failed=False)
            if project:
                project_text = f" Project {project.project_id} status {project.status}; current step {project.current_step_id}."
    elif projects is not None and failure_triggered and item.project_id:
        project = advance_project_from_item(projects, item, state, approved=True, failed=True)
        if project:
            project_text = f" Project {project.project_id} status {project.status}."
    report = (
        f"Approved {item.title}{mitigation_text}. Affected {len(affected)} district(s): "
        f"{', '.join(affected)}. City delta: {_format_delta(averaged)}.{failure_text} "
        f"{_population_report_fragment([districts[cid] for cid in targets])}{project_text}"
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


def _resolve_maintenance_decision(
    state: CityState,
    item: DocketItem,
    action: str,
    action_key: str,
    targets: list[str],
    template: DocketTemplate,
    mitigated: bool,
    active_features: Iterable[FeatureInstance] | None,
) -> DecisionResult:
    features = list(active_features or ())
    feature = next((candidate for candidate in features if candidate.feature_id == item.subject_feature_id), None)
    if action_key == "inspect":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Maintenance inspection requires 1 AP.")
        state.ap -= 1
        item.inspected = True
        item.status = "inspected"
        condition = feature.condition if feature else 0
        item.risk_band = "high" if condition <= 10 else "medium" if condition < 35 else "low"
        item.case_json = dict(item.case_json or {})
        item.case_json["inspection"] = inspection_case_for_item(item, (), fallback_risk_band=item.risk_band)
        item.preview_text = f"{template.preview} Inspection: referenced feature condition {condition}."
        return DecisionResult(True, action, item.item_id, f"Inspection completed for {item.title}: {item.preview_text}", affected_cell_ids=targets, item_status=item.status)

    if feature is None:
        return _blocked(action, item.item_id, "Maintenance order requires a referenced active feature.")
    rule = operating_rule_for_feature(feature)
    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Deferring maintenance requires 1 AP.")
        state.ap -= 1
        item.status = "deferred"
        feature.status = "maintenance_due"
        feature.display_state = "maintenance_due"
        heat_delta = _adjust_heat(state, feature.owner_group or "maintenance_office", template.denial_heat)
        delta = {"risk": 1}
        _apply_city_delta(state, delta)
        return DecisionResult(
            True,
            action,
            item.item_id,
            f"Deferred {item.title}. Maintenance remains open; heat {heat_delta:+d}.",
            delta,
            targets,
            item_status=item.status,
            stakeholder_delta={feature.owner_group or "maintenance_office": heat_delta},
            feature_updates={feature.feature_id: feature_update_payload(feature)},
        )

    if action_key not in ("approve", "approve_mitigated"):
        return _blocked(action, item.item_id, f"Unknown decision action {action!r}.")
    total_money = max(template.money_cost, rule.maintenance_cost) + (template.mitigation_cost if mitigated else 0)
    if state.ap < template.ap_cost:
        return _blocked(action, item.item_id, f"Maintenance requires {template.ap_cost} AP.")
    if state.money < total_money:
        return _blocked(action, item.item_id, f"Maintenance requires ${total_money}.")

    state.ap -= template.ap_cost
    state.money -= total_money
    repair = rule.repair_amount + (20 if mitigated else 0)
    feature.condition = max(0, min(100, feature.condition + repair))
    feature.last_maintained_turn = state.turn
    if rule.maintenance_interval:
        feature.maintenance_due_turn = state.turn + rule.maintenance_interval + (1 if mitigated else 0)
    feature.status = "active" if feature.condition > rule.degrade_threshold else "degraded"
    feature.display_state = feature.status
    feature.state_json = dict(feature.state_json or {})
    feature.state_json.pop("failure_applied", None)
    item.status = "settled" if mitigated else "maintained"
    _settle_item_violations(item, mitigated)
    delta = _mitigate(template.base_effects) if mitigated else dict(template.base_effects)
    _apply_city_delta(state, delta)
    return DecisionResult(
        True,
        action,
        item.item_id,
        f"Maintained {item.title}. Feature condition is now {feature.condition}; next due turn {feature.maintenance_due_turn}.",
        delta,
        targets,
        item_status=item.status,
        feature_updates={feature.feature_id: feature_update_payload(feature)},
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
    projects: dict[str, ProjectRecord] | None = None,
) -> DecisionResult:
    if action_key == "deny":
        if state.ap < 1:
            return _blocked(action, item.item_id, "Deferring enforcement requires 1 AP.")
        state.ap -= 1
        item.status = "deferred"
        delta = {"unrest": 2, "risk": 1}
        _apply_city_delta(state, delta)
        heat_delta = _adjust_heat(state, item.stakeholder, template.denial_heat)
        project_note = ""
        if projects and item.project_id:
            project = advance_project_from_item(projects, item, state, approved=False)
            if project:
                project_note = f" Project {project.project_id} delayed."
        report = (
            f"Deferred enforcement for {item.title}. The unpermitted condition remains useful to someone; "
            f"{item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}.{project_note}"
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
    _settle_item_violations(item, mitigated)
    project_note = ""
    if projects and item.project_id:
        project = advance_project_from_item(projects, item, state, approved=True, failed=False)
        if project:
            project_note = f" Project {project.project_id} status {project.status}."
    if mitigated:
        report = (
            f"Settled {item.title} through a retroactive permit and compliance schedule. "
            f"City delta: {_format_delta(averaged)}. {item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}.{project_note}"
        )
    else:
        report = (
            f"Enforced {item.title}. The record is clearer and several people are louder. "
            f"City delta: {_format_delta(averaged)}. {item.stakeholder.replace('_', ' ')} heat {heat_delta:+d}.{project_note}"
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
    projects: dict[str, ProjectRecord] | None = None,
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
        project_note = ""
        if projects and item.project_id:
            project = advance_project_from_item(projects, item, state, approved=False)
            if project:
                project_note = f" Project {project.project_id} delayed."
        report = (
            f"Deferred {item.title}. The incident remains local in form and citywide in tone. "
            f"City delta: {_format_delta(delta)}. {_group_label(group).title()} heat {heat_delta:+d}.{project_note}"
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
    _settle_item_violations(item, mitigated)
    mode_text = "settled with conditions" if mitigated else "accepted for formal response"
    project_note = ""
    if projects and item.project_id:
        project = advance_project_from_item(projects, item, state, approved=True, failed=False)
        if project:
            project_note = f" Project {project.project_id} status {project.status}."
    report = (
        f"{item.title} {mode_text}. Target group: {_group_label(group)}. "
        f"City delta: {_format_delta(averaged)}. {_population_report_fragment([districts[cid] for cid in targets])}{project_note}"
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


def project_step_template(chain_template_id: str, step_id: str) -> ProjectStepTemplate | None:
    chain = PROJECT_CHAINS.get(chain_template_id)
    if not chain:
        return None
    for step in chain.steps:
        if step.step_id == step_id:
            return step
    return None


def next_project_step(chain_template_id: str, step_id: str) -> ProjectStepTemplate | None:
    chain = PROJECT_CHAINS.get(chain_template_id)
    current = project_step_template(chain_template_id, step_id)
    if not chain or not current or not current.next_step_id:
        return None
    return project_step_template(chain_template_id, current.next_step_id)


def start_project_from_approval(
    state: CityState,
    item: DocketItem,
    template: DocketTemplate,
    target_cell_ids: Iterable[str],
) -> ProjectRecord | None:
    chain_id = template.starts_chain_id
    if not chain_id:
        return None
    chain = PROJECT_CHAINS.get(chain_id)
    if not chain:
        return None
    initial = project_step_template(chain_id, template.project_step_id or chain.initial_step_id)
    if not initial:
        return None
    next_step = next_project_step(chain_id, initial.step_id)
    current_step = next_step or initial
    project_id = f"P{state.turn:02d}-{item.item_id}"
    record = ProjectRecord(
        project_id=project_id,
        chain_template_id=chain_id,
        current_step_id=current_step.step_id,
        status="active" if next_step else "settled",
        turn_started=state.turn,
        due_turn=state.turn + max(1, current_step.due_after),
        stakeholder=item.stakeholder or template.stakeholder,
        target_cell_ids=list(target_cell_ids),
        payload={"source_item_id": item.item_id, "source_template_id": template.template_id},
        last_report=f"{chain.label} created from {item.title}.",
    )
    item.project_id = record.project_id
    item.chain_step_id = initial.step_id
    return record


def advance_project_from_item(
    projects: dict[str, ProjectRecord],
    item: DocketItem,
    state: CityState,
    approved: bool,
    failed: bool = False,
) -> ProjectRecord | None:
    if not item.project_id or item.project_id not in projects:
        return None
    project = projects[item.project_id]
    step = project_step_template(project.chain_template_id, item.chain_step_id or project.current_step_id)
    if not step:
        return None
    if not approved:
        project.status = "delayed"
        project.due_turn = state.turn + 1
        project.last_report = f"{step.title} delayed from docket action."
        return project
    if failed:
        if step.failure_step_id:
            failure_step = project_step_template(project.chain_template_id, step.failure_step_id)
            if failure_step:
                project.current_step_id = failure_step.step_id
                project.status = step.status_on_failure
                project.due_turn = state.turn + max(1, failure_step.due_after)
                project.last_report = f"{step.title} failed; {failure_step.title} is now due."
                return project
        project.status = step.status_on_failure
        project.last_report = f"{step.title} failed."
        return project
    next_step = next_project_step(project.chain_template_id, step.step_id)
    if next_step:
        project.current_step_id = next_step.step_id
        project.status = "active"
        project.due_turn = state.turn + max(1, next_step.due_after)
        project.last_report = f"{step.title} approved; {next_step.title} due turn {project.due_turn}."
    else:
        project.status = step.status_on_approval if step.status_on_approval in ("settled", "complete", "active") else "settled"
        project.last_report = f"{step.title} settled {PROJECT_CHAINS[project.chain_template_id].label}."
    return project


def active_feature_instances(features: Iterable[FeatureInstance], turn: int | None = None) -> list[FeatureInstance]:
    active_status = {"active", "settled", "enforced", "responded", "maintenance_due", "degraded"}
    out = []
    for feature in features:
        if feature.status not in active_status:
            continue
        if turn is not None and feature.expires_turn not in (-1, 0, None) and feature.expires_turn < turn:
            continue
        if feature.archetype_id not in FEATURE_ARCHETYPES:
            continue
        out.append(feature)
    return out


def recompute_network_access(
    districts: dict[str, DistrictProfile],
    features: Iterable[FeatureInstance],
    turn: int | None = None,
) -> dict[str, dict[str, int]]:
    for profile in districts.values():
        profile.network_access = {service: 0 for service in SERVICE_TYPES}
    for feature in active_feature_instances(features, turn):
        archetype = FEATURE_ARCHETYPES[feature.archetype_id]
        network_type = feature.network_type or archetype.network_type or feature.service_type or archetype.service_type
        if network_type not in SERVICE_TYPES:
            continue
        strength = max(1, int(feature.intensity or feature.capacity or archetype.network_strength or archetype.capacity or 1))
        for cid, weight in _feature_spatial_weights(feature, districts).items():
            if cid not in districts:
                continue
            value = _weighted_band(strength, weight)
            districts[cid].network_access[network_type] = min(12, districts[cid].network_access.get(network_type, 0) + value)
    for profile in districts.values():
        normalize_profile(profile)
    return {cid: dict(profile.network_access) for cid, profile in districts.items()}


def apply_hazard_turn(
    districts: dict[str, DistrictProfile],
    features: Iterable[FeatureInstance],
    turn: int | None = None,
) -> dict[str, int]:
    sources = {cid: {hazard: 0 for hazard in HAZARD_TYPES} for cid in districts}
    mitigations = {cid: {hazard: 0 for hazard in HAZARD_TYPES} for cid in districts}
    for feature in active_feature_instances(features, turn):
        archetype = FEATURE_ARCHETYPES[feature.archetype_id]
        hazard_effects = _instance_effect_map(feature, archetype, "hazard_effects")
        mitigation_effects = _instance_effect_map(feature, archetype, "mitigation_effects")
        for cid, weight in _feature_spatial_weights(feature, districts).items():
            if cid not in districts:
                continue
            for hazard, amount in hazard_effects.items():
                if hazard in HAZARD_TYPES and amount > 0:
                    sources[cid][hazard] += _weighted_band(amount, weight)
            for hazard, amount in mitigation_effects.items():
                if hazard in HAZARD_TYPES and amount > 0:
                    mitigations[cid][hazard] += _weighted_band(amount, weight)
    for cid, profile in districts.items():
        for hazard, amount in _service_hazard_mitigation(profile).items():
            mitigations[cid][hazard] += amount

    severe = 0
    for cid, profile in districts.items():
        current = _normalize_service_map(profile.hazards, HAZARD_TYPES, maximum=4, include_zeros=True)
        next_hazards: dict[str, int] = {}
        for hazard in HAZARD_TYPES:
            source = sources[cid][hazard]
            mitigation = mitigations[cid][hazard]
            rule = HAZARD_RULES[hazard]
            if source:
                band = min(4, current.get(hazard, 0) + source)
            else:
                band = max(0, current.get(hazard, 0) - rule.decay)
            band = max(0, band - mitigation)
            if band:
                next_hazards[hazard] = min(4, band)
            if band >= 4:
                severe += 1
        profile.hazards = next_hazards
        _apply_hazard_pressure(profile)
        normalize_profile(profile)
    return {"severe_hazards": severe}


def apply_housing_dynamics(districts: dict[str, DistrictProfile]) -> dict[str, int]:
    population_delta = 0
    pressured = 0
    for profile in districts.values():
        before = profile.population
        normalize_profile(profile)
        pressure = max(profile.displacement.values(), default=0)
        if pressure >= 2:
            pressured += 1
            _adjust_dissatisfaction(profile, ("renters", "elders", "artists", "families"), 1 if pressure < 4 else 2)
        if pressure >= 3:
            _shift_mix(profile, ("renters", "artists"), -1)
            _shift_mix(profile, ("homeowners", "developers"), 1)
        if profile.housing_capacity and profile.population > profile.housing_capacity:
            profile.population = max(100, profile.population - max(4, (profile.population - profile.housing_capacity) // 3))
        normalize_profile(profile)
        population_delta += profile.population - before
    return {"housing_population_delta": population_delta, "displacement_pressure": pressured}


def apply_template_long_term_effects(template: DocketTemplate, profiles: Iterable[DistrictProfile], mitigated: bool = False) -> dict[str, dict[str, int]]:
    deltas: dict[str, dict[str, int]] = {}
    for profile in profiles:
        before = {
            "population": profile.population,
            "housing_capacity": profile.housing_capacity,
            "affordability": profile.affordability,
        }
        _apply_housing_effects(profile, template.housing_effects)
        if mitigated and template.hazard_effects:
            profile.hazards = {
                hazard: max(0, profile.hazards.get(hazard, 0) - 1)
                for hazard in HAZARD_TYPES
                if profile.hazards.get(hazard, 0)
            }
        else:
            _apply_hazard_effects(profile, template.hazard_effects)
        normalize_profile(profile)
        delta = {
            "population": profile.population - before["population"],
            "housing_capacity": profile.housing_capacity - before["housing_capacity"],
            "affordability": profile.affordability - before["affordability"],
        }
        deltas[profile.cell_id] = {key: value for key, value in delta.items() if value}
    return deltas


def apply_scenario(state: CityState, districts: dict[str, DistrictProfile], scenario_id: str | None = None) -> None:
    if scenario_id:
        state.scenario_id = scenario_id
    scenario = SCENARIO_RULES.get(state.scenario_id, SCENARIO_RULES["default"])
    _apply_city_delta(state, scenario.starting_city_effects)
    for profile in districts.values():
        _apply_profile_delta(profile, {key: value for key, value in scenario.starting_district_effects.items() if key in DISTRICT_METRICS})
        _apply_housing_effects(profile, {key: value for key, value in scenario.starting_district_effects.items() if key not in DISTRICT_METRICS})
        _apply_hazard_effects(profile, scenario.hazard_bias)
        normalize_profile(profile)


def _feature_spatial_weights(feature: FeatureInstance, districts: dict[str, DistrictProfile]) -> dict[str, float]:
    targets = [cid for cid in feature.target_cell_ids if cid in districts]
    archetype = FEATURE_ARCHETYPES[feature.archetype_id]
    weights: dict[str, float] = {}
    for cid in targets:
        weights[cid] = max(weights.get(cid, 0.0), 1.0)
    if archetype.geometry_type == "LINE":
        neighbor_weight = 0.5
    else:
        neighbor_weight = 0.5
    for cid in targets:
        for adjacent in districts[cid].adjacent_cell_ids:
            if adjacent in districts and adjacent not in targets:
                weights[adjacent] = max(weights.get(adjacent, 0.0), neighbor_weight)
    return weights


def _weighted_band(amount: int, weight: float) -> int:
    if amount <= 0 or weight <= 0:
        return 0
    return max(1, round(amount * weight))


def _instance_effect_map(feature: FeatureInstance, archetype: FeatureArchetype, key: str) -> dict[str, int]:
    values = getattr(archetype, key)
    out = {str(name): int(value) for name, value in values.items() if int(value or 0)}
    raw = feature.metadata.get(key)
    if isinstance(raw, dict):
        for name, value in raw.items():
            try:
                amount = int(value or 0)
            except (TypeError, ValueError):
                continue
            if amount:
                out[str(name)] = amount
    return out


def _service_hazard_mitigation(profile: DistrictProfile) -> dict[str, int]:
    mitigation = {hazard: 0 for hazard in HAZARD_TYPES}
    for hazard, rule in HAZARD_RULES.items():
        for service, amount in rule.mitigation_service_types.items():
            access = profile.network_access.get(service, 0)
            if access:
                mitigation[hazard] += min(amount, max(1, access // 3))
    return {hazard: amount for hazard, amount in mitigation.items() if amount > 0}


def _apply_hazard_pressure(profile: DistrictProfile) -> None:
    risk_delta = 0
    unrest_delta = 0
    for hazard, band in _normalize_service_map(profile.hazards, HAZARD_TYPES, maximum=4, include_zeros=False).items():
        rule = HAZARD_RULES[hazard]
        if band >= rule.risk_threshold:
            risk_delta += band - rule.risk_threshold + 1
            _adjust_dissatisfaction(profile, rule.affected_groups, 1 if band < 4 else 2)
        if band >= rule.unrest_threshold:
            unrest_delta += 1
    if risk_delta or unrest_delta:
        _apply_profile_delta(profile, {"risk": risk_delta, "unrest": unrest_delta})


def _apply_housing_effects(profile: DistrictProfile, effects: dict[str, int]) -> None:
    if not effects:
        return
    if "housing_capacity" in effects or "capacity" in effects:
        profile.housing_capacity = max(0, int(profile.housing_capacity) + int(effects.get("housing_capacity", effects.get("capacity", 0)) or 0))
    if "population" in effects:
        profile.population = max(100, int(profile.population) + int(effects.get("population", 0) or 0))
    if "affordability" in effects:
        profile.affordability = _clamp(int(profile.affordability) + int(effects.get("affordability", 0) or 0))
    if "vacancy_rate" in effects and profile.housing_capacity:
        extra_capacity = round(profile.housing_capacity * int(effects.get("vacancy_rate", 0) or 0) / 100)
        profile.housing_capacity = max(0, profile.housing_capacity + extra_capacity)


def _apply_hazard_effects(profile: DistrictProfile, effects: dict[str, int]) -> None:
    if not effects:
        return
    hazards = _normalize_service_map(profile.hazards, HAZARD_TYPES, maximum=4, include_zeros=True)
    for hazard, amount in effects.items():
        if hazard not in HAZARD_TYPES:
            continue
        hazards[hazard] = max(0, min(4, hazards.get(hazard, 0) + int(amount or 0)))
    profile.hazards = {hazard: band for hazard, band in hazards.items() if band > 0}


def advance_turn(
    state: CityState,
    open_items: Iterable[DocketItem],
    districts: dict[str, DistrictProfile] | None = None,
    features: Iterable[FeatureInstance] = (),
    projects: dict[str, ProjectRecord] | None = None,
) -> str:
    return advance_turn_result(state, open_items, districts, features, projects).report


def advance_turn_result(
    state: CityState,
    open_items: Iterable[DocketItem],
    districts: dict[str, DistrictProfile] | None = None,
    features: Iterable[FeatureInstance] = (),
    projects: dict[str, ProjectRecord] | None = None,
) -> TurnAdvanceResult:
    items = list(open_items)
    feature_list = list(features or ())
    carried = 0
    expired = 0
    heated = 0
    local_grievances = 0
    overdue_violations = 0
    feature_updates: dict[str, dict[str, object]] = {}
    district_deltas: dict[str, dict[str, int]] = {}
    for item in items:
        overdue_violations += _advance_violation_deadlines(state, item)
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
            if projects and item.project_id in projects:
                project = projects[item.project_id]
                project.status = "overdue"
                project.due_turn = state.turn + 1
                project.last_report = f"{item.title} was unresolved on turn {state.turn}."
    if feature_list:
        feature_updates, district_deltas = _advance_feature_lifecycle(state, districts or {}, feature_list, state.turn + 1)
    revenue, upkeep, net = _apply_recurring_economy(state, districts or {}, feature_list)
    population_delta = 0
    new_incidents = 0
    system_notes: list[str] = []
    if districts:
        if feature_list or any(profile.hazards for profile in districts.values()):
            recompute_network_access(districts, feature_list, state.turn)
            hazard_report = apply_hazard_turn(districts, feature_list, state.turn)
            if hazard_report.get("severe_hazards"):
                system_notes.append(f"Severe hazard bands {hazard_report['severe_hazards']}.")
        housing_report = apply_housing_dynamics(districts)
        if housing_report.get("housing_population_delta"):
            population_delta += housing_report["housing_population_delta"]
        if housing_report.get("displacement_pressure"):
            system_notes.append(f"Displacement pressure in {housing_report['displacement_pressure']} district(s).")
        for profile in districts.values():
            population_delta += _advance_population_pressure(profile)
        new_incidents = _surface_new_incidents(state, districts.values())
    state.turn += 1
    state.ap = state.max_ap
    if state.turn in (3, 6):
        state.audit_stage += 1
    if state.turn > state.max_turns:
        state.status = "complete"
    audit = generate_audit_result(state, districts, feature_list, items)
    heat_text = f" Stakeholder heat added to {heated} unresolved case(s)." if heated else ""
    grievance_text = f" Local grievance files updated for {local_grievances} unresolved target(s)." if local_grievances else ""
    violation_text = f" Overdue violation(s): {overdue_violations}." if overdue_violations else ""
    feature_text = f" Feature updates: {len(feature_updates)}." if feature_updates else ""
    economy_text = f" Economy net {net:+d} (revenue {revenue}, upkeep {upkeep})." if revenue or upkeep else ""
    population_text = f" Population drift {population_delta:+d}." if population_delta else ""
    incident_text = f" New civic incident file(s): {new_incidents}." if new_incidents else ""
    system_text = f" {' '.join(system_notes)}" if system_notes else ""
    audit_text = f" Audit snapshot: {audit.grade}." if state.turn in (3, 6) or state.status == "complete" else ""
    report = (
        f"Advanced turn. Carried {carried} item(s), expired {expired} item(s)."
        f"{heat_text}{grievance_text}{violation_text}{feature_text}{economy_text}{population_text}{incident_text}{system_text}{audit_text}"
    )
    state.last_report = report
    return TurnAdvanceResult(
        report,
        city_delta={"money": net},
        district_deltas=district_deltas,
        feature_updates=feature_updates,
        revenue=revenue,
        upkeep=upkeep,
        net=net,
        audit=audit,
    )


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


def scorecard(
    state: CityState,
    districts: Iterable[DistrictProfile] | dict[str, DistrictProfile] | None = None,
    active_features: Iterable[FeatureInstance] | None = None,
    docket: Iterable[DocketItem] | None = None,
) -> tuple[str, str]:
    audit = generate_audit_result(state, districts, active_features, docket)
    return audit.grade, audit.report


def generate_audit_result(
    state: CityState,
    districts: Iterable[DistrictProfile] | dict[str, DistrictProfile] | None = None,
    active_features: Iterable[FeatureInstance] | None = None,
    docket: Iterable[DocketItem] | None = None,
) -> AuditResult:
    findings: list[AuditFinding] = []
    profiles = list((districts.values() if isinstance(districts, dict) else districts) or ())
    features = list(active_features or ())
    scenario = SCENARIO_RULES.get(state.scenario_id, SCENARIO_RULES["default"])
    score = _scenario_score(state, profiles, features, scenario)
    score += max(-10, min(10, state.last_net))
    if state.money < 0:
        findings.append(AuditFinding("money.negative", "critical", "money", "Budget is negative.", -25))
    elif state.money < 15:
        findings.append(AuditFinding("money.low", "warning", "money", "Budget is below the operating reserve.", -10))
    if state.last_net < 0:
        findings.append(AuditFinding("money.net_negative", "warning", "economy", "Recurring economy is losing money.", -5))
    if state.unrest >= 70:
        findings.append(AuditFinding("city.unrest", "critical", "city", "Citywide unrest is audit-critical.", -20))
    if state.risk >= 70:
        findings.append(AuditFinding("city.risk", "critical", "city", "Citywide risk is audit-critical.", -20))

    for profile in profiles:
        normalize_profile(profile)
        if profile.incident_state != "none":
            findings.append(AuditFinding(f"incident.{profile.cell_id}", "warning", "district", f"{profile.cell_id} has a visible {profile.incident_state}.", -8))
        if profile.risk >= 70:
            findings.append(AuditFinding(f"risk.{profile.cell_id}", "critical", "district", f"{profile.cell_id} risk is critical.", -12))
        if profile.unrest >= 70:
            findings.append(AuditFinding(f"unrest.{profile.cell_id}", "critical", "district", f"{profile.cell_id} unrest is critical.", -12))
        for service, gap in profile.service_gap.items():
            if gap >= AUDIT_THRESHOLDS["service_gap_critical"]:
                findings.append(AuditFinding(f"service_gap.{service}.{profile.cell_id}", "critical", "services", f"{profile.cell_id} has a critical {service.replace('_', ' ')} gap.", -12))
            elif gap >= AUDIT_THRESHOLDS["service_gap_warning"]:
                findings.append(AuditFinding(f"service_gap.{service}.{profile.cell_id}", "warning", "services", f"{profile.cell_id} has a {service.replace('_', ' ')} gap.", -6))
        for hazard, band in profile.hazards.items():
            if band >= 3:
                findings.append(AuditFinding(f"hazard.{hazard}.{profile.cell_id}", "warning", "hazards", f"{profile.cell_id} has elevated {hazard}.", -6))
        displacement = max(profile.displacement.values(), default=0)
        if displacement >= 3:
            findings.append(AuditFinding(f"displacement.{profile.cell_id}", "warning", "housing", f"{profile.cell_id} has displacement pressure.", -6))

    for feature in features:
        normalize_feature_instance(feature, state.turn)
        if feature.status == "failed":
            findings.append(AuditFinding(f"feature.failed.{feature.feature_id}", "critical", "features", f"{feature.feature_id} has failed.", -14))
        elif feature.status in ("maintenance_due", "degraded") or feature.condition <= AUDIT_THRESHOLDS["feature_condition_warning"]:
            severity = "critical" if feature.condition <= AUDIT_THRESHOLDS["feature_condition_critical"] else "warning"
            penalty = -12 if severity == "critical" else -6
            findings.append(AuditFinding(f"feature.condition.{feature.feature_id}", severity, "features", f"{feature.feature_id} condition is {feature.condition}.", penalty))

    for item in docket or ():
        for violation in _open_violations(item):
            deadline = int(violation.get("deadline_turn") or 0)
            if deadline and deadline < state.turn:
                severity = str(violation.get("severity") or "warning")
                penalty = -10 if severity == "critical" else -6
                findings.append(AuditFinding(f"violation.{item.item_id}.{violation.get('code')}", severity, "inspection", f"{item.item_id} has an overdue {violation.get('code')} violation.", penalty))

    score += sum(finding.score_delta for finding in findings)
    critical_count = sum(1 for finding in findings if finding.severity == "critical")
    if score >= 70 and state.money >= 0 and critical_count == 0:
        grade = "PASS"
    elif score >= 45 and critical_count <= 1:
        grade = "CONDITIONAL"
    else:
        grade = "FAIL"
    finding_text = "no findings" if not findings else f"{len(findings)} finding(s), {critical_count} critical"
    scenario_text = "" if state.scenario_id == "default" else f"; scenario={state.scenario_id}; priorities={', '.join(scenario.audit_priorities)}"
    report = (
        f"Audit {grade}: score={score}; prosperity={state.prosperity}, unrest={state.unrest}, "
        f"culture={state.culture}, risk={state.risk}, money={state.money}; net={state.last_net}{scenario_text}; {finding_text}."
    )
    return AuditResult(grade, score, tuple(findings), report)


def operating_rule_for_feature(feature_or_archetype_id: FeatureInstance | str) -> FeatureOperatingRule:
    archetype_id = feature_or_archetype_id.archetype_id if isinstance(feature_or_archetype_id, FeatureInstance) else feature_or_archetype_id
    return FEATURE_OPERATING_RULES.get(archetype_id, FeatureOperatingRule(archetype_id, upkeep_per_turn=1, decay_per_turn=5, maintenance_interval=3, maintenance_cost=6))


def normalize_feature_instance(feature: FeatureInstance, turn: int | None = None) -> FeatureInstance:
    archetype = FEATURE_ARCHETYPES.get(feature.archetype_id)
    if archetype:
        feature.family = feature.family or archetype.family
        feature.service_type = feature.service_type or archetype.service_type
        feature.network_type = feature.network_type or archetype.network_type or archetype.service_type
        feature.capacity = feature.capacity or archetype.capacity
        feature.display_state = feature.display_state or archetype.display_state
    rule = operating_rule_for_feature(feature)
    feature.intensity = max(1, int(feature.intensity or 1))
    feature.condition = max(0, min(100, int(feature.condition if feature.condition is not None else 100)))
    if feature.turn_created <= 0 and turn is not None:
        feature.turn_created = max(1, turn)
    if rule.lifespan_turns and feature.expires_turn in (-1, 0, None):
        feature.expires_turn = max(1, feature.turn_created) + rule.lifespan_turns
    if rule.maintenance_interval and feature.maintenance_due_turn in (-1, 0, None):
        feature.maintenance_due_turn = max(1, feature.turn_created) + rule.maintenance_interval
    if feature.status == "active" and feature.condition <= rule.degrade_threshold:
        feature.status = "degraded" if feature.condition > rule.failure_threshold else "failed"
    feature.display_state = feature.status
    feature.state_json = dict(feature.state_json or {})
    feature.metadata = dict(feature.metadata or {})
    return feature


def feature_update_payload(feature: FeatureInstance) -> dict[str, object]:
    return {
        "status": feature.status,
        "condition": feature.condition,
        "maintenance_due_turn": feature.maintenance_due_turn,
        "last_maintained_turn": feature.last_maintained_turn,
        "display_state": feature.display_state,
        "state_json": dict(feature.state_json or {}),
    }


def _advance_feature_lifecycle(
    state: CityState,
    districts: dict[str, DistrictProfile],
    features: list[FeatureInstance],
    next_turn: int,
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, int]]]:
    updates: dict[str, dict[str, object]] = {}
    district_deltas: dict[str, dict[str, int]] = {}
    backlog = 0
    for feature in features:
        before = feature_update_payload(normalize_feature_instance(feature, state.turn))
        rule = operating_rule_for_feature(feature)
        if feature.status in ("proposed", "expired"):
            continue
        if feature.expires_turn not in (-1, 0, None) and next_turn >= feature.expires_turn:
            feature.status = "expired"
        elif feature.status != "failed":
            if rule.decay_per_turn:
                feature.condition = max(0, feature.condition - rule.decay_per_turn)
            if rule.maintenance_interval and feature.maintenance_due_turn not in (-1, 0, None) and next_turn >= feature.maintenance_due_turn:
                feature.status = "maintenance_due"
            if feature.condition <= rule.failure_threshold:
                feature.status = "failed"
            elif feature.condition <= rule.degrade_threshold and feature.status == "active":
                feature.status = "degraded"
        if feature.status in ("maintenance_due", "degraded", "failed"):
            backlog += 1
        if feature.status == "failed" and not feature.state_json.get("failure_applied"):
            for cid in feature.target_cell_ids:
                if cid not in districts:
                    continue
                _apply_profile_delta(districts[cid], rule.failure_effects)
                _merge_delta(district_deltas.setdefault(cid, {}), rule.failure_effects)
            averaged = {metric: round(value / max(1, len(feature.target_cell_ids))) for metric, value in rule.failure_effects.items() if metric in CORE_METRICS}
            _apply_city_delta(state, averaged)
            feature.state_json["failure_applied"] = True
        feature.display_state = feature.status
        after = feature_update_payload(feature)
        if after != before:
            updates[feature.feature_id] = after
    state.maintenance_backlog = backlog
    return updates, district_deltas


def _apply_recurring_economy(
    state: CityState,
    districts: dict[str, DistrictProfile],
    features: list[FeatureInstance],
) -> tuple[int, int, int]:
    district_revenue = 0
    for profile in districts.values():
        raw = profile.population // 1000
        raw += max(0, profile.prosperity - 40) // 25
        raw += max(0, profile.culture - 55) // 35
        raw -= max(0, profile.unrest - 55) // 30
        raw -= max(0, profile.risk - 55) // 30
        district_revenue += max(0, min(2, raw))
    district_revenue = min(24, district_revenue)

    feature_revenue = 0
    upkeep = 0
    for feature in features:
        normalize_feature_instance(feature, state.turn)
        if feature.status not in ("active", "settled", "enforced", "responded", "maintenance_due", "degraded"):
            continue
        rule = operating_rule_for_feature(feature)
        revenue = rule.revenue_per_turn * feature.intensity
        if feature.status in ("maintenance_due", "degraded"):
            revenue = revenue // 2
        feature_revenue += revenue
        upkeep += rule.upkeep_per_turn * feature.intensity
        if feature.status == "maintenance_due":
            upkeep += 1
    revenue = district_revenue + feature_revenue
    net = revenue - upkeep
    state.money += net
    state.last_revenue = revenue
    state.last_upkeep = upkeep
    state.last_net = net
    return revenue, upkeep, net


def _settle_item_violations(item: DocketItem, mitigated: bool) -> None:
    inspection = dict((item.case_json or {}).get("inspection") or {})
    violations = list(inspection.get("violations") or [])
    changed = False
    for violation in violations:
        if not isinstance(violation, dict) or violation.get("status") not in ("open", "overdue"):
            continue
        if mitigated:
            violation["status"] = "complied"
            violation["compliance_outcome"] = "settled"
        else:
            violation["status"] = "accepted"
            violation["compliance_outcome"] = "conditions"
        changed = True
    if changed:
        inspection["violations"] = violations
        item.case_json = dict(item.case_json or {})
        item.case_json["inspection"] = inspection


def _advance_violation_deadlines(state: CityState, item: DocketItem) -> int:
    overdue = 0
    inspection = dict((item.case_json or {}).get("inspection") or {})
    violations = list(inspection.get("violations") or [])
    changed = False
    for violation in violations:
        if not isinstance(violation, dict) or violation.get("status") not in ("open", "overdue"):
            continue
        deadline = int(violation.get("deadline_turn") or 0)
        if deadline and deadline <= state.turn and violation.get("status") != "overdue":
            violation["status"] = "overdue"
            violation["compliance_outcome"] = "missed"
            _adjust_heat(state, item.stakeholder or TEMPLATES[item.template_id].stakeholder, 1)
            item.priority += 1
            overdue += 1
            changed = True
    if changed:
        inspection["violations"] = violations
        item.case_json = dict(item.case_json or {})
        item.case_json["inspection"] = inspection
    return overdue


def _open_violations(item: DocketItem) -> list[dict[str, object]]:
    inspection = (item.case_json or {}).get("inspection") or {}
    if not isinstance(inspection, dict):
        return []
    return [violation for violation in inspection.get("violations") or [] if isinstance(violation, dict) and violation.get("status") in ("open", "overdue")]


def _stakeholder_profile(stakeholder: str) -> StakeholderProfile:
    if stakeholder in STAKEHOLDERS:
        return STAKEHOLDERS[stakeholder]
    if stakeholder in CITIZEN_GROUPS:
        return StakeholderProfile(stakeholder, influence=2, patience=1, interests=(stakeholder,), followup_template_id=CIVIC_INCIDENT_TEMPLATE_ID)
    return StakeholderProfile(stakeholder or "general_public")


def _stakeholder_escalation_score(stakeholder: str, heat: int) -> int:
    profile = _stakeholder_profile(stakeholder)
    return heat * profile.influence - profile.patience


def adjust_stakeholder_pressure(state: CityState, stakeholder: str, amount: int, reason: str = "") -> int:
    if not stakeholder or amount == 0:
        return 0
    profile = _stakeholder_profile(stakeholder)
    adjusted = amount
    if amount == 1 and profile.patience >= 4:
        adjusted = 0
    before = state.stakeholder_heat.get(stakeholder, 0)
    after = max(0, before + adjusted)
    if after:
        state.stakeholder_heat[stakeholder] = after
    else:
        state.stakeholder_heat.pop(stakeholder, None)
    if adjusted > 0 and adjusted >= 2:
        for ally in profile.allies:
            if ally != stakeholder:
                state.stakeholder_heat[ally] = max(0, state.stakeholder_heat.get(ally, 0) + 1)
        for rival in profile.rivals:
            if rival != stakeholder:
                current = state.stakeholder_heat.get(rival, 0)
                if current > 0:
                    state.stakeholder_heat[rival] = max(0, current - 1)
    return after - before


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
        "network_type": archetype.network_type,
        "network_strength": archetype.network_strength,
        "coverage_radius_m": archetype.coverage_radius_m,
        "capacity": archetype.capacity,
        "land_use": archetype.land_use,
        "hazard_effects": dict(archetype.hazard_effects),
        "mitigation_effects": dict(archetype.mitigation_effects),
        "housing_effects": dict(archetype.housing_effects),
        "starts_chain_id": archetype.starts_chain_id,
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
        if archetype.network_type and archetype.network_type not in SERVICE_TYPES:
            errors.append(f"{archetype_id}: invalid network type {archetype.network_type!r}")
        for hazard in archetype.hazard_effects:
            if hazard not in HAZARD_TYPES:
                errors.append(f"{archetype_id}: invalid hazard effect {hazard!r}")
        for hazard in archetype.mitigation_effects:
            if hazard not in HAZARD_TYPES:
                errors.append(f"{archetype_id}: invalid mitigation effect {hazard!r}")
        if archetype.starts_chain_id and archetype.starts_chain_id not in PROJECT_CHAINS:
            errors.append(f"{archetype_id}: unknown starts_chain_id {archetype.starts_chain_id!r}")
        if archetype_id not in FEATURE_OPERATING_RULES:
            errors.append(f"{archetype_id}: missing operating rule")
    for archetype_id, rule in FEATURE_OPERATING_RULES.items():
        if rule.archetype_id != archetype_id:
            errors.append(f"{archetype_id}: operating rule id mismatch")
        if archetype_id not in FEATURE_ARCHETYPES:
            errors.append(f"{archetype_id}: operating rule has no archetype")
    for template_id, template in TEMPLATES.items():
        if not template.spawn_archetype_id:
            errors.append(f"{template_id}: missing spawn_archetype_id")
        elif template.spawn_archetype_id not in FEATURE_ARCHETYPES:
            errors.append(f"{template_id}: unknown spawn archetype {template.spawn_archetype_id!r}")
        else:
            archetype = FEATURE_ARCHETYPES[template.spawn_archetype_id]
            if archetype.geometry_type != template.geometry_type:
                errors.append(f"{template_id}: archetype geometry {archetype.geometry_type!r} != template geometry {template.geometry_type!r}")
        if template.stakeholder not in STAKEHOLDERS and template.stakeholder not in CITIZEN_GROUPS:
            errors.append(f"{template_id}: stakeholder {template.stakeholder!r} missing profile")
        for hazard in template.hazard_effects:
            if hazard not in HAZARD_TYPES:
                errors.append(f"{template_id}: invalid hazard effect {hazard!r}")
        if template.starts_chain_id and template.starts_chain_id not in PROJECT_CHAINS:
            errors.append(f"{template_id}: unknown starts_chain_id {template.starts_chain_id!r}")
        if template.project_step_id:
            chain_ids = [chain_id for chain_id, chain in PROJECT_CHAINS.items() if any(step.step_id == template.project_step_id for step in chain.steps)]
            if template.starts_chain_id:
                chain_ids = [chain_id for chain_id in chain_ids if chain_id == template.starts_chain_id]
            if not chain_ids:
                errors.append(f"{template_id}: unknown project_step_id {template.project_step_id!r}")
        for tag in template.scenario_tags:
            if tag not in SCENARIO_RULES:
                errors.append(f"{template_id}: unknown scenario tag {tag!r}")
    for rule_id, rule in INSPECTION_RULES.items():
        if rule.rule_id != rule_id:
            errors.append(f"{rule_id}: inspection rule id mismatch")
        for code in rule.evidence_codes + rule.violation_codes:
            if code not in VIOLATION_CODES:
                errors.append(f"{rule_id}: unknown inspection code {code!r}")
    for hazard_type, rule in HAZARD_RULES.items():
        if rule.hazard_type != hazard_type:
            errors.append(f"{hazard_type}: hazard_type mismatch")
        for group in rule.affected_groups:
            if group not in CITIZEN_GROUPS:
                errors.append(f"{hazard_type}: invalid affected group {group!r}")
        for service in rule.mitigation_service_types:
            if service not in SERVICE_TYPES:
                errors.append(f"{hazard_type}: invalid mitigation service {service!r}")
    for chain_id, chain in PROJECT_CHAINS.items():
        step_ids = {step.step_id for step in chain.steps}
        if chain.initial_step_id not in step_ids:
            errors.append(f"{chain_id}: initial step missing")
        for step in chain.steps:
            if step.template_id not in TEMPLATES:
                errors.append(f"{chain_id}:{step.step_id}: unknown template {step.template_id!r}")
            if step.next_step_id and step.next_step_id not in step_ids:
                errors.append(f"{chain_id}:{step.step_id}: unknown next step {step.next_step_id!r}")
            if step.failure_step_id and step.failure_step_id not in step_ids:
                errors.append(f"{chain_id}:{step.step_id}: unknown failure step {step.failure_step_id!r}")
    for scenario_id, scenario in SCENARIO_RULES.items():
        if scenario.scenario_id != scenario_id:
            errors.append(f"{scenario_id}: scenario_id mismatch")
        for template_id in scenario.docket_priority:
            if template_id not in TEMPLATES:
                errors.append(f"{scenario_id}: unknown docket priority {template_id!r}")
        for hazard in scenario.hazard_bias:
            if hazard not in HAZARD_TYPES:
                errors.append(f"{scenario_id}: invalid hazard bias {hazard!r}")
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
    profile.adjacent_cell_ids = sorted({str(cid) for cid in (profile.adjacent_cell_ids or ()) if cid and str(cid) != profile.cell_id})
    profile.network_access = _normalize_service_map(profile.network_access, SERVICE_TYPES, maximum=12, include_zeros=True)
    profile.hazards = _normalize_service_map(profile.hazards, HAZARD_TYPES, maximum=4, include_zeros=False)
    profile.population_mix = _normalize_bands(profile.population_mix, 3)
    if not any(profile.population_mix.values()):
        profile.population_mix = _normalize_bands(ARCHETYPE_BASE_MIX.get(profile.district_type, {}), 3)
    profile.dissatisfaction = _normalize_bands(profile.dissatisfaction, 4)
    for group, band in profile.population_mix.items():
        if band > 0 and group not in profile.dissatisfaction:
            profile.dissatisfaction[group] = 0
    _normalize_housing(profile)
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


def _normalize_service_map(
    values: dict[str, int] | None,
    allowed: Iterable[str],
    maximum: int,
    include_zeros: bool = False,
) -> dict[str, int]:
    allowed_tuple = tuple(allowed)
    out = {key: 0 for key in allowed_tuple} if include_zeros else {}
    for key, value in (values or {}).items():
        if key not in allowed_tuple:
            continue
        band = max(0, min(maximum, int(value or 0)))
        if band or include_zeros:
            out[key] = band
    return out


def _normalize_housing(profile: DistrictProfile) -> None:
    if profile.housing_capacity <= 0:
        vacancy_seed = {
            "residential": 14,
            "mercantile": 9,
            "industrial": 5,
            "civic": 7,
            "academic": 11,
            "natural": 4,
        }.get(profile.district_type, 8)
        profile.housing_capacity = max(profile.population + 50, round(profile.population * (100 + vacancy_seed) / 100))
    profile.housing_capacity = max(0, int(profile.housing_capacity))
    if profile.affordability <= 0:
        profile.affordability = {
            "residential": 58,
            "mercantile": 48,
            "industrial": 42,
            "civic": 52,
            "academic": 50,
            "natural": 44,
        }.get(profile.district_type, 50)
    profile.affordability = _clamp(profile.affordability)
    if profile.housing_capacity:
        profile.vacancy_rate = max(0, min(100, round((profile.housing_capacity - profile.population) * 100 / profile.housing_capacity)))
    else:
        profile.vacancy_rate = 0
    pressure = _displacement_pressure(profile)
    previous = {group: max(0, min(4, int(value or 0))) for group, value in (profile.displacement or {}).items() if group in CITIZEN_GROUPS}
    displacement: dict[str, int] = {}
    for group in ("renters", "elders", "artists", "families"):
        band = max(previous.get(group, 0), pressure if profile.population_mix.get(group, 0) else max(0, pressure - 1))
        if band:
            displacement[group] = min(4, band)
    profile.displacement = displacement


def _displacement_pressure(profile: DistrictProfile) -> int:
    pressure = 0
    if profile.vacancy_rate <= 3:
        pressure += 2
    elif profile.vacancy_rate <= 7:
        pressure += 1
    if profile.affordability < 35:
        pressure += 2
    elif profile.affordability < 50:
        pressure += 1
    if profile.prosperity >= 65 or profile.culture >= 65:
        pressure += 1
    if profile.unrest >= 55 or profile.risk >= 55:
        pressure += 1
    if profile.network_access.get("utilities", 0) >= 2:
        pressure -= 1
    if profile.network_access.get("mobility", 0) >= 2:
        pressure -= 1
    if profile.service_gap.get("child_services", 0) == 0 and profile.population_mix.get("families", 0):
        pressure -= 1
    return max(0, min(4, pressure))


def build_grid_adjacency(rows: int, cols: int) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    for row in range(rows):
        for col in range(cols):
            cell_id = f"D{row:02d}{col:02d}"
            neighbors = []
            for nr, nc in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if 0 <= nr < rows and 0 <= nc < cols:
                    neighbors.append(f"D{nr:02d}{nc:02d}")
            adjacency[cell_id] = neighbors
    return adjacency


def assign_grid_adjacency(profiles: Iterable[DistrictProfile], rows: int | None = None, cols: int | None = None) -> dict[str, list[str]]:
    profiles_by_id = {profile.cell_id: profile for profile in profiles}
    if rows is None or cols is None:
        parsed = [_parse_grid_cell_id(cell_id) for cell_id in profiles_by_id]
        parsed = [value for value in parsed if value is not None]
        rows = max((row for row, _col in parsed), default=-1) + 1
        cols = max((col for _row, col in parsed), default=-1) + 1
    adjacency = build_grid_adjacency(rows or 0, cols or 0)
    for cell_id, profile in profiles_by_id.items():
        profile.adjacent_cell_ids = [cid for cid in adjacency.get(cell_id, []) if cid in profiles_by_id]
    return {cell_id: list(profile.adjacent_cell_ids) for cell_id, profile in profiles_by_id.items()}


def _parse_grid_cell_id(cell_id: str) -> tuple[int, int] | None:
    if len(cell_id or "") != 5 or not cell_id.startswith("D"):
        return None
    try:
        return int(cell_id[1:3]), int(cell_id[3:5])
    except ValueError:
        return None


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
    for service, demand in _network_demand_for_profile(profile).items():
        access = profile.network_access.get(service, 0)
        if demand > access:
            gaps[service] = max(gaps.get(service, 0), (demand - access) * 10)
    return {service: gap for service, gap in sorted(gaps.items()) if gap > 0}


def _network_demand_for_profile(profile: DistrictProfile) -> dict[str, int]:
    population_scale = max(1, profile.population // 1400)
    housing_scale = max(0, profile.housing_capacity // 2500)
    demand = {
        "utilities": 1 + population_scale + housing_scale,
        "mobility": 1 + population_scale,
        "fire_response": 1 if profile.risk >= 35 or profile.district_type in ("industrial", "civic") else 0,
        "green_buffer": 1 if profile.risk >= 45 or profile.hazards.get("heat", 0) or profile.hazards.get("ecology", 0) else 0,
        "child_services": 1 if profile.population_mix.get("families", 0) >= 2 else 0,
        "culture_access": 1 if profile.population_mix.get("artists", 0) >= 2 or profile.population_mix.get("students", 0) >= 2 else 0,
    }
    if profile.district_type in ("industrial", "mercantile"):
        demand["utilities"] += 1
        demand["mobility"] += 1
    if profile.land_use in ("mixed_use", "commerce", "transport_corridor", "bus_priority"):
        demand["mobility"] += 1
    if profile.zoning_overlay in ("mixed_use", "affordable_infill"):
        demand["utilities"] += 1
        demand["mobility"] += 1
    return {service: min(6, max(0, value)) for service, value in demand.items() if value > 0}


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
    return adjust_stakeholder_pressure(state, stakeholder, amount)


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
