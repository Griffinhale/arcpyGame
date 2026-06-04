# District Identity, Spread, and Buyouts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 12-week, attention-scarce district identity system where ignored permits can create hidden city momentum and low-prosperity districts can enter deterministic buyout transitions driven by adjacent district types.

**Architecture:** Keep pure game logic in `toolbox/permit_office/` and ArcGIS persistence/presentation in `toolbox/permit_office_arcgis/`. Add focused pure-rule modules for expiration, hidden type pressure, and buyouts; wire them into `advance_turn_result`, `generate_docket`, and the existing schema/store/symbology layers. First pass represents unattended momentum as district state/report text; ghost features remain disabled until playtesting proves they improve readability.

**Tech Stack:** Python dataclasses, deterministic `random.Random`, pytest, ArcPy geodatabase adapters, ArcGIS Pro unique-value symbology.

## Implementation Status

Implemented on `main` on 2026-06-03. The checklist below is preserved as the
implementation record, but several final fixes were made after review:

- Converted districts are excluded from immediate same-week re-contest.
- Week 12 is playable; the final audit is filed when closing week 12.
- ArcGIS persistence and district-type-first symbology were wired in the same pass.
- `pytest` was unavailable in the local environment, so verification used
  `compileall`, public API import smoke, direct focused test calls, and a broad
  no-arg direct smoke harness. The broad harness still has two known
  `families` dissatisfaction assertion failures tracked separately.

---

## Scope Check

This plan implements the approved district identity, expiration, hidden ledger, buyout, and docket-weighting spec as one connected subsystem. It intentionally does not implement the broader dashboard redesign, scorecard auto-open, start/help screen, or full city-health simplification issues.

## File Structure

- Create `toolbox/permit_office/expiration.py`
  - Owns unresolved docket expiration policy and city momentum effects.
- Create `toolbox/permit_office/type_pressure.py`
  - Owns hidden per-type ledger defaults, persistence helpers, and qualitative pressure summaries.
- Create `toolbox/permit_office/buyouts.py`
  - Owns buyout eligibility, bidding/refusal, contested transition resolution, and report text.
- Modify `toolbox/permit_office/models.py`
  - Adds district identity/transition fields and template expiration policy fields.
- Modify `toolbox/permit_office/catalogs/templates.py`
  - Assigns expiration policies and pressure categories to templates.
- Modify `toolbox/permit_office/profiles.py`
  - Adds district-weighted docket generation and target-aware item metadata.
- Modify `toolbox/permit_office/turns.py`
  - Wires expiration, recurring systems, buyout transitions, 12-week pacing, and week-6 audit.
- Modify `toolbox/permit_office/decisions.py`
  - Makes deny cost 0 AP and adds stabilizing pressure effects for contested districts.
- Modify `toolbox/permit_office/__init__.py`
  - Exports new pure-rule modules through the existing facade.
- Modify `toolbox/permit_office_arcgis/schema.py`
  - Adds district fields for identity/buyout renderer state.
- Modify `toolbox/permit_office_arcgis/store.py`
  - Reads/writes new district fields and hidden ledger state.
- Modify `toolbox/permit_office_arcgis/symbology_config.py`
  - Adds identity/transition symbol values and makes district type the default district renderer field.
- Modify `toolbox/permit_office_arcgis/geometry.py`
  - Applies district identity symbology and preserves transition state readability.
- Modify `tests/test_permit_office_rules.py`
  - Adds pure-rule regression coverage for pacing, expiration, ledger, buyouts, and docket weighting.
- Modify `tests/test_permit_office_symbology.py`
  - Adds renderer coverage for identity-first district symbology.
- Modify `docs/permit-office-turn-data-flow.md`
  - Documents 12-week turn flow and expiration/buyout order.

## Implementation Order

### Task 1: Data Model And Template Policy

**Files:**
- Modify: `toolbox/permit_office/models.py`
- Modify: `toolbox/permit_office/catalogs/templates.py`
- Test: `tests/test_permit_office_rules.py`

- [ ] **Step 1: Write failing model and catalog tests**

Add these tests near the existing catalog tests in `tests/test_permit_office_rules.py`:

```python
def test_city_state_defaults_to_twelve_week_attention_scarcity():
    state = rules.CityState()

    assert state.max_turns == 12
    assert state.ap == 2
    assert state.max_ap == 2
    assert state.type_ledger == {}
    assert state.pending_followups == {}


def test_district_profiles_include_identity_transition_defaults():
    profile = rules.generate_district_profiles(rows=1, cols=1, seed=2026)[0]

    assert profile.prior_district_type == ""
    assert profile.identity_state == "stable"
    assert profile.contesting_cell_id == ""
    assert profile.contesting_type == ""
    assert profile.transition_due_turn == 0
    assert profile.buyout_pressure == 0
    assert profile.last_buyout_report == ""


def test_templates_declare_expiration_policy_and_pressure_category():
    policies = {template.expiration_policy for template in rules.TEMPLATES.values()}

    assert {"missed_window", "city_momentum", "momentum_with_followup_risk", "mandatory_followup"} <= policies
    assert rules.TEMPLATES["procession_route"].expiration_policy == "missed_window"
    assert rules.TEMPLATES["mixed_use_rezoning"].expiration_policy == "city_momentum"
    assert rules.TEMPLATES["street_vendor_compact"].expiration_policy == "momentum_with_followup_risk"
    assert rules.TEMPLATES[rules.MAINTENANCE_TEMPLATE_ID].expiration_policy == "mandatory_followup"
    assert all(template.pressure_category for template in rules.TEMPLATES.values())
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_city_state_defaults_to_twelve_week_attention_scarcity tests/test_permit_office_rules.py::test_district_profiles_include_identity_transition_defaults tests/test_permit_office_rules.py::test_templates_declare_expiration_policy_and_pressure_category -q
```

Expected: FAIL because the new fields and defaults do not exist yet.

- [ ] **Step 3: Add model fields**

In `toolbox/permit_office/models.py`, update `DocketTemplate`, `DistrictProfile`, and `CityState`:

```python
@dataclass(frozen=True)
class DocketTemplate:
    """Catalog definition for a permit, enforcement, or incident docket item."""

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
    expiration_policy: str = "city_momentum"
    pressure_category: str = "general"
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
```

Add these fields to `DistrictProfile` after `district_type`:

```python
    prior_district_type: str = ""
    identity_state: str = "stable"
    contesting_cell_id: str = ""
    contesting_type: str = ""
    transition_due_turn: int = 0
    buyout_pressure: int = 0
    last_buyout_report: str = ""
```

Change `CityState` defaults:

```python
    max_turns: int = 12
    ap: int = 2
    max_ap: int = 2
```

Add this field near `stakeholder_memory`:

```python
    type_ledger: dict[str, dict[str, int]] = field(default_factory=dict)
    pending_followups: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Assign template policies**

In `toolbox/permit_office/catalogs/templates.py`, add explicit `expiration_policy` and `pressure_category` keyword arguments to every `DocketTemplate`.

Use this mapping:

```python
TEMPLATE_POLICY_BY_ID = {
    "connector_corridor": ("city_momentum", "transit"),
    "procession_route": ("missed_window", "event"),
    "utility_expansion_trench": ("momentum_with_followup_risk", "utility"),
    "natural_reserve_conversion": ("missed_window", "land"),
    "mixed_use_rezoning": ("city_momentum", "development"),
    "child_development_park_annex": ("missed_window", "service"),
    "street_vendor_compact": ("momentum_with_followup_risk", "business"),
    "business_license_fee_sweep": ("missed_window", "business"),
    "contractor_renovation_waiver": ("momentum_with_followup_risk", "construction"),
    "fire_budget_escalation": ("mandatory_followup", "safety"),
    "public_art_museum_grant": ("missed_window", "culture"),
    ENFORCEMENT_TEMPLATE_ID: ("mandatory_followup", "enforcement"),
    "compliance_settlement_drive": ("missed_window", "compliance"),
    CIVIC_INCIDENT_TEMPLATE_ID: ("mandatory_followup", "incident"),
    "bus_priority_link": ("city_momentum", "transit"),
    "water_main_loop": ("momentum_with_followup_risk", "utility"),
    "green_buffer_reserve": ("missed_window", "land"),
    "inspection_order": ("mandatory_followup", "inspection"),
    "affordable_infill_rezoning": ("city_momentum", "housing"),
    "infill_construction_site": ("momentum_with_followup_risk", "construction"),
    "infill_inspection_order": ("mandatory_followup", "inspection"),
    "occupancy_certificate": ("missed_window", "housing"),
    "vendor_sanitation_complaint": ("mandatory_followup", "health"),
    MAINTENANCE_TEMPLATE_ID: ("mandatory_followup", "maintenance"),
}
```

Apply the values as explicit keyword arguments in each template definition, for example:

```python
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
    expiration_policy="missed_window",
    pressure_category="event",
    preview="Adds a temporary event route. Culture may improve, but crowd control needs review.",
    inspect_hint="Route review found strong interest, likely bottlenecks, and signage conflicts.",
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
    contact_name="Event Route Office",
    spawn_archetype_id="licensed_procession",
),
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_city_state_defaults_to_twelve_week_attention_scarcity tests/test_permit_office_rules.py::test_district_profiles_include_identity_transition_defaults tests/test_permit_office_rules.py::test_templates_declare_expiration_policy_and_pressure_category -q
```

Expected: PASS.

- [ ] **Step 6: Run the full rules test file and update golden tests intentionally**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py -q
```

Expected: existing six-week golden-route tests fail because pacing defaults changed. Update or replace tests in Task 2, not in this task.

- [ ] **Step 7: Commit**

```bash
git add toolbox/permit_office/models.py toolbox/permit_office/catalogs/templates.py tests/test_permit_office_rules.py
git commit -m "feat: add district identity policy fields"
```

### Task 2: Twelve-Week Pacing And Deny Attention Cost

**Files:**
- Modify: `toolbox/permit_office/turns.py`
- Modify: `toolbox/permit_office/decisions.py`
- Modify: `tests/test_permit_office_rules.py`

- [ ] **Step 1: Replace six-week sequence test with 12-week pacing tests**

In `tests/test_permit_office_rules.py`, replace `test_six_turn_demo_sequence_covers_shortlist` with:

```python
def test_twelve_week_docket_generation_keeps_three_or_four_items_available():
    state = rules.CityState()
    districts = {profile.cell_id: profile for profile in rules.generate_district_profiles(seed=2026)}

    seen = set()
    for _week in range(1, state.max_turns + 1):
        docket = rules.generate_docket(
            turn=state.turn,
            seed=2026,
            count=4,
            state=state,
            districts=districts,
        )
        assert 3 <= len(docket) <= 4
        assert len({item.item_id for item in docket}) == len(docket)
        seen.update(item.template_id for item in docket)
        if state.turn < state.max_turns:
            rules.advance_turn_result(state, docket, districts)

    assert state.max_turns == 12
    assert len(seen & set(rules.DEMO_TEMPLATE_IDS)) >= 8
```

Add this test near decision tests:

```python
def test_deny_does_not_spend_ap_but_still_resolves_case():
    state = rules.CityState()
    districts = {profile.cell_id: profile for profile in rules.generate_district_profiles(rows=1, cols=1, seed=2026)}
    item = rules.DocketItem(
        "deny-test",
        "street_vendor_compact",
        rules.TEMPLATES["street_vendor_compact"].title,
        "POINT",
        1,
    )

    result = rules.resolve_decision(state, item, districts, "deny", ["D0000"], seed=2026)

    assert result.ok is True
    assert item.status == "denied"
    assert state.ap == state.max_ap
    assert result.stakeholder_delta["vendors"] > 0
```

Add this audit checkpoint test:

```python
def test_twelve_week_season_mid_audit_week_six_and_final_week_twelve():
    state = rules.CityState()
    districts = {profile.cell_id: profile for profile in rules.generate_district_profiles(seed=2026)}

    for _ in range(5):
        rules.advance_turn_result(state, [], districts)

    assert state.turn == 6
    assert state.audit_stage == 1
    assert state.status == "playing"

    for _ in range(6):
        rules.advance_turn_result(state, [], districts)

    assert state.turn == 12
    assert state.audit_stage == 2
    assert state.status == "complete"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_twelve_week_docket_generation_keeps_three_or_four_items_available tests/test_permit_office_rules.py::test_deny_does_not_spend_ap_but_still_resolves_case tests/test_permit_office_rules.py::test_twelve_week_season_mid_audit_week_six_and_final_week_twelve -q
```

Expected: FAIL because deny still spends AP, audit checkpoint is week 3, and docket generation is still demo-sequence biased.

- [ ] **Step 3: Make denial cost 0 AP**

In `toolbox/permit_office/decisions.py`, replace the deny AP block:

```python
    if action_key == "deny":
        blocked = _spend_ap(state, action, item.item_id, "Denial")
        if blocked:
            return blocked
```

with:

```python
    if action_key == "deny":
        # Denial records an office disposition but does not consume scarce
        # attention. Inspecting, issuing, and mitigating remain AP-gated.
        if state.ap < 0:
            return _blocked(action, item.item_id, "Invalid AP state.")
```

Do not call `_spend_ap` for deny.

- [ ] **Step 4: Move audit checkpoint to week 6**

In `toolbox/permit_office/turns.py`, replace:

```python
    if not final_week and state.turn == 3:
        state.audit_stage += 1
```

with:

```python
    mid_audit_turn = max(2, state.max_turns // 2)
    if not final_week and state.turn == mid_audit_turn:
        state.audit_stage = max(state.audit_stage, 1)
```

Replace:

```python
    audit_text = f" Final audit: {audit.grade}." if state.status == "complete" else f" Audit snapshot: {audit.grade}." if state.turn == 3 else ""
```

with:

```python
    audit_text = (
        f" Final audit: {audit.grade}."
        if state.status == "complete"
        else f" Audit snapshot: {audit.grade}."
        if state.turn == mid_audit_turn
        else ""
    )
```

- [ ] **Step 5: Keep generated weeks populated**

In `toolbox/permit_office/profiles.py`, change the default count from 3 to 4:

```python
    count: int = 4,
```

Keep call-site overrides working. This gives the attention-scarcity loop more cases than AP by default.

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_twelve_week_docket_generation_keeps_three_or_four_items_available tests/test_permit_office_rules.py::test_deny_does_not_spend_ap_but_still_resolves_case tests/test_permit_office_rules.py::test_twelve_week_season_mid_audit_week_six_and_final_week_twelve -q
```

Expected: PASS.

- [ ] **Step 7: Update the old golden-route test for new pacing or mark it as legacy**

Replace `test_seed_2026_golden_route_produces_stable_conditional_scorecard` with a narrower smoke test that does not pin six-week values:

```python
def test_seed_2026_reasonable_attention_route_reaches_final_audit():
    profiles = {profile.cell_id: profile for profile in rules.generate_district_profiles(seed=2026)}
    state = rules.CityState()
    active_features = []
    docket_history = []

    for _week in range(1, state.max_turns + 1):
        docket = rules.generate_docket(
            turn=state.turn,
            seed=2026,
            count=4,
            state=state,
            districts=profiles,
            active_features=active_features,
        )
        for item in docket[:2]:
            targets = item.target_cell_ids or ["D0000"]
            if item.geometry_type == "LINE":
                targets = ["D0000", "D0001"]
            result = rules.resolve_decision(
                state,
                item,
                profiles,
                "deny" if item.template_id == "mixed_use_rezoning" else "approve",
                targets,
                seed=2026,
                active_features=active_features,
            )
            assert result.ok is True
        docket_history.extend(docket)
        rules.advance_turn_result(state, docket, profiles, active_features)

    grade, report = rules.scorecard(state, profiles, active_features, docket_history)

    assert state.status == "complete"
    assert state.turn == 12
    assert grade in {"PASS", "CONDITIONAL", "FAIL"}
    assert "score=" in report
```

- [ ] **Step 8: Run full rules tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add toolbox/permit_office/turns.py toolbox/permit_office/decisions.py toolbox/permit_office/profiles.py tests/test_permit_office_rules.py
git commit -m "feat: shift game pacing to attention scarcity"
```

### Task 3: Explicit Expiration And City Momentum

**Files:**
- Create: `toolbox/permit_office/expiration.py`
- Modify: `toolbox/permit_office/turns.py`
- Modify: `toolbox/permit_office/profiles.py`
- Modify: `toolbox/permit_office/__init__.py`
- Test: `tests/test_permit_office_rules.py`

- [ ] **Step 1: Write failing expiration tests**

Add these tests to `tests/test_permit_office_rules.py`:

```python
def test_missed_window_expiration_closes_original_without_pressure():
    state = rules.CityState()
    districts = {profile.cell_id: profile for profile in rules.generate_district_profiles(rows=1, cols=1, seed=2026)}
    item = rules.DocketItem("expire-event", "procession_route", "Licensed Procession Route", "LINE", 1)
    item.target_cell_ids = ["D0000"]

    result = rules.resolve_unattended_item(state, item, districts, seed=2026)

    assert item.status == "expired"
    assert result.policy == "missed_window"
    assert result.followup_template_id == ""
    assert districts["D0000"].buyout_pressure == 0
    assert "window closed" in result.report.lower()


def test_city_momentum_expiration_adds_pressure_and_report():
    state = rules.CityState()
    districts = {profile.cell_id: profile for profile in rules.generate_district_profiles(rows=1, cols=1, seed=2026)}
    districts["D0000"].prosperity = 42
    item = rules.DocketItem("expire-rezone", "mixed_use_rezoning", "Mixed-Use Rezoning Petition", "POLYGON", 1)
    item.target_cell_ids = ["D0000"]

    result = rules.resolve_unattended_item(state, item, districts, seed=2026)

    assert item.status == "expired"
    assert result.policy == "city_momentum"
    assert districts["D0000"].buyout_pressure > 0
    assert districts["D0000"].identity_state in {"stable", "vulnerable"}
    assert "momentum" in result.report.lower()


def test_bad_momentum_can_spawn_different_followup_template():
    state = rules.CityState()
    districts = {profile.cell_id: profile for profile in rules.generate_district_profiles(rows=1, cols=1, seed=2026)}
    districts["D0000"].risk = 70
    item = rules.DocketItem("expire-vendor", "street_vendor_compact", "Street Vendor Compact", "POINT", 1)
    item.target_cell_ids = ["D0000"]

    result = rules.resolve_unattended_item(state, item, districts, seed=1)

    assert item.status == "expired"
    assert result.policy == "momentum_with_followup_risk"
    assert result.followup_template_id in {"", rules.CIVIC_INCIDENT_TEMPLATE_ID, rules.ENFORCEMENT_TEMPLATE_ID}
    assert result.report


def test_pending_momentum_followup_appears_as_different_next_docket_item():
    state = rules.CityState()
    state.pending_followups["expire-vendor"] = rules.CIVIC_INCIDENT_TEMPLATE_ID
    docket = rules.generate_docket(turn=2, seed=2026, count=4, state=state, districts={})

    assert docket[0].template_id == rules.CIVIC_INCIDENT_TEMPLATE_ID
    assert docket[0].origin_item_id == "momentum:expire-vendor"
    assert "Follow-up from unattended city momentum" in docket[0].preview_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_missed_window_expiration_closes_original_without_pressure tests/test_permit_office_rules.py::test_city_momentum_expiration_adds_pressure_and_report tests/test_permit_office_rules.py::test_bad_momentum_can_spawn_different_followup_template tests/test_permit_office_rules.py::test_pending_momentum_followup_appears_as_different_next_docket_item -q
```

Expected: FAIL because `resolve_unattended_item` does not exist.

- [ ] **Step 3: Create expiration result and resolver**

Create `toolbox/permit_office/expiration.py`:

```python
"""Unattended docket expiration and city momentum rules."""

from __future__ import annotations

from dataclasses import dataclass
import random

from .catalogs import CIVIC_INCIDENT_TEMPLATE_ID, ENFORCEMENT_TEMPLATE_ID, TEMPLATES
from .helpers import _adjust_heat, _apply_population_reaction, normalize_profile
from .models import CityState, DistrictProfile, DocketItem


@dataclass(frozen=True)
class ExpirationResult:
    """Outcome from resolving one unattended docket item at week close."""

    item_id: str
    policy: str
    report: str
    affected_cell_ids: tuple[str, ...] = ()
    followup_template_id: str = ""


def resolve_unattended_item(
    state: CityState,
    item: DocketItem,
    districts: dict[str, DistrictProfile] | None,
    seed: int = 2026,
) -> ExpirationResult:
    """Resolve one unresolved docket item without returning the same item."""

    template = TEMPLATES[item.template_id]
    item.stakeholder = item.stakeholder or template.stakeholder
    policy = template.expiration_policy or "city_momentum"
    affected = tuple(cid for cid in item.target_cell_ids if districts and cid in districts)
    _adjust_heat(state, item.stakeholder, template.ignore_heat)
    if policy == "mandatory_followup":
        item.status = "carried"
        return ExpirationResult(
            item.item_id,
            policy,
            f"{item.title} remains mandatory and returns next week.",
            affected,
            template.template_id,
        )
    item.status = "expired"
    if policy == "missed_window":
        return ExpirationResult(
            item.item_id,
            policy,
            f"{item.title} window closed without office action.",
            affected,
        )
    pressure_added = _apply_momentum_pressure(template, affected, districts or {})
    followup = ""
    if policy == "momentum_with_followup_risk":
        followup = _followup_from_bad_momentum(template.template_id, affected, districts or {}, seed)
    return ExpirationResult(
        item.item_id,
        policy,
        f"{item.title} expired into city momentum; pressure +{pressure_added}.",
        affected,
        followup,
    )


def _apply_momentum_pressure(template, affected: tuple[str, ...], districts: dict[str, DistrictProfile]) -> int:
    """Apply hidden buyout pressure from unattended city momentum."""

    if not affected:
        return 0
    pressure = 2 if template.expiration_policy == "momentum_with_followup_risk" else 1
    for cid in affected:
        profile = districts[cid]
        profile.buyout_pressure = max(0, min(100, profile.buyout_pressure + pressure))
        if profile.prosperity < 50 and profile.identity_state == "stable":
            profile.identity_state = "vulnerable"
        _apply_population_reaction(template, [profile], "ignore", False)
        normalize_profile(profile)
    return pressure


def _followup_from_bad_momentum(
    template_id: str,
    affected: tuple[str, ...],
    districts: dict[str, DistrictProfile],
    seed: int,
) -> str:
    """Return a different follow-up template when unattended momentum goes badly."""

    if not affected:
        return ""
    worst = max((districts[cid].risk + districts[cid].unrest for cid in affected), default=0)
    rng = random.Random(f"momentum:{seed}:{template_id}:{','.join(affected)}:{worst}")
    if worst + rng.randrange(0, 40) < 80:
        return ""
    if template_id in {"contractor_renovation_waiver", "infill_construction_site"}:
        return ENFORCEMENT_TEMPLATE_ID
    return CIVIC_INCIDENT_TEMPLATE_ID
```

- [ ] **Step 4: Export expiration helpers**

In `toolbox/permit_office/__init__.py`, add:

```python
from .expiration import *
```

above:

```python
from .turns import *
```

- [ ] **Step 5: Wire expiration into turn advancement**

In `toolbox/permit_office/turns.py`, import:

```python
from .expiration import resolve_unattended_item
```

Replace this block inside unresolved item handling:

```python
            if item.carryover == "expire_or_return" and (item.turn + len(item.item_id)) % 2 == 0:
                item.status = "carried"
                carried += 1
            else:
                item.status = "expired"
                expired += 1
```

with:

```python
            expiration = resolve_unattended_item(state, item, districts or {}, seed=2026)
            if item.status == "carried":
                carried += 1
            elif item.status == "expired":
                expired += 1
            if expiration.followup_template_id:
                state.pending_followups[item.item_id] = expiration.followup_template_id
```

Keep the existing project-overdue block after this replacement.

- [ ] **Step 6: Add pending follow-up docket generation**

In `toolbox/permit_office/profiles.py`, add this helper below `_project_due_items`:

```python
def _pending_momentum_followup_items(turn: int, state: CityState | None, limit: int) -> list[DocketItem]:
    """Convert pending momentum follow-ups into current docket items."""

    if not state or not state.pending_followups or limit <= 0:
        return []
    out: list[DocketItem] = []
    consumed: list[str] = []
    for idx, origin_item_id in enumerate(sorted(state.pending_followups), start=1):
        if len(out) >= limit:
            break
        template_id = state.pending_followups[origin_item_id]
        if template_id not in TEMPLATES:
            consumed.append(origin_item_id)
            continue
        item = _make_docket_item(turn, idx, template_id, origin_item_id=f"momentum:{origin_item_id}")
        item.preview_text = f"{item.preview_text} Follow-up from unattended city momentum."
        item.priority = max(item.priority, 2)
        out.append(item)
        consumed.append(origin_item_id)
    for origin_item_id in consumed:
        state.pending_followups.pop(origin_item_id, None)
    return out
```

In `generate_docket`, after project due items and before maintenance follow-ups, add:

```python
    for followup in _pending_momentum_followup_items(turn, state, count - len(items)):
        if len(items) >= count:
            break
        items.append(followup)
```

- [ ] **Step 7: Run focused expiration tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_missed_window_expiration_closes_original_without_pressure tests/test_permit_office_rules.py::test_city_momentum_expiration_adds_pressure_and_report tests/test_permit_office_rules.py::test_bad_momentum_can_spawn_different_followup_template tests/test_permit_office_rules.py::test_pending_momentum_followup_appears_as_different_next_docket_item -q
```

Expected: PASS.

- [ ] **Step 8: Run rules tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py -q
```

Expected: PASS or only docket-order failures that Task 6 will intentionally replace. If unrelated failures occur, fix them in this task before committing.

- [ ] **Step 9: Commit**

```bash
git add toolbox/permit_office/expiration.py toolbox/permit_office/turns.py toolbox/permit_office/profiles.py toolbox/permit_office/__init__.py tests/test_permit_office_rules.py
git commit -m "feat: resolve unattended docket momentum"
```

### Task 4: Hidden Type Ledger

**Files:**
- Create: `toolbox/permit_office/type_pressure.py`
- Modify: `toolbox/permit_office/__init__.py`
- Test: `tests/test_permit_office_rules.py`

- [ ] **Step 1: Write failing ledger tests**

Add:

```python
def test_type_ledger_rebuilds_from_district_holdings():
    districts = {
        profile.cell_id: profile
        for profile in rules.generate_district_profiles(rows=2, cols=2, seed=2026)
    }

    ledger = rules.rebuild_type_ledger(districts)

    assert set(ledger) == set(rules.DISTRICT_TYPES)
    assert sum(entry["holdings"] for entry in ledger.values()) == 4
    assert all(entry["capital"] >= 0 for entry in ledger.values())
    assert all("appetite" in entry for entry in ledger.values())
    assert all("fatigue" in entry for entry in ledger.values())
    assert all("overextension" in entry for entry in ledger.values())


def test_type_ledger_round_trips_through_city_state_memory():
    state = rules.CityState()
    districts = {
        profile.cell_id: profile
        for profile in rules.generate_district_profiles(rows=2, cols=2, seed=2026)
    }
    ledger = rules.rebuild_type_ledger(districts)

    rules.write_type_ledger(state, ledger)
    loaded = rules.read_type_ledger(state, districts)

    assert loaded == ledger
    assert state.type_ledger == ledger


def test_type_pressure_summary_is_qualitative_not_table_data():
    ledger = {
        "mercantile": {"capital": 85, "appetite": 12, "fatigue": 1, "holdings": 4, "overextension": 0},
        "residential": {"capital": 20, "appetite": 2, "fatigue": 4, "holdings": 2, "overextension": 5},
    }

    summary = rules.type_pressure_summary(ledger)

    assert "Mercantile" in summary
    assert "expansion pressure" in summary
    assert "$" not in summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_type_ledger_rebuilds_from_district_holdings tests/test_permit_office_rules.py::test_type_ledger_round_trips_through_city_state_memory tests/test_permit_office_rules.py::test_type_pressure_summary_is_qualitative_not_table_data -q
```

Expected: FAIL because ledger helpers do not exist.

- [ ] **Step 3: Create type pressure module**

Create `toolbox/permit_office/type_pressure.py`:

```python
"""Hidden district-type pressure ledger."""

from __future__ import annotations

from .catalogs import DISTRICT_TYPES
from .models import CityState, DistrictProfile

TYPE_LEDGER_KEY = "type_ledger"


def rebuild_type_ledger(districts: dict[str, DistrictProfile]) -> dict[str, dict[str, int]]:
    """Create a hidden ledger from current district holdings."""

    ledger = {
        dtype: {"capital": 20, "appetite": 3, "fatigue": 0, "holdings": 0, "overextension": 0}
        for dtype in DISTRICT_TYPES
    }
    prosperity_by_type = {dtype: [] for dtype in DISTRICT_TYPES}
    for profile in districts.values():
        dtype = profile.district_type
        if dtype not in ledger:
            continue
        ledger[dtype]["holdings"] += 1
        prosperity_by_type[dtype].append(int(profile.prosperity))
    for dtype, prosperities in prosperity_by_type.items():
        if prosperities:
            average = sum(prosperities) // len(prosperities)
            ledger[dtype]["capital"] = max(0, average + ledger[dtype]["holdings"] * 5)
            ledger[dtype]["appetite"] = max(1, min(20, average // 8))
            ledger[dtype]["overextension"] = max(0, ledger[dtype]["holdings"] * 3 - average // 5)
    return ledger


def read_type_ledger(state: CityState, districts: dict[str, DistrictProfile]) -> dict[str, dict[str, int]]:
    """Read hidden type ledger from city state, rebuilding missing or invalid data."""

    if isinstance(state.type_ledger, dict) and state.type_ledger:
        return _normalize_ledger(state.type_ledger, districts)
    ledger = rebuild_type_ledger(districts)
    write_type_ledger(state, ledger)
    return ledger


def write_type_ledger(state: CityState, ledger: dict[str, dict[str, int]]) -> None:
    """Persist hidden type ledger on city state."""

    state.type_ledger = _normalize_ledger(ledger, {})


def adjust_type_ledger(
    ledger: dict[str, dict[str, int]],
    dtype: str,
    capital_delta: int = 0,
    appetite_delta: int = 0,
    fatigue_delta: int = 0,
    holdings_delta: int = 0,
    overextension_delta: int = 0,
) -> None:
    """Apply bounded changes to one ledger entry."""

    entry = ledger.setdefault(dtype, {"capital": 0, "appetite": 0, "fatigue": 0, "holdings": 0, "overextension": 0})
    entry["capital"] = max(0, min(200, int(entry.get("capital", 0)) + capital_delta))
    entry["appetite"] = max(0, min(50, int(entry.get("appetite", 0)) + appetite_delta))
    entry["fatigue"] = max(0, min(100, int(entry.get("fatigue", 0)) + fatigue_delta))
    entry["holdings"] = max(0, int(entry.get("holdings", 0)) + holdings_delta)
    entry["overextension"] = max(0, min(100, int(entry.get("overextension", 0)) + overextension_delta))


def type_pressure_summary(ledger: dict[str, dict[str, int]]) -> str:
    """Return one qualitative report sentence for the strongest type pressure."""

    if not ledger:
        return "No dominant expansion pressure is visible."
    dtype, entry = max(
        ledger.items(),
        key=lambda row: int(row[1].get("capital", 0)) + int(row[1].get("appetite", 0)) - int(row[1].get("fatigue", 0)),
    )
    label = dtype.replace("_", " ").title()
    return f"{label} districts show the strongest expansion pressure."


def _normalize_ledger(
    ledger: dict[str, dict[str, int]],
    districts: dict[str, DistrictProfile],
) -> dict[str, dict[str, int]]:
    """Return a complete bounded ledger for all known district types."""

    rebuilt = rebuild_type_ledger(districts) if districts else {
        dtype: {"capital": 20, "appetite": 3, "fatigue": 0, "holdings": 0, "overextension": 0}
        for dtype in DISTRICT_TYPES
    }
    for dtype, entry in ledger.items():
        if dtype not in rebuilt or not isinstance(entry, dict):
            continue
        for key in ("capital", "appetite", "fatigue", "holdings", "overextension"):
            rebuilt[dtype][key] = max(0, int(entry.get(key, rebuilt[dtype][key]) or 0))
    return rebuilt
```

- [ ] **Step 4: Export type pressure helpers**

In `toolbox/permit_office/__init__.py`, add:

```python
from .type_pressure import *
```

before `from .expiration import *`.

- [ ] **Step 5: Run focused ledger tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_type_ledger_rebuilds_from_district_holdings tests/test_permit_office_rules.py::test_type_ledger_round_trips_through_city_state_memory tests/test_permit_office_rules.py::test_type_pressure_summary_is_qualitative_not_table_data -q
```

Expected: PASS.

- [ ] **Step 6: Run rules tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add toolbox/permit_office/type_pressure.py toolbox/permit_office/__init__.py tests/test_permit_office_rules.py
git commit -m "feat: add hidden district type ledger"
```

### Task 5: Buyout Engine

**Files:**
- Create: `toolbox/permit_office/buyouts.py`
- Modify: `toolbox/permit_office/__init__.py`
- Modify: `toolbox/permit_office/decisions.py`
- Modify: `toolbox/permit_office/turns.py`
- Test: `tests/test_permit_office_rules.py`

- [ ] **Step 1: Write failing buyout tests**

Add:

```python
def _district_for_buyout(cell_id, dtype, prosperity, adjacent):
    profile = rules.DistrictProfile(
        cell_id=cell_id,
        name=cell_id,
        population=1000,
        prosperity=prosperity,
        unrest=25,
        culture=35,
        risk=20,
        services=40,
        district_type=dtype,
        adjacent_cell_ids=list(adjacent),
    )
    rules.normalize_profile(profile)
    return profile


def test_buyout_no_eligible_target_does_nothing():
    state = rules.CityState()
    districts = {
        "A": _district_for_buyout("A", "residential", 60, ["B"]),
        "B": _district_for_buyout("B", "mercantile", 70, ["A"]),
    }
    ledger = rules.rebuild_type_ledger(districts)

    result = rules.resolve_buyout_round(state, districts, ledger, seed=2026)

    assert result.started == []
    assert districts["A"].identity_state == "stable"
    assert districts["B"].identity_state == "stable"


def test_buyout_single_bidder_starts_contested_transition():
    state = rules.CityState()
    districts = {
        "A": _district_for_buyout("A", "residential", 35, ["B"]),
        "B": _district_for_buyout("B", "mercantile", 78, ["A"]),
    }
    ledger = rules.rebuild_type_ledger(districts)
    ledger["mercantile"]["capital"] = 100
    ledger["mercantile"]["appetite"] = 20

    result = rules.resolve_buyout_round(state, districts, ledger, seed=2026)

    assert result.started == ["A"]
    assert districts["A"].identity_state == "contested"
    assert districts["A"].contesting_cell_id == "B"
    assert districts["A"].contesting_type == "mercantile"
    assert districts["A"].transition_due_turn == state.turn + 1
    assert "entered contested buyout" in result.report.lower()


def test_contested_transition_converts_when_pressure_remains_high():
    state = rules.CityState(turn=2)
    target = _district_for_buyout("A", "residential", 32, ["B"])
    target.identity_state = "contested"
    target.contesting_cell_id = "B"
    target.contesting_type = "mercantile"
    target.transition_due_turn = 2
    target.buyout_pressure = 5
    districts = {
        "A": target,
        "B": _district_for_buyout("B", "mercantile", 80, ["A"]),
    }
    ledger = rules.rebuild_type_ledger(districts)

    result = rules.resolve_contested_transitions(state, districts, ledger)

    assert result.converted == ["A"]
    assert districts["A"].district_type == "mercantile"
    assert districts["A"].prior_district_type == "residential"
    assert districts["A"].identity_state == "converted"


def test_contested_transition_cancels_when_target_stabilizes():
    state = rules.CityState(turn=2)
    target = _district_for_buyout("A", "residential", 57, ["B"])
    target.identity_state = "contested"
    target.contesting_cell_id = "B"
    target.contesting_type = "mercantile"
    target.transition_due_turn = 2
    target.buyout_pressure = 0
    districts = {
        "A": target,
        "B": _district_for_buyout("B", "mercantile", 80, ["A"]),
    }
    ledger = rules.rebuild_type_ledger(districts)

    result = rules.resolve_contested_transitions(state, districts, ledger)

    assert result.cancelled == ["A"]
    assert districts["A"].district_type == "residential"
    assert districts["A"].identity_state == "stable"


def test_successful_attention_reduces_buyout_pressure_on_target():
    state = rules.CityState(money=100)
    districts = {
        "D0000": _district_for_buyout("D0000", "residential", 42, []),
    }
    districts["D0000"].identity_state = "contested"
    districts["D0000"].buyout_pressure = 5
    item = rules.DocketItem(
        "stabilize-annex",
        "child_development_park_annex",
        rules.TEMPLATES["child_development_park_annex"].title,
        "POINT",
        1,
    )

    result = rules.resolve_decision(state, item, districts, "approve_mitigated", ["D0000"], seed=2026, mitigated=True)

    assert result.ok is True
    assert districts["D0000"].buyout_pressure < 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_buyout_no_eligible_target_does_nothing tests/test_permit_office_rules.py::test_buyout_single_bidder_starts_contested_transition tests/test_permit_office_rules.py::test_contested_transition_converts_when_pressure_remains_high tests/test_permit_office_rules.py::test_contested_transition_cancels_when_target_stabilizes tests/test_permit_office_rules.py::test_successful_attention_reduces_buyout_pressure_on_target -q
```

Expected: FAIL because buyout helpers do not exist.

- [ ] **Step 3: Create buyout module**

Create `toolbox/permit_office/buyouts.py`:

```python
"""District buyout bidding and contested-transition rules."""

from __future__ import annotations

from dataclasses import dataclass
import random

from .helpers import normalize_profile
from .models import CityState, DistrictProfile
from .type_pressure import adjust_type_ledger


@dataclass(frozen=True)
class BuyoutRoundResult:
    """Summary of buyout bids started during one week close."""

    started: list[str]
    refused: list[str]
    report: str


@dataclass(frozen=True)
class TransitionResult:
    """Summary of contested transitions resolved during one week close."""

    converted: list[str]
    cancelled: list[str]
    report: str


def resolve_buyout_round(
    state: CityState,
    districts: dict[str, DistrictProfile],
    ledger: dict[str, dict[str, int]],
    seed: int = 2026,
) -> BuyoutRoundResult:
    """Start contested buyout transitions for eligible low-prosperity districts."""

    started: list[str] = []
    refused: list[str] = []
    reports: list[str] = []
    for target_id in sorted(districts):
        target = districts[target_id]
        if not _eligible_target(target):
            continue
        bids = _candidate_bids(state, target, districts, ledger, seed)
        if not bids:
            continue
        bid_score, bidder = bids[0]
        threshold = _refusal_threshold(target, seed, state.turn, bidder.cell_id)
        if bid_score < threshold:
            refused.append(target.cell_id)
            target.last_buyout_report = f"{target.name} refused a {bidder.district_type} bid."
            reports.append(target.last_buyout_report)
            continue
        _start_transition(state, target, bidder, bid_score, ledger)
        started.append(target.cell_id)
        reports.append(target.last_buyout_report)
    return BuyoutRoundResult(started, refused, " ".join(reports))


def resolve_contested_transitions(
    state: CityState,
    districts: dict[str, DistrictProfile],
    ledger: dict[str, dict[str, int]],
) -> TransitionResult:
    """Convert or cancel districts whose contested transition is due."""

    converted: list[str] = []
    cancelled: list[str] = []
    reports: list[str] = []
    for profile in districts.values():
        if profile.identity_state != "contested" or profile.transition_due_turn > state.turn:
            continue
        if profile.prosperity >= 50 and profile.buyout_pressure <= 1:
            profile.identity_state = "stable"
            profile.contesting_cell_id = ""
            profile.contesting_type = ""
            profile.transition_due_turn = 0
            profile.last_buyout_report = f"{profile.name} stabilized and cancelled the pending buyout."
            cancelled.append(profile.cell_id)
            reports.append(profile.last_buyout_report)
            continue
        old_type = profile.district_type
        new_type = profile.contesting_type
        profile.prior_district_type = old_type
        profile.district_type = new_type
        profile.identity_state = "converted"
        profile.contesting_cell_id = ""
        profile.contesting_type = ""
        profile.transition_due_turn = 0
        profile.buyout_pressure = max(0, profile.buyout_pressure - 2)
        profile.prosperity = max(0, min(100, profile.prosperity + 6))
        profile.unrest = max(0, min(100, profile.unrest + 3))
        profile.last_buyout_report = f"{profile.name} converted from {old_type} to {new_type} after the buyout closed."
        adjust_type_ledger(ledger, old_type, holdings_delta=-1)
        adjust_type_ledger(ledger, new_type, holdings_delta=1, fatigue_delta=2, overextension_delta=3)
        normalize_profile(profile)
        converted.append(profile.cell_id)
        reports.append(profile.last_buyout_report)
    return TransitionResult(converted, cancelled, " ".join(reports))


def reduce_buyout_pressure(profile: DistrictProfile, amount: int = 2) -> None:
    """Reduce pressure on a district after stabilizing player action."""

    profile.buyout_pressure = max(0, int(profile.buyout_pressure or 0) - amount)
    if profile.identity_state == "vulnerable" and profile.buyout_pressure == 0:
        profile.identity_state = "stable"


def _eligible_target(profile: DistrictProfile) -> bool:
    return (
        profile.prosperity < 50
        and profile.identity_state != "contested"
        and bool(profile.adjacent_cell_ids)
        and profile.incident_state == "none"
    )


def _candidate_bids(
    state: CityState,
    target: DistrictProfile,
    districts: dict[str, DistrictProfile],
    ledger: dict[str, dict[str, int]],
    seed: int,
) -> list[tuple[int, DistrictProfile]]:
    bids: list[tuple[int, DistrictProfile]] = []
    for bidder_id in sorted(target.adjacent_cell_ids):
        bidder = districts.get(bidder_id)
        if bidder is None or bidder.identity_state == "contested":
            continue
        if bidder.district_type == target.district_type:
            continue
        if bidder.prosperity < target.prosperity + 8:
            continue
        entry = ledger.get(bidder.district_type, {})
        if int(entry.get("capital", 0)) <= 0 or int(entry.get("appetite", 0)) <= 0:
            continue
        rng = random.Random(f"bid:{seed}:{state.turn}:{target.cell_id}:{bidder.cell_id}:{target.prosperity}")
        score = (
            bidder.prosperity
            + int(entry.get("capital", 0)) // 3
            + int(entry.get("appetite", 0))
            - int(entry.get("fatigue", 0))
            - int(entry.get("overextension", 0))
            + target.buyout_pressure * 3
            + rng.randrange(-8, 9)
        )
        bids.append((score, bidder))
    return sorted(bids, key=lambda row: (-row[0], row[1].cell_id))


def _refusal_threshold(target: DistrictProfile, seed: int, turn: int, bidder_id: str) -> int:
    leverage = max(
        0,
        min(
            100,
            int(target.prosperity)
            + int(target.services) // 2
            + int(target.culture) // 3
            - int(target.unrest) // 2
            - int(target.risk) // 3,
        ),
    )
    rng = random.Random(f"refuse:{seed}:{turn}:{target.cell_id}:{bidder_id}:{leverage}")
    return 35 + leverage // 2 + rng.randrange(-10, 11)


def _start_transition(
    state: CityState,
    target: DistrictProfile,
    bidder: DistrictProfile,
    bid_score: int,
    ledger: dict[str, dict[str, int]],
) -> None:
    target.identity_state = "contested"
    target.contesting_cell_id = bidder.cell_id
    target.contesting_type = bidder.district_type
    target.transition_due_turn = state.turn + 1
    target.last_buyout_report = (
        f"{target.name} entered contested buyout from {bidder.name}; "
        f"{bidder.district_type} bid strength {bid_score}."
    )
    adjust_type_ledger(ledger, bidder.district_type, capital_delta=-(bid_score // 8), fatigue_delta=1, overextension_delta=1)
```

- [ ] **Step 4: Export buyout helpers**

In `toolbox/permit_office/__init__.py`, add:

```python
from .buyouts import *
```

before `from .turns import *`.

- [ ] **Step 5: Wire buyouts into turn advancement**

In `toolbox/permit_office/turns.py`, import:

```python
from .buyouts import resolve_buyout_round, resolve_contested_transitions
from .type_pressure import read_type_ledger, write_type_ledger
```

After population/incidents are processed and before `final_week = state.turn >= state.max_turns`, add:

```python
        ledger = read_type_ledger(state, districts)
        transition_result = resolve_contested_transitions(state, districts, ledger)
        buyout_result = resolve_buyout_round(state, districts, ledger, seed=2026)
        write_type_ledger(state, ledger)
        if transition_result.report:
            system_notes.append(transition_result.report)
        if buyout_result.report:
            system_notes.append(buyout_result.report)
```

Keep this inside the `if districts:` block so save files without district rows still advance.

- [ ] **Step 6: Reduce buyout pressure after successful attention**

In `toolbox/permit_office/decisions.py`, import:

```python
from .buyouts import reduce_buyout_pressure
```

After successful approval effects are applied and before the approval report is built, add:

```python
    if not failure_triggered:
        for cid in targets:
            reduction = 3 if mitigated else 2
            reduce_buyout_pressure(districts[cid], reduction)
```

This first pass limits pressure reduction to ordinary permit approvals and mitigated approvals. Incident and enforcement actions keep their existing effects until playtesting shows pressure reduction needs to apply there too.

- [ ] **Step 7: Run focused buyout tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_buyout_no_eligible_target_does_nothing tests/test_permit_office_rules.py::test_buyout_single_bidder_starts_contested_transition tests/test_permit_office_rules.py::test_contested_transition_converts_when_pressure_remains_high tests/test_permit_office_rules.py::test_contested_transition_cancels_when_target_stabilizes tests/test_permit_office_rules.py::test_successful_attention_reduces_buyout_pressure_on_target -q
```

Expected: PASS.

- [ ] **Step 8: Add integration test for week close**

Add:

```python
def test_week_close_can_start_buyout_transition_from_unattended_pressure():
    state = rules.CityState()
    districts = {
        "A": _district_for_buyout("A", "residential", 35, ["B"]),
        "B": _district_for_buyout("B", "mercantile", 82, ["A"]),
    }
    item = rules.DocketItem("ignored-rezone", "mixed_use_rezoning", "Mixed-Use Rezoning Petition", "POLYGON", 1)
    item.target_cell_ids = ["A"]

    result = rules.advance_turn_result(state, [item], districts)

    assert state.turn == 2
    assert districts["A"].identity_state in {"vulnerable", "contested"}
    assert "expired" in result.report.lower()
```

- [ ] **Step 9: Run rules tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add toolbox/permit_office/buyouts.py toolbox/permit_office/decisions.py toolbox/permit_office/turns.py toolbox/permit_office/__init__.py tests/test_permit_office_rules.py
git commit -m "feat: add district buyout transitions"
```

### Task 6: District-Weighted Docket Variability

**Files:**
- Modify: `toolbox/permit_office/profiles.py`
- Test: `tests/test_permit_office_rules.py`

- [ ] **Step 1: Write failing docket variability tests**

Add:

```python
def test_docket_order_varies_by_seed_for_same_week():
    state = rules.CityState()
    districts = {profile.cell_id: profile for profile in rules.generate_district_profiles(seed=2026)}

    first = rules.generate_docket(turn=1, seed=2026, count=4, state=state, districts=districts)
    second = rules.generate_docket(turn=1, seed=2027, count=4, state=copy.deepcopy(state), districts=copy.deepcopy(districts))

    assert [item.template_id for item in first] != [item.template_id for item in second]


def test_docket_weights_reflect_district_type_distribution():
    state = rules.CityState()
    mercantile = {
        f"M{i}": _district_for_buyout(f"M{i}", "mercantile", 65, [])
        for i in range(8)
    }
    natural = {
        f"N{i}": _district_for_buyout(f"N{i}", "natural", 65, [])
        for i in range(8)
    }

    market_docket = rules.generate_docket(turn=4, seed=2026, count=4, state=state, districts=mercantile)
    natural_docket = rules.generate_docket(turn=4, seed=2026, count=4, state=copy.deepcopy(state), districts=natural)

    market_categories = [rules.TEMPLATES[item.template_id].category for item in market_docket]
    natural_categories = [rules.TEMPLATES[item.template_id].category for item in natural_docket]

    assert market_categories.count("business") + market_categories.count("development") >= 1
    assert natural_categories.count("land") >= 1
    assert [item.template_id for item in market_docket] != [item.template_id for item in natural_docket]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_docket_order_varies_by_seed_for_same_week tests/test_permit_office_rules.py::test_docket_weights_reflect_district_type_distribution -q
```

Expected: FAIL because the demo sequence dominates ordering.

- [ ] **Step 3: Add weighted template helpers**

In `toolbox/permit_office/profiles.py`, add below `_scenario_ordered_templates`:

```python
TYPE_CATEGORY_WEIGHTS = {
    "mercantile": {"business": 4, "development": 3, "compliance": 2},
    "industrial": {"utility": 4, "department": 2, "compliance": 2, "transit": 2},
    "civic": {"department": 3, "education": 2, "culture": 2, "transit": 2},
    "academic": {"culture": 3, "education": 3, "event": 2, "land": 1},
    "natural": {"land": 5, "culture": 1},
    "residential": {"residential": 4, "education": 2, "development": 2, "business": 1},
}


def _weighted_template_pool(
    turn: int,
    seed: int,
    count: int,
    state: CityState | None,
    districts: dict[str, DistrictProfile] | None,
    scenario: ScenarioRule,
) -> list[str]:
    """Return deterministic proposal templates weighted by district mix."""

    rng = random.Random(f"docket:{seed}:{turn}:{_district_mix_key(districts)}:{state.prosperity if state else 0}:{state.unrest if state else 0}:{state.risk if state else 0}")
    weights = {template_id: 1 for template_id in DEMO_TEMPLATE_IDS}
    for template_id in scenario.docket_priority:
        if template_id in weights:
            weights[template_id] += 4
    if districts:
        for profile in districts.values():
            for template_id, template in TEMPLATES.items():
                if template_id not in weights:
                    continue
                weights[template_id] += TYPE_CATEGORY_WEIGHTS.get(profile.district_type, {}).get(template.category, 0)
                if profile.district_type in template.good_fit_types:
                    weights[template_id] += 2
                if profile.district_type in template.bad_fit_types:
                    weights[template_id] = max(1, weights[template_id] - 1)
                if profile.prosperity < 45 and template.category in {"development", "business", "residential"}:
                    weights[template_id] += 2
                if profile.unrest > 45 and template.is_incident:
                    weights[template_id] += 3
                if profile.risk > 45 and template.category in {"utility", "department", "compliance"}:
                    weights[template_id] += 2
    chosen: list[str] = []
    available = dict(weights)
    while available and len(chosen) < count:
        total = sum(available.values())
        pick = rng.randrange(total)
        running = 0
        selected = next(iter(available))
        for template_id, weight in sorted(available.items()):
            running += weight
            if pick < running:
                selected = template_id
                break
        chosen.append(selected)
        available.pop(selected)
    return chosen


def _district_mix_key(districts: dict[str, DistrictProfile] | None) -> str:
    if not districts:
        return "none"
    counts = {}
    for profile in districts.values():
        counts[profile.district_type] = counts.get(profile.district_type, 0) + 1
    return ",".join(f"{key}:{counts[key]}" for key in sorted(counts))
```

- [ ] **Step 4: Use weighted pool in `generate_docket`**

In `generate_docket`, replace:

```python
    chosen = _scenario_ordered_templates(turn, scenario)
    if len(chosen) < count:
        rng = random.Random(seed * 1000 + turn)
        pool = [template_id for template_id in DEMO_TEMPLATE_IDS if template_id not in chosen]
        chosen.extend(rng.sample(pool, min(count - len(chosen), len(pool))))
```

with:

```python
    chosen = _weighted_template_pool(turn, seed, count, state, districts, scenario)
```

Keep `_scenario_ordered_templates` for any legacy tests or future fallback until no longer referenced.

- [ ] **Step 5: Run focused docket tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_docket_order_varies_by_seed_for_same_week tests/test_permit_office_rules.py::test_docket_weights_reflect_district_type_distribution -q
```

Expected: PASS.

- [ ] **Step 6: Run rules tests**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py -q
```

Expected: PASS. If old tests still pin exact demo order, rewrite them to assert determinism, valid template IDs, and coverage across a 12-week run.

- [ ] **Step 7: Commit**

```bash
git add toolbox/permit_office/profiles.py tests/test_permit_office_rules.py
git commit -m "feat: weight docket by district identity"
```

### Task 7: ArcGIS Persistence And Identity-First Symbology

**Files:**
- Modify: `toolbox/permit_office_arcgis/schema.py`
- Modify: `toolbox/permit_office_arcgis/store.py`
- Modify: `toolbox/permit_office_arcgis/symbology_config.py`
- Modify: `toolbox/permit_office_arcgis/geometry.py`
- Test: `tests/test_permit_office_symbology.py`
- Test: `tests/test_permit_office_arcgis_geometry.py`

- [ ] **Step 1: Write failing symbology tests**

In `tests/test_permit_office_symbology.py`, add:

```python
def test_district_layers_render_by_district_type_by_default():
    from toolbox.permit_office_arcgis.symbology_config import RENDER_FIELD_BY_LAYER_KEY

    assert RENDER_FIELD_BY_LAYER_KEY["districts"] == "district_type"


def test_identity_transition_symbol_values_are_configured():
    from toolbox.permit_office_arcgis.symbology_config import SYMBOLS_BY_FIELD

    identity_symbols = SYMBOLS_BY_FIELD["identity_state"]
    assert {"stable", "vulnerable", "contested", "converted", "overextended"} <= set(identity_symbols)
    assert "district_type" in SYMBOLS_BY_FIELD
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_permit_office_symbology.py::test_district_layers_render_by_district_type_by_default tests/test_permit_office_symbology.py::test_identity_transition_symbol_values_are_configured -q
```

Expected: FAIL because district renderer still uses `display_state` and no identity-state symbol table exists.

- [ ] **Step 3: Add schema fields**

In `toolbox/permit_office_arcgis/schema.py`, add these district fields after `district_type`:

```python
    ("prior_district_type", "TEXT", "Prior District Type", 32),
    ("identity_state", "TEXT", "Identity State", 32),
    ("contesting_cell_id", "TEXT", "Contesting District ID", 32),
    ("contesting_type", "TEXT", "Contesting Type", 32),
    ("transition_due_turn", "LONG", "Transition Due Week", None),
    ("buyout_pressure", "LONG", "Buyout Pressure", None),
    ("last_buyout_report", "TEXT", "Last Buyout Report", 512),
```

- [ ] **Step 4: Read and write new store fields**

In `toolbox/permit_office_arcgis/store.py`, extend district insert, read, and update field lists with:

```python
"prior_district_type",
"identity_state",
"contesting_cell_id",
"contesting_type",
"transition_due_turn",
"buyout_pressure",
"last_buyout_report",
```

When writing a `DistrictProfile`, map:

```python
profile.prior_district_type,
profile.identity_state,
profile.contesting_cell_id,
profile.contesting_type,
profile.transition_due_turn,
profile.buyout_pressure,
profile.last_buyout_report,
```

When reading, pass:

```python
prior_district_type=row[index] or "",
identity_state=row[index] or "stable",
contesting_cell_id=row[index] or "",
contesting_type=row[index] or "",
transition_due_turn=int(row[index] or 0),
buyout_pressure=int(row[index] or 0),
last_buyout_report=row[index] or "",
```

Use actual indices from the updated field list. Do not infer them from the snippet.

- [ ] **Step 5: Persist type ledger and pending follow-ups**

In `toolbox/permit_office_arcgis/store.py`, update `write_state` so `PermitGameState` includes JSON string rows for:

```python
"type_ledger": (json.dumps(state.type_ledger, sort_keys=True), None),
"pending_followups": (json.dumps(state.pending_followups, sort_keys=True), None),
```

Update `read_state` after the existing `stakeholder_heat` parsing:

```python
    if "type_ledger" in values and values["type_ledger"][0]:
        try:
            parsed = json.loads(values["type_ledger"][0])
        except ValueError:
            parsed = {}
        if isinstance(parsed, dict):
            state.type_ledger = {
                str(dtype): {str(key): int(value or 0) for key, value in entry.items()}
                for dtype, entry in parsed.items()
                if isinstance(entry, dict)
            }
    if "pending_followups" in values and values["pending_followups"][0]:
        try:
            parsed = json.loads(values["pending_followups"][0])
        except ValueError:
            parsed = {}
        if isinstance(parsed, dict):
            state.pending_followups = {str(key): str(value) for key, value in parsed.items()}
```

This uses the existing key/value `PermitGameState` table and does not require new schema fields.

- [ ] **Step 6: Configure identity-first symbols**

In `toolbox/permit_office_arcgis/symbology_config.py`, add:

```python
IDENTITY_STATE_SYMBOLS = {
    "stable": ([226, 232, 222, 0], "Stable Identity"),
    "vulnerable": ([210, 132, 78, 100], "Vulnerable"),
    "contested": ([188, 74, 70, 100], "Contested Buyout"),
    "converted": ([92, 150, 105, 100], "Recently Converted"),
    "overextended": ([150, 72, 90, 100], "Overextended"),
}
```

Update:

```python
SYMBOLS_BY_FIELD = {
    "display_state": DISPLAY_STATE_SYMBOLS,
    "district_type": DISTRICT_TYPE_SYMBOLS,
    "identity_state": IDENTITY_STATE_SYMBOLS,
}

RENDER_FIELD_BY_LAYER_KEY = {
    "districts": "district_type",
    "points": "display_state",
    "lines": "display_state",
    "zones": "display_state",
}
```

In `symbol_style_for`, add:

```python
    elif value in ("vulnerable", "contested", "converted", "overextended"):
        outline_color = [93, 48, 48, 100]
        outline_width = max(outline_width, 3.2)
```

- [ ] **Step 7: Preserve label readability**

In `toolbox/permit_office_arcgis/geometry.py`, keep district labels as district names. If `_configure_labels` currently labels by `cell_id`, update the district branch to prefer `$feature.district_name` with `cell_id` as fallback:

```python
label_expression = "$feature.district_name"
```

Keep existing compatibility handling for ArcGIS label APIs.

- [ ] **Step 8: Run focused symbology tests**

Run:

```bash
uv run pytest tests/test_permit_office_symbology.py::test_district_layers_render_by_district_type_by_default tests/test_permit_office_symbology.py::test_identity_transition_symbol_values_are_configured -q
```

Expected: PASS.

- [ ] **Step 9: Run ArcGIS adapter tests**

Run:

```bash
uv run pytest tests/test_permit_office_symbology.py tests/test_permit_office_arcgis_geometry.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add toolbox/permit_office_arcgis/schema.py toolbox/permit_office_arcgis/store.py toolbox/permit_office_arcgis/symbology_config.py toolbox/permit_office_arcgis/geometry.py tests/test_permit_office_symbology.py tests/test_permit_office_arcgis_geometry.py
git commit -m "feat: persist and render district identity state"
```

### Task 8: Reports, Documentation, And Full Verification

**Files:**
- Modify: `toolbox/permit_office/buyouts.py`
- Modify: `toolbox/permit_office/expiration.py`
- Modify: `docs/permit-office-turn-data-flow.md`
- Modify: `docs/permit-office-demo-script.md`
- Test: `tests/test_permit_office_rules.py`

- [ ] **Step 1: Add report text assertions**

Add:

```python
def test_buyout_reports_explain_target_bidder_and_reason():
    state = rules.CityState()
    districts = {
        "A": _district_for_buyout("A", "residential", 35, ["B"]),
        "B": _district_for_buyout("B", "mercantile", 82, ["A"]),
    }
    ledger = rules.rebuild_type_ledger(districts)
    ledger["mercantile"]["capital"] = 100
    ledger["mercantile"]["appetite"] = 20

    result = rules.resolve_buyout_round(state, districts, ledger, seed=2026)

    assert "A" in result.report or "A" in districts["A"].last_buyout_report
    assert "mercantile" in result.report.lower()
    assert any(phrase in result.report.lower() for phrase in ("bid", "leverage", "contested", "refused"))


def test_expiration_reports_hint_at_original_policy():
    state = rules.CityState()
    districts = {profile.cell_id: profile for profile in rules.generate_district_profiles(rows=1, cols=1, seed=2026)}
    item = rules.DocketItem("expire-event", "procession_route", "Licensed Procession Route", "LINE", 1)
    item.target_cell_ids = ["D0000"]

    result = rules.resolve_unattended_item(state, item, districts, seed=2026)

    assert "window" in result.report.lower()
    assert result.policy == "missed_window"
```

- [ ] **Step 2: Run tests to verify current report gaps**

Run:

```bash
uv run pytest tests/test_permit_office_rules.py::test_buyout_reports_explain_target_bidder_and_reason tests/test_permit_office_rules.py::test_expiration_reports_hint_at_original_policy -q
```

Expected: PASS if previous reports already satisfy this, otherwise FAIL with the missing phrase.

- [ ] **Step 3: Tighten buyout and expiration report copy**

If the report test fails, update `toolbox/permit_office/buyouts.py` so `_start_transition` sets:

```python
    target.last_buyout_report = (
        f"{target.name} entered contested buyout from {bidder.name}; "
        f"{bidder.district_type} bid cleared local leverage after weak prosperity and pressure."
    )
```

Update refusal report:

```python
            target.last_buyout_report = (
                f"{target.name} refused a {bidder.district_type} buyout bid; "
                f"local leverage remained high enough to resist."
            )
```

Update `toolbox/permit_office/expiration.py` missed-window report:

```python
            f"{item.title} window closed without office action; the original filing expired."
```

- [ ] **Step 4: Update turn-flow documentation**

In `docs/permit-office-turn-data-flow.md`, update the current week-advance section to include this order:

```markdown
1. Unresolved open/inspected items resolve through template-specific expiration policy.
2. Missed-window items expire cleanly; city-momentum items alter district pressure; bad momentum can seed later follow-up cases.
3. Feature lifecycle, recurring economy, network, hazard, housing, and population systems advance.
4. Contested buyout transitions resolve.
5. New buyout bids are evaluated for low-prosperity districts.
6. `CityState.turn` increments, AP resets, week 6 files the mid-season audit, and week 12 files the final audit.
```

- [ ] **Step 5: Update demo script**

In `docs/permit-office-demo-script.md`, replace six-week-specific language with 12-week language:

```markdown
The current design target is a 12-week civic season. The old six-week script remains useful as a short smoke path, but balance verification should use a 12-week route with AP scarcity and unresolved-item pressure.
```

- [ ] **Step 6: Run all tests**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 7: Run public API import smoke**

Run:

```bash
uv run python -c "from toolbox import arcpy_permit_office_rules as r; print(r.CityState().max_turns, hasattr(r, 'resolve_buyout_round'), hasattr(r, 'resolve_unattended_item'))"
```

Expected:

```text
12 True True
```

- [ ] **Step 8: Check git diff for accidental unrelated changes**

Run:

```bash
git status --short
git diff --stat
```

Expected: only files touched by this plan are modified. Preserve the pre-existing `README.md` edit unless the user explicitly asks to include it.

- [ ] **Step 9: Commit**

```bash
git add toolbox/permit_office/buyouts.py toolbox/permit_office/expiration.py tests/test_permit_office_rules.py docs/permit-office-turn-data-flow.md docs/permit-office-demo-script.md
git commit -m "docs: document district buyout turn flow"
```

## Final Verification

After all tasks are complete, run:

```bash
uv run pytest -q
git status --short
git log --oneline -8
```

Expected:

- pytest exits 0.
- Working tree contains no unexpected implementation changes.
- Recent commits correspond to the task commits above.

## Implementation Notes

- Use deterministic string seeds for all new RNG decisions.
- Keep hidden ledger values qualitative in player-facing text.
- Keep `cell_id` stable and machine-readable; use district names for labels and reports.
- Do not add a visible dashboard ledger.
- Do not enable ghost/informal features by default in the first pass.
- If a test wants a specific bid outcome, set district prosperity and ledger values explicitly in the test instead of depending on generated board randomness.
- If ArcGIS schema migrations need extra compatibility handling, keep missing-field defaults aligned with dataclass defaults.
