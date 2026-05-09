# Delphi Panel — Implementation Plan Improvement Review

Date: 2026-05-08

Subject plan:

- `ideas/minesweeper-to-containment-implementation-plan.md`

Purpose:

- Run a second Delphi-style review focused on improving the staged ArcPy game implementation plan.
- Round 1: independent critique from multiple lenses.
- Round 2: reviewers received the plan plus unlabeled Round 1 synthesis.
- Round 3: voting on concrete recommendations.

No code was written during this review.

---

## Executive Summary

The panel strongly agreed that the plan is directionally correct:

- Start with **Survey Sweeper / Map Minesweeper** as the technical proof of loop.
- Evolve into **Containment Commander** as the main game.
- Add **Bufferlands-style powers** only after the selected-cell core works.

But the panel also found that the current plan overcommits by treating Stage 1, Stage 2, and multiple Stage 3 powers as one final MVP. The most important improvement is to rewrite the plan around **tiered acceptance criteria**:

1. **Minimum shippable:** polished Survey Sweeper.
2. **Target:** deterministic selected-cell Containment Commander.
3. **Stretch:** one or two Bufferlands-style GP powers.

The second major consensus is that an **early ArcGIS Pro feasibility spike** should happen before heavy implementation. The project must prove `.pyt` loading, action dropdowns, `GPFeatureLayer` selection handling, `FIDSet` behavior, OID-to-`cell_id` resolution, cursor updates, refresh, and field-driven symbology inside ArcGIS Pro before the rules/schema work grows too large.

---

## Round 1 — Independent Critique Synthesis

Five independent reviewers examined the implementation plan from different lenses:

- ArcGIS Pro / ArcPy feasibility.
- Game design and classroom demo quality.
- Software architecture / testing / sequencing.
- GIS pedagogy and geoprocessing legitimacy.
- Adversarial scope/risk critique.

### Round 1 Consensus Strengths

- The staged build order is correct: Survey Sweeper first, Containment Commander second, Bufferlands powers last.
- One controller tool, feature-class state, precomputed adjacency, map selections, GP messages, and symbology are the right ArcGIS Pro architecture.
- Pure Python rule tests before ArcPy integration are valuable.
- The framing “geoprocessing is the gameplay verb” is strong and should remain central.

### Round 1 Main Concerns

- The final MVP scope is too large.
- The controller action dropdown is too crowded.
- `state` and `protected` are overloaded and likely to cause confusion.
- The ArcGIS Pro integration risks are discovered too late in the current milestone sequence.
- Packaging, refresh, symbology, and schema-lock behavior are under-risked.
- Stage 3 powers risk bloat; `Clip Quarantine`, `Dissolve Safe Zone`, and actual `Erase` should not be required.
- The plan needs stronger GIS legitimacy: synthetic risk sources, assets, asset exposure scoring, learning objectives, and messages that explicitly name the GP operation used.

### Round 1 Key Suggested Changes

- Add Minimum / Target / Stretch acceptance tiers.
- Add an early ArcGIS Pro feasibility spike.
- Stage visible actions by scenario/stage.
- Define selection/OID-to-`cell_id` contract.
- Define `ensure_schema()` vs `assert_schema()`.
- Avoid deleting displayed feature classes during `New Game`.
- Separate `display_state` from domain fields.
- Split permanent `critical_asset` from temporary `defended` / protection fields.
- Make Containment deterministic and all-visible first.
- Promote demo seed/action script to a first-class deliverable.
- Cut/defer fog-of-war, real data, hexes, Feature Set drawing, PlayerActions table, probabilistic spread, Clip, Dissolve, and actual Erase dependency.

---

## Round 2 — Refined Recommendation Synthesis

Three reviewers received the plan plus the unlabeled Round 1 synthesis. They converged on a coherent revision direction.

### 1. Rewrite the Plan Around Acceptance Tiers

Replace the current single final MVP list with:

#### Minimum: Polished Survey Sweeper

Required if time is tight:

- Python toolbox loads in ArcGIS Pro.
- `New Game`, `Reveal / Scout`, `Flag / Mark`, `Show Score`, and `Reset` work.
- Board state is stored in `GameBoard`, `GameState`, `Adjacency`, and `ActionLog`.
- Player selects cells on the map as input.
- Clue counts, flags, win/loss state, GP messages, and symbology are clear.
- Known demo seed and scripted action path exist.
- No schema changes occur during ordinary reveal/flag actions.

#### Target: Selected-Cell Containment Commander

Only after Minimum is solid:

- `Scenario Mode = Containment Commander` works from the same controller/data model.
- Threat spread is deterministic and all-visible.
- `Scout`, `Treat / Clear`, `Place Barrier`, `Resolve Turn`, and `Show Score` work from selected cells.
- Fixed AP rules are implemented.
- Critical assets create visible stakes.
- Barriers and treatments visibly alter spread.
- A 5–10 turn scripted demo is playable in under 5 minutes.

#### Stretch: Bufferlands GP Powers

Only after Target is stable:

- `Buffer Defense` first.
- `Spatial Join Harvest / Score` second if an `Assets` layer exists.
- Optional `Erase`/`Suppress Hotspot` only if it stays simple.
- `Clip Quarantine` and `Dissolve Safe Zone` move to future ideas.

### 2. Add an Early ArcGIS Pro Feasibility Spike

Add a new early milestone before heavy implementation:

**Milestone 0.5 — ArcGIS Pro GP Interaction Spike**

Prove:

- `.pyt` loads in ArcGIS Pro.
- `GPString` `ValueList` action dropdown works.
- `GPFeatureLayer` parameter accepts the board layer.
- Selected feature IDs are readable from `Describe(layer).FIDSet`.
- Selected OIDs/FIDs can be resolved to stable `cell_id`.
- A cursor update changes a field.
- Derived output and/or `arcpy.RefreshLayer(...)` makes the map redraw.
- Field-driven symbology reacts to the updated field.
- GP messages are clear.

Exit criterion:

> Select a map cell, run a GP action, update its state field, and see the map change.

### 3. Add Explicit ArcPy Contracts

Add a new section to the plan: **ArcPy Implementation Contracts**.

Required contracts:

- **Stable identity:** gameplay uses `cell_id`, never durable `OBJECTID`.
- **Selection resolution:** map selection yields OIDs/FIDs; every action maps those to `cell_id`s before rule logic.
- **Schema:** split `ensure_schema()` from `assert_schema()`.
- **Reset/New Game:** create schema once where possible; clear/update rows instead of deleting displayed feature classes.
- **Indexing:** add indexes on `GameBoard.cell_id`, `Adjacency.cell_id`, `Adjacency.neighbor_id`, and `GameState.key`.
- **Memory workspace:** use action-specific `memory\\...` names; delete before/after reuse; never persist gameplay state in memory outputs.
- **Refresh:** mutating actions set derived output and call refresh as needed; gameplay remains verifiable in fields/logs if redraw lags.

### 4. Keep Architecture Lightweight but More Explicit

Adopt lightweight seams without building a generalized game framework:

- `ActionContext`
  - workspace
  - board layer
  - scenario/mode
  - action
  - selected `cell_id`s
  - current `GameState`
  - parameters such as radius/seed/difficulty
- `ActionResult`
  - status
  - changed cell IDs
  - score delta
  - updated state keys
  - GP messages
  - log payload
  - refresh flag
- `arcpy_game_store.py`
  - cursor read/write, selected-cell resolution, `GameState`, `ActionLog`
- `arcpy_game_display.py`
  - domain fields -> `display_state`
- `arcpy_game_scenarios.py`
  - tiny scenario presets, not a complex scenario engine
- `schema_version`
  - stored in `GameState`

### 5. Separate Domain State From Display State

Replace or redefine the current `state` field as `display_state`.

Rules should depend on domain fields such as:

- `is_hazard`
- `revealed`
- `flagged`
- `threat`
- `threat_level`
- `treated_turn`
- `barrier`
- `critical_asset`
- `defended_until_turn`
- `asset_value`

Symbology should depend on:

- `display_state`

This prevents cartographic categories from becoming fragile rule logic.

### 6. Fix Containment Semantics

Do not overload `protected`.

Use:

- `critical_asset` — permanent scenario-defined asset/loss condition.
- `asset_value` — scoring weight.
- `defended` or `defended_until_turn` — temporary/current player defense.
- `barrier` — spread blocker/modifier.
- `treated_turn` — last treatment turn.
- `lost_asset` — optional flag if threat reaches a critical asset.

Recommended Containment MVP rules:

- All cells visible.
- Deterministic spread only.
- 2 AP per turn.
- `Scout`, `Treat`, and `Place Barrier` cost 1 AP.
- `Resolve Turn` ends turn and costs 0 AP.
- `Treat` clears or suppresses a selected cell.
- `Barrier` blocks spread into selected cells.
- Spread infects top `N` candidate neighbors ranked by risk, then `cell_id` for stable tie-breaks.
- Win after 5–10 turns if critical assets survive and threat remains under threshold.
- Lose if threat reaches a critical asset or exceeds threshold.

### 7. Make GIS Legitimacy Concrete but Bounded

Add a **GIS Learning Objectives** section:

- Feature classes as durable game state.
- Attribute fields as model variables and symbology drivers.
- Map selection as GP input.
- Adjacency / `Touches` as clue/spread graph.
- Buffer / Select Layer By Location as defensive action.
- Spatial Join as asset exposure scoring.
- Symbology and labels as cartographic UI.
- GP messages as turn feedback.

Add tiny synthetic layers once the core loop is stable:

- `RiskSources`
  - synthetic road/river/industrial source/spill source.
- `Assets`
  - town center, habitat core, water intake, school, infrastructure.

Use these to support:

- spatially biased hazards or susceptibility,
- asset exposure scoring,
- Spatial Join scoring,
- a stronger class-demo story.

### 8. Promote the Demo Script Early

`docs/demo-script.md` should become a milestone deliverable, not final polish.

For each demo scenario, document:

- scenario name,
- board size,
- seed,
- exact cells to select,
- expected action result,
- expected GP message,
- expected visual state.

Survey Sweeper script should include:

- known safe reveal,
- known clue reveal,
- known flood reveal if implemented,
- known flag example,
- known win/loss path or near-win state.

Containment script should include:

- first treatment,
- first barrier,
- expected spread after first `Resolve Turn`,
- expected score/status message.

---

## Round 3 — Voting Results

Five panelists voted on eleven recommendations.

Vote scale:

- Strong adopt
- Adopt
- Conditional
- Reject

### Vote Tally

#### A. Replace single final MVP with tiered Minimum/Target/Stretch acceptance

- Strong adopt: 5
- Adopt: 0
- Conditional: 0
- Reject: 0

**Decision: Strong adopt.**

#### B. Add early ArcGIS Pro feasibility spike

- Strong adopt: 5
- Adopt: 0
- Conditional: 0
- Reject: 0

**Decision: Strong adopt.**

#### C. Stage action dropdown by scenario/stage

- Strong adopt: 5
- Adopt: 0
- Conditional: 0
- Reject: 0

**Decision: Strong adopt.**

#### D. Add explicit ArcPy contracts

- Strong adopt: 5
- Adopt: 0
- Conditional: 0
- Reject: 0

**Decision: Strong adopt.**

#### E. Add lightweight architecture contracts/modules

- Strong adopt: 0
- Adopt: 5
- Conditional: 0
- Reject: 0

**Decision: Adopt, with anti-framework caution.**

#### F. Separate `display_state` from domain fields; split `critical_asset` from defended/protected

- Strong adopt: 5
- Adopt: 0
- Conditional: 0
- Reject: 0

**Decision: Strong adopt.**

#### G. Make Containment deterministic and all-visible first; fixed AP; selected-cell Treat/Barrier before Feature Set drawing

- Strong adopt: 5
- Adopt: 0
- Conditional: 0
- Reject: 0

**Decision: Strong adopt.**

#### H. Promote demo seed/action script to first-class deliverable early

- Strong adopt: 5
- Adopt: 0
- Conditional: 0
- Reject: 0

**Decision: Strong adopt.**

#### I. Add GIS legitimacy layer

- Strong adopt: 1
- Adopt: 4
- Conditional: 0
- Reject: 0

**Decision: Adopt strongly, but keep bounded.**

#### J. Scope cuts/defer list

- Strong adopt: 5
- Adopt: 0
- Conditional: 0
- Reject: 0

**Decision: Strong adopt.**

#### K. Stage 3 priority: Buffer Defense first; Spatial Join Harvest second if Assets exists; Erase/Suppress optional; Clip/Dissolve future only

- Strong adopt: 0
- Adopt: 5
- Conditional: 0
- Reject: 0

**Decision: Adopt.**

---

## Final Ranked Plan Edits

Synthesized from all Round 3 top-10 rankings.

### 1. Add mandatory ArcGIS Pro feasibility spike first

Before serious implementation, prove:

- `.pyt` load,
- action dropdown,
- selected `GPFeatureLayer`,
- `FIDSet` reading,
- OID/FID -> `cell_id`,
- cursor update,
- derived output / `RefreshLayer`,
- field-driven symbology/labels.

### 2. Replace single MVP with Minimum / Target / Stretch tiers

This is the central scope-control correction.

### 3. Define explicit ArcPy contracts

Add stable identity, selection, schema, reset, indexing, memory, and refresh contracts.

### 4. Make Survey Sweeper the reliable fallback endpoint

Survey Sweeper must be playable, polished, scripted, and shippable if every later stage slips.

### 5. Make Containment deterministic/all-visible/selected-cell-first

No fog, probability, Feature Set drawing, complex durations, or real-time behavior in the first Containment version.

### 6. Separate `display_state` from domain fields

Use domain fields for rules and `display_state` for symbology.

### 7. Split `critical_asset` from temporary defense/protection

Avoid overloaded `protected` semantics.

### 8. Stage the action dropdown by mode and implementation stage

Only expose actions that are available and relevant.

### 9. Promote demo seed/action script early

Use it as both demo backbone and regression harness.

### 10. Lock scope deferrals into the plan

Explicitly defer:

- `Clip Quarantine`,
- `Dissolve Safe Zone`,
- actual `Erase` dependency,
- fog-of-war,
- hexes before squares,
- real data,
- `PlayerActions`,
- Feature Set drawing before selected-cell actions,
- probabilistic spread,
- complex durations,
- persistent `Barriers` / `Treatments` feature classes unless needed later.

### 11. Add lightweight architecture seams, not a framework

Use `ActionContext`, `ActionResult`, store helpers, display mapper, tiny scenario definitions, and `schema_version`. Do not build a generalized game engine.

### 12. Add bounded GIS legitimacy layer

Add learning objectives, synthetic `RiskSources`/`Assets`, spatial bias, asset exposure scoring, field aliases, and GP messages that name operation + gameplay effect.

### 13. Prioritize Buffer Defense as first Stage 3 power

Then add Spatial Join Harvest only if the `Assets` layer already exists and scoring is stable. Treat Erase/Suppress as optional. Move Clip/Dissolve to future ideas.

### 14. Add packaging/refresh/symbology smoke tests earlier

Do not wait until the final milestone to test whether layers, paths, labels, symbology, refresh, and project reopen behavior work.

---

## Hidden Concerns Raised in Voting

The voting panel raised several extra risks not directly on the ballot.

### ArcGIS Pro execution-state fragility

The plan should define behavior for:

- renamed layers,
- stale selections,
- reopened projects,
- changed paths,
- partial prior state after failed actions,
- schema already existing,
- locks persisting after table views or failed tools.

### Refresh/state synchronization risk

The plan should define what “state updated and visible” means after each action:

- field updated,
- symbology updated,
- labels updated,
- selection cleared or intentionally retained,
- GP message emitted,
- `ActionLog` row written,
- `GameState.last_message` updated.

### Classroom pacing risk

Even if technically successful, the demo can feel slow if each turn requires too many clicks/parameter edits. The demo script should include:

- exact operator flow,
- expected runtime per action,
- expected visual feedback,
- fallback screenshots or precomputed states if refresh misbehaves.

### Recovery / fallback states

Add a simple recovery policy:

- `Reset` clears rows and reinitializes state.
- `Rebuild Workspace` or manual cleanup is an explicit destructive maintenance action if schema becomes incompatible.
- Failed actions should leave enough log/message context to recover.

---

## Recommended Replacement Milestone Structure

### Milestone 0 — Planning Freeze and Scope Gates

Deliverables:

- Updated plan with Minimum / Target / Stretch tiers.
- Deferred-feature list.
- Agreement that polished Survey Sweeper is shippable.

### Milestone 0.5 — ArcGIS Pro Feasibility Spike

Deliverables:

- Minimal `.pyt`.
- Tiny board layer.
- Action dropdown.
- Selection/FIDSet read.
- OID-to-`cell_id` resolution.
- Cursor field update.
- Refresh/symbology proof.

### Milestone 1 — Pure Survey Sweeper Rules

Deliverables:

- grid board model,
- stable `cell_id`,
- adjacency,
- hazard placement,
- neighbor counts,
- reveal,
- flag,
- win/loss,
- optional flood reveal,
- pure Python tests.

### Milestone 2 — Schema / Store / Display Foundation

Deliverables:

- `ensure_schema()`,
- `assert_schema()`,
- `schema_version`,
- `GameBoard`,
- `GameState`,
- `Adjacency`,
- `ActionLog`,
- indexes,
- reset/clear rows behavior,
- `display_state` mapper.

### Milestone 3 — Playable Survey Sweeper in ArcGIS Pro

Actions:

- `New Game`,
- `Reveal / Scout`,
- `Flag / Mark`,
- `Show Score`,
- `Reset`.

Exit criterion:

- Player can complete a Survey Sweeper game in ArcGIS Pro.

### Milestone 4 — Survey Sweeper Polish / Fallback Lock

Deliverables:

- `.lyrx` symbology,
- labels,
- better messages,
- known seed,
- exact demo script,
- quickstart,
- manual smoke test,
- packaging/refresh check.

Exit criterion:

- If development stopped here, the project could still be submitted.

### Milestone 5 — Pure Containment Rules

Deliverables:

- deterministic spread,
- all-visible model,
- fixed AP rules,
- treatment,
- barrier,
- critical assets,
- scoring,
- win/loss,
- golden scenario tests.

### Milestone 6 — Selected-Cell Containment Commander in Pro

Actions:

- `Scout`,
- `Treat / Clear`,
- `Place Barrier`,
- `Resolve Turn`,
- `Show Score`,
- `Reset`.

Exit criterion:

- 5–10 turn deterministic Containment scenario works in under 5 minutes.

### Milestone 7 — GIS Legitimacy Layer

Deliverables:

- GIS learning objectives,
- synthetic `RiskSources`,
- synthetic `Assets`,
- asset exposure scoring,
- field aliases,
- GP messages naming operation + effect.

### Milestone 8 — Bufferlands Stretch Powers

Priority order:

1. `Buffer Defense`.
2. `Spatial Join Harvest / Score`, if `Assets` exists.
3. Optional `Suppress Hotspot` / `Erase Hotspot`.

Future only:

- `Clip Quarantine`,
- `Dissolve Safe Zone`.

### Milestone 9 — Final Packaging / Class Demo

Deliverables:

- README update,
- quickstart,
- exact demo script,
- smoke-tested project package if feasible,
- fallback plan if package fails,
- final manual checklist.

---

## Final Recommendation

Revise the existing plan rather than replacing it. The core direction is correct, but the plan should be made more ruthless and implementation-safe.

Highest-priority edits:

1. Add tiered acceptance criteria.
2. Add early ArcGIS Pro feasibility spike.
3. Add ArcPy interaction contracts.
4. Make Survey Sweeper the minimum shippable endpoint.
5. Make Containment deterministic/all-visible/selected-cell-first.
6. Defer risky Stage 3 and UI-heavy features.
7. Promote exact demo seed/action scripts early.
8. Add bounded GIS legitimacy through synthetic assets/risk sources and operation-aware messages.

The resulting project target should be:

> **A polished Survey Sweeper fallback, a deterministic selected-cell Containment Commander target, and one visible Buffer Defense wow move if time allows.**
