# Changelog

All notable changes to Permit Office are recorded here. This project uses
[semantic versioning](https://semver.org/); pre-1.0 releases may change
behavior between minor versions.

## v0.9.0 — 2026-06-04

First tagged public release. Permit Office is playable end to end as a 12-week
civic season inside ArcGIS Pro.

### Highlights
- Pure-Python rules engine (districts, dockets, inspections, decisions, turns,
  scorecards, audits) that runs and tests without ArcGIS.
- ArcGIS adapter: geodatabase-backed save state, generated district geometry,
  proposal/activation, map repaint, and a Tkinter desk dashboard.
- Content systems: weighted docket templates (shaped by district type **and**
  citizen-culture mix), stakeholder heat, population mix and dissatisfaction,
  civic incidents, service gaps, housing, hazards, projects, maintenance,
  recurring economy, and deepened district identity / multi-bidder buyouts.
- Deterministic seeded generation; seed `2026` is a locked 12-week balance route.

### Added
- **District identity deepening (#6):** human-readable district names everywhere
  in player-facing text (audit findings, dashboard, reports, previews; `cell_id`
  stays the stable key); district type + citizen-culture distribution shape which
  proposals appear; multi-bidder buyout negotiation with per-bidder willingness
  rolls; a successful buyout shifts the district's type, culture, and resources
  with overextension risk. See ADR-14.
- **Empty-map fresh start:** launching against a workspace whose `.gdb` holds a
  save but whose map has no Permit Office layers now opens a New Game prompt
  instead of silently resuming the old board (the save is left untouched).
- **ArcGIS Pro smoke checklist** (`docs/arcgis-pro-smoke-checklist.md`) for live
  beta validation.

### Changed
- The optional **Game Workspace** is honored verbatim — even when its `.gdb` is
  empty — and the project/scratch default is used only when no workspace is
  given; each resolution logs its source.
- City-health vocabulary unified on the four vitals (Activity / Friction / Trust
  / Exposure) with Heat + Pressure signals (#5, ADR-10); revenue/upkeep/net shown
  on inspected revenue cases, and action lanes read per case family (#1, #2).

### Fixed
- District layers render their evolving state across an End Week (live-verified
  2026-06-04). `arcpy.RefreshLayer` does not reload GDB attribute writes, so
  `rebuild_output_layers()` removes + re-adds the district family every rebuild
  (feature layers stay refresh-only). See ADR-4.
- Resuming a save no longer crashes when a selected case targets several
  aggrieved districts: grievance bands now aggregate by max (staying within the
  label range) instead of summing — was an `IndexError` in
  `target_population_hint`.
- A manual **End Week** control is always available from the desk utility menu
  (previously it only appeared once the queue was empty, trapping players out of
  AP with unaffordable cases queued).

### Performance
- Controller-side **audit-grade cache:** the scorecard (and its district
  `deepcopy`) recomputes only on game-data writes, not on selection-only redraws.
- Desk view caches per-model lookup maps and memoizes text-fit across redraws.
- Fewer geodatabase cursor opens per action (batch proposal-visibility scan,
  read-once reload, memoized district geometry; `selected_cell_ids` reads the
  `cell_id` column directly, falling back to a field scan only on error).
- A "skip the district re-add when no rendered field changed" experiment was
  tried and **reverted**: `RefreshLayer` reloads neither symbology nor
  attributes, and attribute tables change nearly every action, so the district
  family must re-add unconditionally (ADR-4).

### Known gaps
- Developed and tested on **ArcGIS Pro 3.6**; earlier versions are untested and
  may lack some arcpy APIs the toolbox uses (`arcpy.mp`, `arcpy.da.Describe`, CIM
  renderer definitions, spatial-reference handling). 3.6+ recommended.
- Live ArcGIS Pro smoke-test results on a target machine are not yet recorded
  (see `docs/arcgis-pro-smoke-checklist.md`; open issues #9, #11).
- 12-week balance tuning toward a reliable PASS is ongoing.
- Map symbology legibility (#9) and the cursor/IO live-verification items (#11)
  still need a live session.
