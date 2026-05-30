# Permit Office Prototype Smoke Test

Purpose: validate the first Permit Office dashboard-map loop inside ArcGIS Pro.

## Toolbox

Add this Python toolbox in ArcGIS Pro:

```text
toolbox/arcpy_permit_office.pyt
```

Tool:

```text
Permit Office Prototype
```

## Smoke Sequence

1. Run the `Permit Office Prototype` geoprocessing tool.
   - The tool resolves or creates `permit_office.gdb`, repairs the map layers, and opens the dashboard.
   - If saved game rows already exist, the dashboard resumes them.
1. If no saved game is present, click `New Game` in the dashboard.
   - Confirm replacement if prompted.
   - Accept seed `2026` for the deterministic smoke route.
   - The dashboard creates or resets the geodatabase rows, adds `PermitDistricts`, `PermitPoints`, `PermitLines`, and `PermitZones`, and generates a 5x5 named district board with three docket items.
1. Select one district on the map if you want to override the seeded exhibit.
1. In the dashboard, pick a point-style docket item.
   - The docket row should select its proposed exhibit and target district on the map.
   - Click `Hide Exhibit`, then `Show Exhibit`; only that selected proposed row should disappear and return.
   - If changing placement, select a replacement district and click `Update From Map`.
1. Click `Inspect`.
   - AP should decrease and the dashboard item text should include a risk band.
1. Click `Approve` or `Approve + Mitigate`.
   - The proposed feature should become active.
   - District metrics and `display_state` should update.
   - A modal effect report should appear.
   - GP messages should include refresh attempts.
1. Test a line item:
   - Select exactly two districts.
   - Click `Update From Map`.
   - Approve the corridor/procession item.
1. Test a polygon item:
   - Select one or more districts.
   - Click `Update From Map`.
   - Approve or deny it.
1. Click `End Day`.
    - AP should reset.
    - A new three-item docket should be generated.
1. Click `Scorecard` in the dashboard.
    - The scorecard dialog should show the current audit score.

## Expected Data

The prototype writes:

- `PermitDistricts`: playable district polygons.
- `PermitPoints`: proposed/active point permits.
- `PermitLines`: proposed/active line permits.
- `PermitZones`: proposed/active polygon zone permits.
- `PermitDocket`: current docket rows.
- `PermitGameState`: turn, AP, money, audit and city metrics.
- `PermitUICommand`: recoverable command rows.
- `PermitActionLog`: player-facing action history.

## Known Prototype Boundaries

- The dashboard is intentionally the main controller.
- Manual map refresh is acceptable if live redraw lags.
- Proposed geometries are seeded automatically and can be replaced from the current district selection; Feature Set drawing is not used.
- This smoke test validates ArcGIS dashboard-map mechanics. The final six-turn balance is locked by pure Python regression coverage, but still needs a recorded live ArcGIS Pro run.
