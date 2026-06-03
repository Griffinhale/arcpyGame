# Permit Office Current Status

Date: 2026-06-03

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
- 12-week attention-scarce pacing: 2 AP per week, ordinary permit denials cost 0 AP, week 6 is the mid-season audit, and closing week 12 files the final audit.
- Template-specific unattended-item expiration: missed windows, city momentum, mandatory carryovers, and pending follow-up cases.
- Hidden district type ledger plus deterministic contested buyout/refusal/conversion rules for low-prosperity districts.
- District-weighted docket generation that varies by seed and district type distribution while preserving mandatory follow-up priority.
- ArcGIS district identity persistence and district-type-first symbology, with district-name labels.

## Missing

- Recorded live ArcGIS Pro smoke-test results from `docs/permit-office-prototype-smoke-test.md`.
- Final cold-start demo instructions for a clean ArcGIS Pro project.
- Confirmation that map refresh, layer addition, and Tkinter dashboard behavior are reliable on the target presentation machine.
- Full `pytest` verification in this environment; the current environment cannot spawn `pytest`, so direct smoke calls and `compileall` were used for the district-identity pass.
- Resolution for the two known direct no-arg smoke failures around `families` dissatisfaction assertions.

## Iterate Later

- Dashboard layout and copy polish after the live smoke test identifies real friction.
- Docket template balance and score tuning for a fair 12-week route that can reliably PASS with competent play.
- Revenue/city-health clarity, help/start/end-game flow, final scorecard auto-display, and report/docket/tab layout polish.
- Deeper symbology and map presentation polish for `PermitDistricts`, `PermitPoints`, `PermitLines`, and `PermitZones`.
- Playtest whether hidden buyout pressure is legible enough through reports and map symbology without exposing a raw ledger.
- If live display staleness remains, revisit the ArcPy refresh-only branch as a reliability fix, not as a confirmed speed improvement.
- Possible `store.py` split if persistence grows beyond the current file-size budget.

## Validation

Run the active pure Python checks with:

```bash
python3 -m pytest tests/test_permit_office_rules.py -q
```

If `pytest` is unavailable, the last implementation pass used:

```bash
python3 -m compileall toolbox/permit_office toolbox/permit_office_arcgis docs tests
uv run python -c "from toolbox import arcpy_permit_office_rules as r; print(r.CityState().max_turns, hasattr(r, 'resolve_buyout_round'), hasattr(r, 'resolve_unattended_item'))"
```

The seed `2026` route is now a 12-week balance target; the six-week route in
`docs/permit-office-demo-script.md` remains a short ArcGIS smoke path.

Manual ArcGIS validation should follow:

```text
docs/permit-office-prototype-smoke-test.md
```
