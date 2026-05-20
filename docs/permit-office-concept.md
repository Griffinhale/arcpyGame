# Permit Office Concept

Date: 2026-05-14

Purpose: capture the active concept direction for Permit Office as the repo's main ArcGIS Pro / ArcPy game.

## Current Working Concept

A turn-based city management / planning sim played through ArcGIS Pro and ArcPy, framed as a dryly absurd municipal permit office.

The player reviews a rotating docket of permit applications, civic incidents, and development proposals. They approve, deny, inspect, or otherwise process items, usually by selecting districts on the map. Approved items can spawn businesses, services, events, institutions, or hazards as support features. These then affect the host district and nearby districts through spatial spillover.

The main player experience should be a simple sim loop with surprising but legible city consequences, not a pure GIS demo and not primarily a deduction puzzle.

## Tone and Player Fantasy

- Tone: dry municipal absurdism.
- Player role: permit office / audit-facing planning bureaucracy, not all-powerful mayor.
- Fantasy: shape the city through paperwork, approvals, inspections, denials, and official reports.
- The city should sometimes feel strange, but the game should remain playable as a civic sim.

## Core Loop

1. A new turn presents a small rotating docket.
2. The player selects one or more districts or reviews map context.
3. The player approves, denies, inspects, or responds to docket items.
4. Approved permits may spawn support features such as businesses, clinics, festivals, factories, shrines, housing, transit stops, incidents, or public works.
5. ArcPy resolves host-district effects and spatial spillover.
6. District attributes, city metrics, support features, and `display_state` values update.
7. A dry official report summarizes outcomes.
8. The audit clock advances toward a pass/fail or score result.

## Design Direction Chosen So Far

- Primary tension should include management, expansion, crisis control, and light inference.
- The central game promise is not "solve the hidden cult"; hidden district behavior can exist as seasoning.
- Main fun should come from event variety and watching the city respond to permit decisions.
- Outcomes should be surprising but legible in hindsight.
- Player information should be partial: visible district traits plus uncertain side effects.
- MVP should favor a few clear metrics and richer docket events over many shallow systems.
- First prototype success means one satisfying turn loop, not a full short game.

## Metrics and Audit

Likely audit backbone:

- prosperity
- unrest
- health or risk
- culture

Secondary or later metrics may include:

- money
- population
- services
- infrastructure

The audit should primarily judge city metrics rather than requiring the player to solve a mystery. A final report can still comment on patterns, contradictions, and bureaucratic justifications.

## Map and Data Model Direction

MVP should use one main playable polygon layer, with support features for permits/events/assets.

Likely layers/tables:

- `Districts` or `GameBoard`: main playable polygons.
- `PermitFeatures`: spawned businesses, events, services, hazards, or institutions.
- `GameState`: turn, audit status, citywide metrics, budget/AP.
- `Docket`: current turn applications/incidents/proposals.
- `ActionLog` or `UICommand`: durable command and report history.

The project can still model parcel/block/district scale conceptually, but the first build should avoid multiple nested polygon layers unless needed later.

## ArcGIS / ArcPy Fit

The concept should use ArcGIS operations mostly under the hood:

- Map selections choose target districts.
- Buffers model spillover from spawned permit features.
- Adjacency drives neighborhood reactions.
- Spatial joins or summary statistics support inspections and audit reports.
- Cursor updates mutate district metrics and display fields.
- Unique-value symbology on `display_state` renders visible city condition.
- Tkinter can act as a docket/dashboard/controller.

Possible later operations:

- Dissolve for mergers, consolidation, or district aggregation.
- Joins for mergers/acquisitions, service coverage, or audit summaries.
- Clip/intersect for targeted intervention zones.

## Open Design Questions

- What exactly is a docket item: spawned feature, direct district modifier, temporary incident, or mixed schema?
- How much forecast information should the player see before approval?
- Should inspection be a core action that reduces uncertainty?
- How should approve/deny decisions differ mechanically?
- What are the first 6-10 docket item types?
- What should a single "satisfying turn loop" demonstrate in ArcGIS Pro?
- How explicit should GIS operation names be in UI vs logs/messages?
