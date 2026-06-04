# Permit Office Architecture

Date: 2026-05-27

The Permit Office prototype is split into two layers: pure game rules and the ArcGIS adapter.

## Pure Rules

`toolbox/permit_office/` contains ArcPy-free gameplay code. It can be imported and tested without ArcGIS Pro.

- `models.py`: dataclasses and shared constants.
- `catalogs/`: typed Python catalogs for docket templates, feature archetypes, scenarios, governance, inspections, and operating rules.
- `helpers.py`: district normalization, population/service helpers, stakeholder heat, catalog validation, and shared effect math.
- `systems.py`: projects, active feature lifecycle, network access, hazards, housing, scenarios, and recurring economy.
- `profiles.py`: district generation, docket generation, inspection case creation, and follow-up docket items.
- `expiration.py`: unattended docket expiration policies, city momentum, and pending follow-up triggers.
- `type_pressure.py`: hidden district-type ledger defaults, persistence helpers, and pressure summaries.
- `buyouts.py`: low-activity district buyout eligibility, refusal, contested transition, and conversion rules.
- `turns.py`: turn advancement, scorecards, audit results, and violation deadline handling.
- `decisions.py`: inspect/approve/mitigate/deny resolution for regular, maintenance, enforcement, and incident docket items.

`toolbox/arcpy_permit_office_rules.py` is a compatibility facade. Existing tests and the ArcGIS toolbox can keep importing it as `rules`.

## ArcGIS Adapter

`toolbox/permit_office_arcgis/` contains ArcGIS Pro and Tkinter integration.

- `schema.py`: geodatabase names, field declarations, and idempotent schema creation.
- `store.py`: reads/writes game state, districts, support features, docket rows, projects, commands, and logs.
- `geometry.py`: map selection, proposed geometries, spillover buffers, feature activation, map refresh, and symbology hooks.
- `dashboard.py`: Tkinter dashboard and effect report windows.
- `messages.py`: ArcGIS message helpers.
- `rules_loader.py`: direct file loading for the pure-rules compatibility facade.

`toolbox/arcpy_permit_office.pyt` should stay small: parameter definitions, action dispatch, and ArcGIS toolbox class declarations only.

## Turn Data Flow

The current turn and dashboard callback flow is documented in `docs/permit-office-turn-data-flow.md`. That file is the canonical reference for how `CityState`, `DistrictProfile`, `DocketItem`, `FeatureInstance`, and `ProjectRecord` move between pure rules and ArcGIS feature classes during inspect, approve, deny, exhibit, and advance-turn actions.

## File Size Rule

Active Permit Office Python files should stay under 1,000 lines. Retired prototype code should not remain in the active tree; recover older explorations from git history when needed.
