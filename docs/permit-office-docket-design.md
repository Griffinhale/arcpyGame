# Permit Office Docket Design

Date: 2026-05-15

This records the first real docket/balance layer for the Permit Office prototype.

## Card Shape

Docket cards are small case files. Each template carries:

- applicant/stakeholder group
- category and geometry type
- target selection rule
- AP and money cost, plus mitigation cost
- fuzzy pre-inspection preview
- inspection reveal and risk band
- approval and spillover effects
- denial and ignored-case heat
- approved-permit failure mode and failure effects
- enforcement follow-up behavior when heat rises

The UI should continue to sound like dry municipal paperwork: legible civic management with procedural absurdity in the margins.

## Permit Families

Potential permit families to draw from:

- Transit and roads: public transit pilots, private roads, corridor closures, bridges, curb allocations.
- Events: festivals, worship days, parties, parades, marches, vigils, processions.
- Utilities: plumbing, power, drainage, streetlights, telecom trenches, emergency repairs.
- Land and natural resources: mining, forestry, rewilding, natural reserve conversion, zoning changes.
- Education and parks: schools, daycare, playgrounds, recreation fields, park annexes.
- Business, nonprofit, and vendors: storefronts, nonprofits, markets, food carts, street vending.
- Residential and building: additions, disputes, demolitions, renovations, contractor waivers.
- Public safety and departments: fire, police, EMS, inspections, department budget escalations.
- Infrastructure upkeep: roads, water, bridges, maintenance packages, deferred repairs.
- Culture and branding: public art, museums, memorials, city branding, merchandise licenses.

## Demo Shortlist

The six-week demo uses these ten normal templates, with three items per week:

- `connector_corridor`: transit/roads, line, access gain with construction failure risk.
- `procession_route`: event, line, culture gain with crowd-control risk.
- `utility_expansion_trench`: utility, line, risk reduction with outage risk.
- `natural_reserve_conversion`: land use, polygon, culture/risk upside with boundary dispute risk.
- `mixed_use_rezoning`: development, polygon, prosperity gain with zoning appeal risk.
- `child_development_park_annex`: education/parks, point, family services with staffing risk.
- `street_vendor_compact`: business/vendor, point, prosperity/culture with unlicensed spillover risk.
- `contractor_renovation_waiver`: residential, point, faster work with inspection failure risk.
- `fire_budget_escalation`: department/public safety, polygon, risk reduction with coverage gap risk.
- `public_art_museum_grant`: culture/branding, point, culture gain with procurement scandal risk.

`unpermitted_followthrough` is a generated enforcement template. It appears when a stakeholder group's heat reaches the threshold.

## Consequence Model

Rejected and ignored permits add stakeholder heat. Heat is not a citywide audit metric; it is a pressure layer that can spawn enforcement follow-up cards. Enforcement cards reinterpret the existing buttons:

- Approve: enforce the order.
- Approve + Mitigate: settle or retroactively permit under conditions.
- Deny: defer enforcement.

Approved permits can still fail. Failure chance is deterministic from seed and depends on:

- inspection risk band
- district archetype fit
- service capacity
- current district risk
- mitigation

The first district archetype set is residential, mercantile, industrial, civic, academic, and natural.
