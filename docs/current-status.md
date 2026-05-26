# Permit Office Current Status

Date: 2026-05-16

## Purpose

This file is the quick project status source for Permit Office. It separates the implemented prototype from the remaining validation and cleanup work so new sessions do not restart from the older Survey Sweeper / Containment direction.

## Implemented

- Pure Python gameplay package in `toolbox/permit_office/`, with dataclasses, catalogs, district generation, docket generation, inspections, decisions, turns, scorecards, and audit findings.
- Content systems for docket templates, stakeholder pressure, population mix, local dissatisfaction, civic incidents, service gaps, housing, hazards, projects, maintenance, and feature lifecycle.
- ArcGIS adapter package in `toolbox/permit_office_arcgis/`, covering schema creation, store/read/write helpers, generated district geometry, proposal geometry, proposal activation, map refresh hooks, and the Tkinter dashboard.
- Seed `2026` six-turn golden route documented in `docs/permit-office-demo-script.md`, with pure Python regression coverage for the route state and scorecard.
- Thin ArcGIS toolbox entrypoint in `toolbox/arcpy_permit_office.pyt`.
- Compatibility facade in `toolbox/arcpy_permit_office_rules.py` for tests and toolbox loading.
- Active automated regression suite in `tests/test_permit_office_rules.py`.

## Missing

- Recorded live ArcGIS Pro smoke-test results from `docs/permit-office-prototype-smoke-test.md`.
- Final cold-start demo instructions for a clean ArcGIS Pro project.
- Confirmation that map refresh, layer addition, and Tkinter dashboard behavior are reliable on the target presentation machine.
- Refresh/cache spike comparison results from `docs/permit-office-refresh-spike-benchmark.md`.

## Iterate Later

- Dashboard layout and copy polish after the live smoke test identifies real friction.
- Docket template balance and report wording for a short demo rather than a broad simulation sandbox.
- Symbology and map presentation polish for `PermitDistricts`, `PermitPoints`, `PermitLines`, and `PermitZones`.
- Possible `store.py` split if persistence grows beyond the current file-size budget.

## Validation

Run the active pure Python checks with:

```bash
python3 -m pytest tests/test_permit_office_rules.py -q
```

The seed `2026` golden route is covered there and should remain `CONDITIONAL` with the documented scorecard.

Manual ArcGIS validation should follow:

```text
docs/permit-office-prototype-smoke-test.md
```

The archived Survey Sweeper / Containment tests are historical and are not part of the active default validation path.
