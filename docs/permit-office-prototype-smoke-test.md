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
   - The dashboard creates or resets the geodatabase rows, adds `PermitDistricts`, `PermitPoints`, `PermitLines`, and `PermitZones`, and generates a 5x5 named district board with a four-item docket.
1. Select one district on the map if you want to override the seeded exhibit.
1. In the dashboard, pick a point-style docket item.
   - The docket row should select its proposed exhibit and target district on the map.
   - Click `Hide Proposed Feature`, then `Show Proposed Feature`; only that selected proposed row should disappear and return.
   - If changing placement, select a replacement district and click `Retarget Map`.
1. Click `Inspect File`.
   - AP should decrease and the dashboard item text should include a risk band.
1. Click `Issue Permit` or `Add Conditions`.
   - The proposed feature should become active.
   - District metrics and `display_state` should update.
   - A filed report tab should be appended without stealing focus from the next application.
   - GP messages should include refresh attempts.
1. Test a line item:
   - Select exactly two districts.
   - Click `Retarget Map`.
   - Click the visible approval action, usually `Issue Permit` for ordinary permit files.
1. Test a polygon item:
   - Select one or more districts.
   - Click `Retarget Map`.
   - Click the visible approval or denial action, such as `Issue Permit`, `Add Conditions`, or `Deny`.
1. Click `End Week`.
    - AP should reset.
    - A new four-item docket should be generated unless the final audit has completed.
    - Unresolved items should produce carried, expired, momentum, or follow-up behavior in the filed report.
1. Click `Scorecard` in the dashboard.
    - A scorecard report tab should show the current audit score.
1. Optional pacing check: continue ending weeks until week 12.
    - Week 6 should file the mid-season audit while keeping the game playable.
    - Week 12 should still have a playable docket.
    - Closing week 12 should open the final audit in Filed Reports and stop generating new dockets.
    - If buyout pressure appears, record whether vulnerable, contested, and converted districts are understandable from map labels, symbology, and filed reports without inspecting raw tables.
1. Record map symbology observations or screenshots.
    - District type colors and district-name labels should be readable at normal demo zoom.
    - Proposed features should stand apart from active features.
    - Roads and utility lines should remain distinguishable above district fills.
    - Seeded housing, commerce, civic, industrial, campus, and park details should add context without hiding permit features.
    - `PermitZones` transparency should preserve district identity under polygon features.

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
- This smoke test validates ArcGIS dashboard-map mechanics. The 12-week balance is covered by pure Python regression smoke checks where available, but still needs a recorded live ArcGIS Pro run.
