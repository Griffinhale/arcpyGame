# ArcGIS Panel Automation Spike

Date: 2026-06-04

## Question

Can the Permit Office Python toolbox reliably open or arrange ArcGIS Pro
Contents and Geoprocessing panes as part of dashboard startup?

## Result

Do not automate ArcGIS Pro pane arrangement from the Python toolbox path.

The current reliable startup contract is geodatabase and layer repair:

- create or resume the `permit_office.gdb` rows,
- repair or add `PermitDistricts`, `PermitPoints`, `PermitLines`, and
  `PermitZones`,
- open the Tk dashboard in a predictable size,
- let ArcGIS Pro keep normal pane layout under user control.

ArcPy exposes geoprocessing, data, layer, selection, and map-refresh operations
that the toolbox already uses. It does not provide a stable public Python API
for arranging the ArcGIS Pro Contents or Geoprocessing panes. UI automation or
SDK-only pane control would add deployment fragility and is outside the normal
dashboard command flow.

## Decision Rule

If a future live smoke test shows pane layout blocks the demo, solve it with
documented setup instructions first. Revisit automation only if ArcGIS exposes a
supported Python API for pane arrangement.
