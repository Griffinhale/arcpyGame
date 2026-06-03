# Permit Office Turn Data Flow

Date: 2026-05-27

## Purpose

This document describes the current per-week logic and data flow for the active Permit Office prototype. The persisted field is still named `turn` for compatibility, but player-facing copy treats each turn as one office week. Dashboard actions spend AP, mutate docket items, update map features, and persist results; `End Week` closes the audit week and generates the next docket until the final audit is filed.

## Dependencies

- `toolbox/arcpy_permit_office.pyt`: ArcGIS Pro tool entrypoint and top-level action dispatch.
- `toolbox/permit_office/`: ArcPy-free rules for districts, dockets, inspections, decisions, projects, feature lifecycle, city systems, and audits.
- `toolbox/permit_office_arcgis/schema.py`: feature class and table definitions.
- `toolbox/permit_office_arcgis/store.py`: reads and writes ArcGIS rows into pure-rule dataclasses.
- `toolbox/permit_office_arcgis/geometry.py`: selection, proposed exhibits, spillover buffers, activation, symbology, and map refresh.
- `toolbox/permit_office_arcgis/dashboard.py`: Tkinter callbacks that coordinate rules, store writes, map updates, receipts, and dashboard reloads.

## Persisted State

- `PermitGameState` stores `CityState`: turn, AP, money, audit stage, city metrics, stakeholder heat, recurring economy, and last report.
- `PermitDistricts` stores `DistrictProfile` rows: metrics, population mix, dissatisfaction, service gaps, hazards, housing fields, incident state, display state, and public profile text.
- `PermitDocket` stores `DocketItem` rows: item identity, template, status, inspection packet, targets, project linkage, risk band, due turn, and case JSON.
- `PermitPoints`, `PermitLines`, and `PermitZones` store proposed, active, context, denied, failed, incident, compliance, and maintenance features as `FeatureInstance` data split by geometry type.
- `PermitProjects` stores `ProjectRecord` rows for multi-turn chains.
- `PermitUICommand` and `PermitActionLog` store command lifecycle and player-facing audit trail.

## Primary Flows

### Tool Launch, Resume, And New Game

1. `arcpy_permit_office.pyt` resolves the workspace, calls `ensure_schema`, adds known output layers to the active map, and opens `DashboardController`.
2. Dashboard startup treats the resolved geodatabase as canonical saved-game state; Contents layers are repaired from the geodatabase when missing.
3. If saved district and state rows exist, the dashboard resumes them. If docket rows are missing, it regenerates the current docket before play.
4. If no saved game rows exist, the dashboard opens to a start state and waits for the player to click `New Game`.
5. Confirmed `New Game` calls `clear_game_rows`, `create_district_board`, `seed_city_features`, `write_state`, and `generate_docket_rows`.
6. New-game reset removes stale Permit Office output layers, adds fresh layers from the geodatabase, refreshes the map, and reloads the dashboard.

### Dashboard Load And Selection

1. `reload` reads state, districts, docket rows, and proposal visibility, then builds the desk model.
2. If no saved game rows exist, the same desk view renders a start status with `New Game` available.
3. Selecting a docket item calls `select_case_context`, which ensures a proposal exists, selects target districts, and selects the proposal or referenced active feature.
4. `Toggle Exhibit` deletes or recreates only the selected unresolved proposal row, then refreshes map layers and reloads the dashboard.
5. `Update From Map` reads selected district IDs from the district layer, replaces the selected proposal, persists the target IDs on the docket item, refreshes, and reloads.

### Inspect

1. The dashboard inserts a `PermitUICommand` row.
2. It reads `CityState`, districts, and active features.
3. `rules.resolve_decision(..., "inspect", ...)` spends AP and enriches the selected `DocketItem` with risk band, inspection evidence, and case JSON.
4. The dashboard writes state, the docket item, action log, and command finish status.
5. No proposal is activated and no district geometry changes. The filed report opens, then the dashboard reloads.

### Approve Or Approve With Mitigation

1. The dashboard ensures the selected item has a proposed exhibit, using existing targets or current map selection.
2. It computes spillover districts through ArcGIS buffer/select logic except for maintenance items.
3. It reads state, districts, active features, and projects.
4. `rules.resolve_decision` spends AP and money, applies target and spillover effects, applies mitigation if selected, checks contextual failure risk, updates population reactions, surfaces incidents, settles inspection violations, and advances or opens projects.
5. Feature maintenance updates are written first when the decision changed existing active features.
6. The proposed exhibit is activated into the appropriate support layer unless the approval failed.
7. Districts, state, projects, docket item, action log, and command status are persisted.
8. A targeted layer rebuild/refresh runs for `PermitDistricts` plus the changed support layer, then the filed report opens and the dashboard reloads.

### Deny

1. The dashboard inserts a command and reads state, districts, active features, and projects.
2. `rules.resolve_decision(..., "deny", ...)` records disposition, denial friction, stakeholder heat, local population reaction, and any project delay without spending AP or applying approval/project benefits.
3. Existing feature updates are written if the denial is a maintenance deferral.
4. Proposed rows for the docket item are marked denied or deferred.
5. Districts, state, projects, docket item, action log, and command status are persisted.
6. The affected layer set is rebuilt/refreshed, the filed report opens, and the dashboard reloads.

### End Week

1. The dashboard inserts an `advance_turn` command.
2. It reads state, open docket rows, districts, active features, and projects.
3. `rules.advance_turn_result` applies the current rules order:
   1. Unresolved open/inspected items resolve through template-specific expiration policy.
   2. Missed-window items expire cleanly; city-momentum items alter district pressure; bad momentum can seed later follow-up cases.
   3. Feature lifecycle, recurring economy, network, hazard, housing, and population systems advance.
   4. Contested buyout transitions resolve.
   5. New buyout bids are evaluated for low-prosperity districts.
   6. `CityState.turn` increments, AP resets, week 6 files the mid-season audit, and week 12 files the final audit.
6. State, projects, districts, active features, old docket item statuses, and command status are written.
7. `generate_docket_rows` replaces the visible docket with due project, maintenance, incident, stakeholder heat, and deterministic demo items in priority order unless the final audit has completed.
8. All output layers are rebuilt/refreshed, the dashboard status updates, and the dashboard reloads.

## Edge Cases

- Approvals require valid target counts by geometry type: one district for points, two for lines, at least one for zones.
- Maintenance items reference an existing active feature and skip geometric spillover.
- Inspections mutate only AP and the selected docket item packet.
- Failed approvals can create failed feature state and audit risk instead of ordinary active-feature benefits.
- Unresolved docket items create future pressure rather than disappearing quietly.
- Display refresh is an ArcGIS adapter concern. Current timing results do not justify an SDK dependency.

## Validation

- Pure rules: `python3 -m pytest tests/test_permit_office_rules.py -q`
- Full active suite: `python3 -m pytest -q`
- Live ArcGIS validation: `docs/permit-office-prototype-smoke-test.md`
- Refresh diagnostics: enable `Log Refresh Timings` in the toolbox or set `PERMIT_OFFICE_PERF=1` before running the dashboard.
