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

1. Run `Ping Environment`.
   - Confirms workspace resolution and lists loaded docket templates.
2. Run `New Game`.
   - Creates or resets `permit_office.gdb`.
   - Adds `PermitDistricts`, `PermitPoints`, `PermitLines`, and `PermitZones` to the active map.
   - Generates a 5x5 named district board and three docket items.
3. Select one district on the map.
4. Run `Open Dashboard`.
5. In the dashboard, pick a point-style docket item and click `Preview From Selection`.
   - A proposed point feature should appear in `PermitPoints`.
6. Click `Inspect`.
   - AP should decrease and the dashboard item text should include a risk band.
7. Click `Approve` or `Approve + Mitigate`.
   - The proposed feature should become active.
   - District metrics and `display_state` should update.
   - A modal effect report should appear.
   - GP messages should include refresh attempts.
8. Test a line item:
   - Select exactly two districts.
   - Click `Preview From Selection`.
   - Approve the corridor/procession item.
9. Test a polygon item:
   - Select one or more districts.
   - Click `Preview From Selection`.
   - Approve or deny it.
10. Click `Advance Turn`.
    - AP should reset.
    - A new three-item docket should be generated.
11. Run `Show Scorecard` from the GP tool.
    - The GP pane should show the current audit score.

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
- Proposed geometries are auto-generated from selected districts; Feature Set drawing is not used.
- This smoke test validates ArcGIS dashboard-map mechanics. The final six-turn balance is locked by pure Python regression coverage, but still needs a recorded live ArcGIS Pro run.
