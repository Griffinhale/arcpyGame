# Changelog

All notable changes to Permit Office are recorded here. This project uses
[semantic versioning](https://semver.org/); pre-1.0 releases may change
behavior between minor versions.

## Unreleased

### Fixed
- District layers now render their evolving state (live-verified in ArcGIS Pro
  2026-06-04: districts repaint type/identity/prosperity across an End Week).
  `arcpy.RefreshLayer` only redraws a cached renderer and does not reload GDB
  attribute writes, so the refresh-only rebuild left district base/prosperity/
  identity frozen on the new-game snapshot. `rebuild_output_layers()` now removes
  + re-adds the district family every rebuild (feature layers stay refresh-only).
  See ADR-4.
- Added a manual **End Week** control to the desk utility menu so the week can
  always be closed — previously End Week only appeared once the queue was empty,
  trapping players who ran out of AP with unaffordable cases still queued
  (incident Deny also costs AP).

## v0.9.0-beta — Initial public beta

First public release. Permit Office is playable end to end as a 12-week civic
season inside ArcGIS Pro.

### Highlights
- Pure-Python rules engine (districts, dockets, inspections, decisions, turns,
  scorecards, audits) that runs and tests without ArcGIS.
- ArcGIS adapter: geodatabase-backed save state, generated district geometry,
  proposal/activation, map refresh, and a Tkinter desk dashboard.
- Content systems: weighted docket templates, stakeholder heat, population mix
  and dissatisfaction, civic incidents, service gaps, housing, hazards,
  projects, maintenance, recurring economy, district identity, and buyouts.
- Deterministic seeded generation; seed `2026` is a locked 12-week balance route.

### Performance
- Refresh-only map layer rebuild by default (skips redundant layer re-adds on
  data-only turns); full re-add reserved for new game / symbology changes.
- Fewer geodatabase cursor opens per action (batch proposal-visibility scan,
  read-once reload, memoized district geometry, where-narrowed single-row ops).

### Known gaps
- Live ArcGIS Pro smoke-test results on a target machine are not yet recorded.
- 12-week balance tuning toward a reliable PASS is ongoing.
- Map symbology legibility, cold-start resume, and legacy field migration on an
  existing `.gdb` still need live validation. See open issues and
  `docs/decisions.md`.
