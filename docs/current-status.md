# Permit Office Current Status

Date: 2026-06-04

## Purpose

This file is the quick project status source for Permit Office. It separates the implemented prototype from the remaining validation and cleanup work so new sessions stay focused on the municipal permit office archetype.

## Implemented

- Pure Python gameplay package in `toolbox/permit_office/`, with dataclasses, catalogs, district generation, docket generation, inspections, decisions, turns, scorecards, and audit findings.
- Content systems for docket templates, stakeholder pressure, population mix, local dissatisfaction, civic incidents, service gaps, housing, hazards, projects, maintenance, and feature lifecycle.
- ArcGIS adapter package in `toolbox/permit_office_arcgis/`, covering schema creation, store/read/write helpers, generated district geometry, proposal geometry, proposal activation, map refresh hooks, and the Tkinter dashboard.
- Seed `2026` smoke route documented in `docs/permit-office-demo-script.md`; the current balance target is a 12-week civic season with pure Python regression coverage for pacing, docket generation, and scorecard behavior.
- Thin ArcGIS toolbox entrypoint in `toolbox/arcpy_permit_office.pyt`.
- Compatibility facade in `toolbox/arcpy_permit_office_rules.py` for tests and toolbox loading.
- Active automated regression suite in `tests/test_permit_office_rules.py`.
- Current turn/data-flow reference in `docs/permit-office-turn-data-flow.md`.
- Refresh/cache spike interpretation in `docs/permit-office-refresh-spike-benchmark.md`: main and ArcPy refresh timings were close, while the SDK add-in strategy was slower.
- ArcGIS pane arrangement spike in `docs/arcgis-panel-automation-spike.md`: startup repairs layers and opens the dashboard, but does not automate Contents/Geoprocessing pane layout from Python.
- 12-week attention-scarce pacing: 2 AP per week, ordinary permit denials cost 0 AP, week 6 is the mid-season audit, and closing week 12 files the final audit.
- Template-specific unattended-item expiration: missed windows, city momentum, mandatory carryovers, and pending follow-up cases.
- Hidden district type ledger plus deterministic contested buyout/refusal/conversion rules for low-activity districts.
- Buyout legibility closure note in `docs/buyout-legibility-playtest.md`: reports identify target, bidder, reason, and stabilization hint; richer multi-bid negotiation remains follow-up scope.
- District-weighted docket generation that varies by seed and district type distribution while preserving mandatory follow-up priority.
- ArcGIS district identity persistence and district-type-first symbology, with district-name labels.
- Map symbology spike in `docs/map-symbology-spike.md`: districts render by identity, support layers render by workflow/detail state, and richer bivariate renderers are deferred until live ArcGIS evidence proves they are needed.
- City health now uses Activity, Friction, Trust, Exposure, Services, and Dissatisfaction; legacy district fields are migrated into the renamed persisted fields.
- Selected applications now show decision lanes, selected-case exhibit controls, and compact recurring revenue/upkeep/net forecasts.
- Fresh saves open into a start/help overlay with seed-based New Game flow, while End Game closes the dashboard without clearing geodatabase state.
- Closing week 12 automatically records an inline final audit receipt with PASS/CONDITIONAL/FAIL flavor text.

## Missing

- Recorded live ArcGIS Pro smoke-test results from `docs/permit-office-prototype-smoke-test.md`.
- Final cold-start demo instructions for a clean ArcGIS Pro project.
- Confirmation that map refresh, layer addition, and Tkinter dashboard behavior are reliable on the target presentation machine.
- Final cold-start validation of the legacy ArcGIS field migration on an existing `.gdb`.

## Iterate Later

- Docket template balance and score tuning for a fair 12-week route that can reliably PASS with competent play.
- Dashboard layout, report/docket/tab copy, and live scorecard presentation tuning after ArcGIS smoke testing identifies real friction.
- Live ArcGIS screenshots or notes for `PermitDistricts`, `PermitPoints`, `PermitLines`, and `PermitZones` readability.
- Live-check whether buyout pressure, contested districts, and converted districts are visually legible in ArcGIS Pro without exposing a raw ledger.
- If live display staleness remains, revisit the ArcPy refresh-only branch as a reliability fix, not as a confirmed speed improvement.
- Possible `store.py` split if persistence grows beyond the current file-size budget.

## Validation

Run the active pure Python checks with:

```bash
python3 -m pytest -q
```

If the system Python environment does not have `pytest` installed, install the
development requirements first or run the suite through `uv run pytest -q`.

The seed `2026` route is now locked as a 12-week balance target that should end
with a final audit `PASS`; the six-week route in
`docs/permit-office-demo-script.md` remains a short ArcGIS smoke path.

Manual ArcGIS validation should follow:

```text
docs/permit-office-prototype-smoke-test.md
```
