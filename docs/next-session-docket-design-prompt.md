# Next Session Prompt - Permit Office

Use this prompt to restart the next design/build session:

```text
We are continuing the Permit Office ArcGIS Pro / ArcPy game project.

Repo context to read first:
- README.md
- docs/current-status.md
- docs/permit-office-concept.md
- docs/permit-office-architecture.md
- docs/permit-office-prototype-smoke-test.md
- toolbox/arcpy_permit_office.pyt
- tests/test_permit_office_rules.py

Current state:
- Permit Office is the active product direction.
- Old Survey Sweeper / Containment / GUI spike work has been archived under archive/survey-sweeper-containment/.
- The pure Python Permit Office rules suite is the active automated regression target.
- The project already has docket templates, inspections, population/grievance, incidents, projects, active features, maintenance, audit findings, and ArcGIS schema/store coverage.
- Live ArcGIS Pro smoke-test results are still the main missing evidence.

Next major slice:
Run the ArcGIS Pro smoke test, record failures or friction, then tune the six-turn demo around the actual dashboard/map feel.

Default automated check:
python3 -m pytest tests/test_permit_office_rules.py -q
```
