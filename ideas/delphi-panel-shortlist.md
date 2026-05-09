# Delphi Panel Shortlist — arcpyGame

Date: 2026-05-08

This document summarizes a three-layer Delphi-style ideation pass for **arcpyGame**, an ArcGIS Pro / ArcPy geoprocessing-tool-based class game.

Method:

1. **Round 1:** Five independent reviewers critiqued the existing idea set and added new concepts.
2. **Round 2:** Five reviewers received the original ideas plus an unlabeled synthesis of Round 1 feedback, then refined/merged concepts.
3. **Final layer:** Five reviewers produced decisive shortlists and recommended build order.

## Core consensus

The strongest project is not “a game displayed on a map.” It is a game where **geoprocessing is the player’s verb**.

Good mappings:

- **Buffer** = defend, contain, threaten, reveal, tower range, quarantine radius.
- **Intersect / Clip / Erase** = resolve conflict, apply damage, remove threats, cut off spread.
- **Spatial Join** = score consequences, assign population/resources/exposure.
- **Dissolve** = consolidate territory, merge safe zones, upgrade controlled regions.
- **Adjacency / Touches** = legal moves, spread, attacks, neighboring clues.
- **Network / cost distance** = routing, rescue, logistics, escape.
- **Suitability scoring** = planning tradeoffs and location choices.

Hard constraint:

- Build it **turn-based or tick-based**.
- Avoid real-time animation, custom UI-heavy mechanics, literal deckbuilder interfaces, RPG inventory bloat, and large dynamic simulations.

Best implementation pattern:

- Small curated/generated board: parcels, grid, hexes, tracts, or cells.
- Feature classes store game state.
- Player selects, edits, or places features.
- One `Game Controller` geoprocessing tool with an `Action` dropdown resolves turns.
- Symbology and labels communicate state.
- Precompute adjacency, static suitability, route candidates, and expensive relationships.

## Final category winners

### Best overall: Containment Commander

**Pitch:** A spreading threat — invasive species, wildfire, outbreak, kudzu, contamination, zombie infection — expands across parcels/cells each turn. The player uses limited interventions to contain, treat, quarantine, or block it.

Why it wins:

- Best blend of game feel, GIS legitimacy, visual feedback, and feasible ArcPy mechanics.
- Naturally turn-based.
- Threat spread creates urgency without real-time engineering.
- Works with core vector tools.

Core mechanics:

- Threat spreads by adjacency/proximity.
- Player places treatment zones, barriers, quarantine buffers, or removal actions.
- `Buffer`, `Intersect`, `Erase`, `Clip`, `Spatial Join`, and field calculations resolve each tick.
- Score by area/population/habitat/assets saved.

MVP sketch:

- 20–50 cell board.
- Fields: `threat`, `revealed`, `protected`, `treated`, `asset_value`, `turn_updated`.
- Actions: `Scout`, `Treat Selected`, `Place Barrier`, `Buffer Defense`, `Resolve Turn`.
- Win: contain threat below threshold after N turns.
- Lose: threat reaches protected zone or exceeds area/population threshold.

Tie-break note:

- Beats Census Conquest because it is more visibly dynamic and more naturally tense.

### Safest MVP: Map Minesweeper / Survey Sweeper

**Pitch:** Hidden hazards/artifacts/contamination are placed on a grid, parcel layer, or survey map. Player reveals cells/areas and receives spatial clues.

Why it matters:

- Lowest implementation risk.
- Built-in hidden information and win/loss.
- Easy to polish and demo.
- Proves the ArcPy game loop before building a richer game.

GIS-native upgrades:

- Use irregular parcels or real land-use zones, not just a square grid.
- Make hazards spatially biased: near roads, rivers, industry, old settlements, slopes, or utility corridors.
- Survey actions can use buffer radius, area cost, false positives, or proximity hints.

MVP sketch:

- `New Game`: generate board and hidden hazards.
- `Reveal Selected`: reveal selected polygon and clue count.
- `Flag Selected`: mark suspected hazard.
- `Check Win`: all safe cells revealed or hazards flagged.

Tie-break note:

- Best first prototype and fallback deliverable if time is tight.

### Highest wow factor: Bufferlands: Spatial Tactics

**Pitch:** A small tactics board where each player action is a geoprocessing operation: Buffer Shield, Clip Trap, Erase Hotspot, Dissolve Stronghold, Spatial Join Harvest, Intersect Strike.

Why it stands out:

- Most explicit “ArcPy as game engine” concept.
- Geoprocessing tools become visible tactical powers.
- Great class-demo line: “Every move is a GIS operation.”

Scope warning:

- Do **not** build a literal deckbuilder UI.
- Use an action dropdown or action table with costs/cooldowns.
- No real-time tower-defense behavior.

MVP sketch:

- Board: 25–75 parcels/hexes.
- Threat/opponent has simple spread/claim rule.
- Player gets 2 actions per turn.
- Actions are rows in an `AvailableActions` table or choices in GP parameters.
- The controller tool applies one action and updates feature fields/symbology.

Tie-break note:

- Highest conceptual ceiling, but only if aggressively scoped.

### Best GIS pedagogy: Census / District Conquest

**Pitch:** Territory-control or redistricting-style strategy game on census tracts/counties/parcels where demographics, contiguity, compactness, resources, and equity affect scoring.

Why it teaches well:

- Directly demonstrates joins, dissolves, aggregation, adjacency, choropleths, contiguity, and demographic tradeoffs.
- Easy to explain to a GIS class.
- Strong fit for a traditional geoprocessing assignment.

Make it less dry:

- Add opponent pressure or civic events.
- Win by controlling population/resources, not raw area.
- Penalize fragmentation, inequity, unrest, or non-contiguity.
- Use playful framing: “District Boss Fight,” “Census Conquest,” or “Win the Map Without Breaking It.”

Tie-break note:

- Strongest academic concept, but less game-like than Containment Commander unless the scoring and opposition are sharp.

### Riskiest-but-coolest: Watershed Dungeon Crawler

**Pitch:** A raindrop, pollutant, or explorer moves through a hydrologic dungeon defined by flow direction, streams, basins, and downstream topology.

Why it is cool:

- Deeply GIS-native.
- Hydrology becomes the game board, not just a theme.
- Very memorable if it works.

Risk:

- Hydrology preprocessing and raster tools may require Spatial Analyst.
- Gameplay loop can be harder to explain.
- Data prep could eat the project.

Safer version:

- Precompute or hand-build the stream/basin graph.
- Use vector catchments and downstream adjacency instead of live raster hydrology.
- Treat it as a stretch scenario after the core engine works.

## Full final ranking

1. **Containment Commander** — best complete concept; strong gameplay, strong ArcPy fit, manageable scope.
2. **Map Minesweeper / Survey Sweeper** — safest polished MVP and best first implementation.
3. **Bufferlands: Spatial Tactics** — highest conceptual upside, but must avoid custom UI/deckbuilder bloat.
4. **Census / District Conquest** — best pedagogy and solid alternate, slightly less playful.
5. **Urban Planner Puzzle / Habitat Corridor** — educational and feasible, but risks feeling like a planning exercise.
6. **RescueOps / Evacuation / Route-risk** — compelling theme, but routing/network dependencies increase risk.
7. **Watershed Dungeon Crawler** — coolest stretch, least reliable for class scope.
8. **Supply Chain / Logistics RTS-lite** — interesting but likely too simulation-heavy.
9. **Guildmaster GIS RPG** — theme-heavy and likely to bloat with inventory/quests/combat.
10. **GeoGuessr ArcGIS Edition** — accessible and fun, but ArcPy is mostly supporting decoration unless clue generation is heavily geoprocessing-driven.

## Recommended build order

### Phase 1 — Shared engine skeleton

Build a minimal reusable ArcPy game architecture:

- `GameBoard` feature class with state fields.
- `GameState` table for turn number, score, seed, resources, win/loss.
- Optional `ActionLog` table.
- One Python toolbox / script tool:
  - `New Game`
  - `Play Action`
  - `Resolve Turn`
  - `Show Score`
  - `Reset`
- Map symbology keyed off state fields.

### Phase 2 — Map Minesweeper MVP

Use Minesweeper/Survey Sweeper to validate:

- Hidden/revealed state.
- Selections as player input.
- Action dropdown workflow.
- Win/loss state.
- Symbology refresh.
- Clear turn messages.

This becomes the fallback deliverable.

### Phase 3 — Containment Commander main game

Reuse the same skeleton and add:

- Threat spread by adjacency/proximity.
- Limited actions/resources per turn.
- Treatment/barrier/buffer mechanics.
- Consequence scoring by assets saved/lost.
- Escalating events or difficulty.

This should be the primary final submission target.

### Phase 4 — Bufferlands-style wow actions

Add one or two special geoprocessing powers:

- `Buffer Barrier`
- `Erase Hotspot`
- `Clip Quarantine`
- `Dissolve Safe Zone`
- `Spatial Join Harvest / Score`

Keep these as GP actions, not a custom card UI.

### Phase 5 — Optional alternate scenario

If the engine is stable, consider a small Census/District Conquest scenario to show reusability and pedagogical depth.

Avoid Watershed Dungeon, RescueOps, or true Network/Spatial Analyst dependency unless the core game is already polished.

## Practical design guardrails

- Board size: 20–75 features for MVP.
- Turns: 5–15 turns per scenario.
- Actions: 3–5 actions maximum for first build.
- State: keep all meaningful state in fields/tables, not Python globals.
- Data: generated or curated beats messy real-world data for first prototype.
- Extensions: core vector baseline first; advanced tools optional only.
- Demo: every turn should visibly change the map.

## Decisive recommendation

Build **Map Minesweeper / Survey Sweeper first** as the technical proof-of-loop, then evolve it into **Containment Commander** as the main class project.

Use **Bufferlands-style geoprocessing powers** as the presentation wow layer.

That path gives the best balance of:

- feasible implementation,
- class-demo polish,
- real GIS/geoprocessing substance,
- game feel,
- and “ArcPy is the engine” credibility.
