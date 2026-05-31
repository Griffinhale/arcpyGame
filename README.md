# Permit Office

Permit Office is the active direction for this repo: an ArcGIS Pro / ArcPy geoprocessing game about running a municipal permit office. The player reviews docket items, selects districts on the map, previews proposed point/line/polygon work, inspects cases, approves or denies applications, and advances through audit turns while the city changes in response.

The project uses ArcGIS Pro as the game engine:

- Feature classes hold districts, permit features, projects, docket rows, commands, and logs.
- Map selections are player input.
- ArcPy geometry and cursor operations resolve proposals, spillover, district state, and persistence.
- Tkinter provides the docket dashboard.
- Pure Python rules keep gameplay testable outside ArcGIS Pro.

## Active Code

- `toolbox/arcpy_permit_office.pyt`: ArcGIS Pro toolbox entrypoint.
- `toolbox/arcpy_permit_office_rules.py`: compatibility facade for the pure rules package.
- `toolbox/permit_office/`: ArcPy-free gameplay rules, catalogs, decisions, turn systems, and audit scoring.
- `toolbox/permit_office_arcgis/`: ArcGIS schema, persistence, geometry, dashboard, and message helpers.
- `tests/test_permit_office_rules.py`: active automated regression coverage.

## Current Status

See `docs/current-status.md` for the implemented/missing/iterate breakdown.

Short version:

- Implemented: deterministic Permit Office rules, generated districts, docket templates, inspections, population/grievance, incidents, projects, active features, maintenance, audit findings, ArcGIS schema/store coverage, and a dashboard-map loop.
- Missing: recorded live ArcGIS Pro smoke-test results, polished setup instructions for a cold demo machine, and presentation-machine confirmation for dashboard/map refresh behavior.
- Current default check:

```bash
python3 -m pytest tests/test_permit_office_rules.py -q
```

## ArcGIS Pro Smoke Test

Manual validation starts with:

```text
docs/permit-office-prototype-smoke-test.md
```

Add `toolbox/arcpy_permit_office.pyt` to ArcGIS Pro and run the `Permit Office Prototype` tool sequence from that document.

## Documentation

- `docs/permit-office-concept.md`: product concept and design direction.
- `docs/permit-office-architecture.md`: module boundaries and file-size rule.
- `docs/permit-office-turn-data-flow.md`: current per-week logic and ArcGIS data flow.
- `docs/permit-office-docket-design.md`: docket template and consequence model.
- `docs/permit-office-population-design.md`: population, dissatisfaction, and incident model.
- `docs/permit-office-prototype-smoke-test.md`: manual ArcGIS Pro validation sequence.
