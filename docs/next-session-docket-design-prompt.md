# Next Session Prompt - Permit Office Docket Design

Use this prompt to restart the next design/build session:

```text
We just implemented the Permit Office prototype slice for the ArcGIS Pro / ArcPy game project.

Repo context to read first:
- README.md
- ideas/permit-office-city-sim-concept-notes.md
- docs/permit-office-prototype-smoke-test.md
- toolbox/arcpy_permit_office.pyt
- toolbox/arcpy_permit_office_rules.py
- tests/test_permit_office_rules.py

Current state:
- The project pivoted from Survey Sweeper / Containment toward Permit Office, a dryly absurd municipal city sim.
- The player reviews a rotating docket, selects districts, previews proposed point/line/polygon geometries, inspects, approves, approves with mitigation, denies, and advances turns.
- The first prototype creates generated districts, support feature classes, a persistent Tkinter dashboard, effect report popups, command logging, action logging, and pure-Python rules/tests.
- Local rule tests pass under ArcGIS Pro Python.
- Live ArcGIS Pro smoke testing is still needed with docs/permit-office-prototype-smoke-test.md.

Next major slice:
Design and implement the first real docket/balance layer.

Goals:
1. Define the first 8-10 docket templates.
2. For each template, specify geometry type, target rules, preview text, inspection reveal, approval effects, mitigation effects, denial/carryover behavior, lifespan, and report flavor.
3. Define the first four district archetypes and their effect modifiers.
4. Build a deterministic 6-turn golden demo sequence with reliable surprises.
5. Add tests for docket generation, target validation, template effects, carryover, audit milestones, and scorecard outcomes.
6. Keep the dashboard-map loop intact; do not rewrite the architecture unless ArcGIS Pro smoke testing exposes a concrete blocker.

Recommendation:
Start by running the ArcGIS Pro smoke test, record any dashboard/map-refresh failures, then tune the docket templates around the actual feel of one full turn.
```

