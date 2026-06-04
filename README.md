# Permit Office

Permit Office is a turn-based city planning game that runs inside ArcGIS Pro.
You play as a municipal permit clerk trying to keep a strange city functional
through inspections, approvals, denials, mitigation conditions, and weekly audit
reports.

The joke is bureaucratic, but the game loop is real: every permit is tied to
map geometry, district state, stakeholder pressure, recurring costs, and visible
city consequences.

## How It Plays

Each office week gives you a small docket of permit applications, incidents, or
follow-up orders.

1. Select a docket item in the dashboard.
2. Review its proposed map exhibit and selected district targets.
3. Optionally inspect the file to reveal risk, evidence, violations, and local
   population context.
4. Issue the permit, issue it with mitigation conditions, deny it, or leave it
   unresolved until the week closes.
5. ArcPy applies the result to districts, support features, stakeholder heat,
   population grievances, recurring revenue/upkeep, maintenance, and audit risk.
6. At the end of the run, the city receives an audit scorecard.

Approvals can spawn points, lines, or polygons on the map: vendor markets,
utility trenches, fire coverage areas, public art grants, corridors, reserves,
incidents, inspection orders, and other civic paperwork with consequences.
The current rules target a 12-week civic season with scarce AP, more docket
items than the player can fully process, and city momentum from unresolved
cases.

## Why I Built It

Permit Office is an experiment in using ArcGIS Pro as a game engine rather than
only a mapping tool. Feature classes are the save file, map selections are the
input device, and ArcPy geometry operations become part of the rules system.

The project is also a small design study in "paperwork as play": the player is
not an all-powerful mayor, but an audit-facing office that shapes the city by
filing, approving, delaying, and explaining official decisions.

## What Is Interesting

- **ArcGIS-native game state:** districts, docket rows, projects, commands,
  logs, and permit features live in a file geodatabase.
- **Spatial consequences:** selected districts, adjacency, buffers, feature
  geometry, and support layers drive gameplay effects.
- **Pure Python rules:** the main simulation is testable without ArcGIS Pro,
  while ArcPy handles persistence and map operations.
- **Procedural civic texture:** district names, populations, services,
  grievances, hazards, housing pressure, stakeholder heat, and docket items are
  generated from a seed.
- **District identity pressure:** district type mix influences dockets, ignored
  proposals can create hidden momentum, and low-activity districts can enter
  contested buyout transitions from stronger neighbors.
- **Dry municipal absurdism:** the interface is built like a cluttered permit
  desk, with filed reports and audit language instead of fantasy UI tropes.

## Quick Start

### Requirements

- ArcGIS Pro with ArcPy available.
- Python 3 for the pure rules tests.
- `pytest` if you want to run the test suite outside ArcGIS Pro:
  `python3 -m pip install -r requirements-dev.txt`

### Run In ArcGIS Pro

1. Open an ArcGIS Pro project.
2. Add `toolbox/arcpy_permit_office.pyt` as a Python toolbox.
3. Run `Permit Office Prototype`.
4. If no saved game exists, click `New Game` in the dashboard.
5. Use the dashboard and map together: select docket rows, update targets from
   map selections, inspect files, issue or deny permits, and end the week.

By default the tool creates or resumes `permit_office.gdb` under the ArcGIS
project's `data/` folder. The geodatabase is local generated state and should
not be committed.

### Run Pure Python Tests

```bash
python3 -m pytest -q
```

The tests cover the ArcPy-free rules and lightweight ArcGIS adapter shims. They
do not replace a live ArcGIS Pro smoke test.

## Repository Map

- `toolbox/arcpy_permit_office.pyt` - ArcGIS Pro toolbox entrypoint.
- `toolbox/permit_office/` - pure gameplay rules, catalogs, decisions, turn
  advancement, audits, and city systems.
- `toolbox/permit_office_arcgis/` - schema, geodatabase store helpers, geometry
  operations, symbology, and the Tkinter dashboard.
- `tests/` - regression tests for the rules and ArcGIS adapter shims.
- `docs/` - the core reference set (see below).

## Documentation

- `docs/systems-overview.md` - architecture, persisted state, stat model, and the
  turn loop. Start here.
- `docs/docket-items.md` - docket template/item shape with worked examples.
- `docs/arcpy-usage.md` - which stock ArcPy APIs we use and how (cursors, schema,
  geometry, map refresh/redraw, selection).
- `docs/writing-and-tone.md` - the municipal voice and real copy examples.
- `docs/decisions.md` - concise ADRs: choices made and alternatives rejected.

## Current Status

Permit Office is a playable prototype. It has generated districts, seeded city
detail, weighted docket templates, inspections, approvals, no-AP ordinary
denials, mitigation, incidents, maintenance follow-ups, recurring economy,
projects, audits, map symbology, district identity/buyout pressure, start/help
flow, selected-case exhibit controls, an inline final audit receipt, and a
Tkinter dashboard.

The next public-readiness work is focused on evidence and balance: recording a
live ArcGIS Pro smoke test, validating cold-start resume behavior on the target
machine, tuning a fair 12-week route, and deepening map symbology only where the
live map proves it is still hard to read.

See `docs/systems-overview.md` for the implementation map, current status, and
the live ArcGIS validation walkthrough.
