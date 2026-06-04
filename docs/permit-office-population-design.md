# Permit Office Population and Dissatisfaction Design

Date: 2026-05-15

This records the first implementation slice for district population composition and local dissatisfaction.

## District Model

District archetype remains the static land-use fit layer: residential, mercantile, industrial, civic, academic, or natural.

Population composition is separate and dynamic:

- `population`: total visible district population.
- `population_mix_json`: citizen-group pressure bands from 0 to 3.
- `dissatisfaction_json`: local grievance bands from 0 to 4.
- `incident_state`: no incident, complaints, petition, protest, strike, or noncompliance.
- `incident_group`: group currently driving the visible incident.
- `public_profile`: census-style visible description.

The first citizen groups are families, elders, students, commuters, workers, artists, vendors, homeowners, renters, civil servants, developers, and conservationists.

## Docket Behavior

Permit templates now carry supporter groups, concerned groups, growth groups, decline groups, and a light named contact. These are used for hints, local grievance changes, pressure drift, and report flavor.

Dashboard cards stay qualitative:

- Before targeting, cards show the regular permit preview.
- After preview, cards add a target census note based on selected districts.
- Inspection reveals likely supporters, likely objectors, highest local grievance, and service-capacity wording without exposing exact formulas.

## Dissatisfaction and Incidents

Dissatisfaction is local and group-specific. It differs from citywide friction: citywide friction only rises when a local grievance becomes administratively visible as an incident.

High grievance creates a civic incident follow-up docket item. In the first slice, incidents are civic rather than catastrophic: complaints, petitions, protests, strikes, and noncompliance waves. Riots, recalls, lawsuits, and department revolts remain later design space.

Incident response cards reuse the existing dashboard actions:

- Approve: formal response.
- Approve + Mitigate: settlement or service response.
- Deny: defer the incident and raise friction plus group heat.

## Population Drift

Approvals can move population and group bands slightly when a template has growth or decline groups. Failures can reverse growth pressure. Turn advance applies small deterministic drift:

- High-activity, low-exposure, low-friction districts grow.
- High-exposure, high-friction, or incident districts lose population.
- Low services can add local grievance pressure.

Population is now visible in dashboard summaries and scorecard messages, but it is not yet a primary audit win condition.
