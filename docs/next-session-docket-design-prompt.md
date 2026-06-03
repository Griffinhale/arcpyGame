# Next Session Prompt - Permit Office

Use this prompt to restart the next design/build session:

```text
We are continuing the Permit Office ArcGIS Pro / ArcPy game project.

Repo context to read first:
- README.md
- docs/current-status.md
- docs/permit-office-concept.md
- docs/permit-office-architecture.md
- docs/permit-office-turn-data-flow.md
- docs/permit-office-prototype-smoke-test.md
- toolbox/arcpy_permit_office.pyt
- tests/test_permit_office_rules.py

Current state:
- Permit Office is the active product direction.
- The pure Python Permit Office rules suite is the active automated regression target.
- The project already has docket templates, inspections, population/grievance, incidents, projects, active features, maintenance, audit findings, ArcGIS schema/store coverage, 12-week pacing, explicit expiration policies, hidden district type pressure, district-weighted dockets, and first-pass buyout transitions.
- The refresh/cache spike comparison has been interpreted: main and ArcPy refresh timings were close, while the SDK add-in strategy was slower.
- Live ArcGIS Pro smoke-test results and presentation-machine refresh behavior are still the main missing evidence.
- The local environment used for the district-identity pass could not spawn `pytest`; use the direct smoke checks in `docs/current-status.md` if pytest is still unavailable.

Next major slice:
Run the ArcGIS Pro smoke test, record failures or friction, then tune the 12-week balance and remaining dashboard clarity around the actual dashboard/map feel. The old six-week route is now only a short smoke path. Only revisit refresh implementation details if stale display behavior, flicker, or lock errors show up during the live run.

Default automated check:
python3 -m pytest tests/test_permit_office_rules.py -q
```
