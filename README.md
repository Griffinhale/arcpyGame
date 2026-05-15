# arcpyGame

Brainstorming a class geoprocessing-tool project that abuses ArcGIS Pro + ArcPy as a game engine: geometry as sprites/colliders, layers as render targets, geoprocessing tools as turns/ticks, attributes as game state, symbology/layouts as UI.

## Core premise

Build an ArcGIS Pro geoprocessing tool that feels like a small game while still demonstrating legitimate GIS/geoprocessing concepts.

The trick is to treat the GIS stack as the engine:

- **Feature classes**: entities, map tiles, board cells, NPCs, resources, projectiles, territories.
- **Geometry operations**: movement, visibility, collisions, adjacency, buffers, influence zones, attacks, pathfinding approximations.
- **Attribute tables**: health, owner, score, resources, fog-of-war, cooldowns, turns.
- **Symbology**: rendering/game art.
- **Definition queries/layer visibility**: UI states, hidden information, menus.
- **Selections**: player input.
- **Geoprocessing parameters**: buttons, choices, commands.
- **ArcGIS Pro map refresh**: game loop, probably turn-based or semi-idle rather than real-time.

## Current spike artifacts

- `toolbox/arcpy_game_spike.pyt`: original ArcGIS Pro feasibility spike for Python toolbox loading, parameters, selections, cursor updates, refresh, symbology hooks, and memory geoprocessing.
- `toolbox/arcpy_game_gui_spike.pyt`: GUI validation spike for GP-pane-to-Tkinter handoff, durable command/session tables, live map preview updates, crash recovery, idempotency, Containment dry-runs, Bufferlands dry-runs, and Novelty Reopen control-panel checks.
- `toolbox/arcpy_game_rules.py`: pure Python Survey Sweeper rule engine, tested outside ArcGIS Pro.
- `toolbox/arcpy_permit_office.pyt`: Permit Office prototype toolbox for the new dashboard-map-loop city sim direction.
- `toolbox/arcpy_permit_office_rules.py`: pure Python Permit Office sim rules for generated districts, docket items, inspections, approvals, mitigation, denials, and audit scoring.

See `ideas/gui-validation-spike.md` for the GUI spike smoke-test sequence and interpretation notes.
See `ideas/gui-era-concept-reopen.md` for the novelty-first concept re-rank after the GUI spike.
See `docs/permit-office-prototype-smoke-test.md` for the Permit Office prototype smoke-test sequence.

## Design constraints / likely realities

- Real-time action is probably painful. ArcPy + Pro rendering is not a 60fps loop.
- Turn-based, tick-based, idle, puzzle, board-game, strategy, and guessing-game formats are much better fits.
- Input should probably be one of:
  - Select features on the map, then run a GP tool.
  - Pick parameters in a tool dialog.
  - Click/edit a small command feature layer.
  - Use bookmarks/layouts as screens.
- Best class-project angle: make the game visibly teach/use GIS operations, not just hide them.
- The best games will make the geoprocessing concept the mechanic.

## Strong candidate concepts

### 1. Census Conquest

**Pitch:** Turn census tracts/counties into a Risk-like territory game. You expand from a starting tract, gather population/tax/resource points, and fight neighboring areas.

**GIS mechanics:**
- Polygon adjacency for legal moves.
- Demographic attributes determine resource generation.
- Buffers or commute flows influence attack/defense.
- Dissolve conquered territories into player regions.
- Choropleth symbology shows control, unrest, wealth, population.

**Why it fits:**
- Very class-friendly: census data, tracts, joins, adjacency, dissolve, field calculations.
- Naturally turn-based.
- Easy to explain and demo.

**Core loop:**
1. Choose starting tract.
2. Run `Next Turn` tool to collect resources.
3. Select adjacent enemy tract.
4. Run `Attack / Annex` tool.
5. Update ownership, score, map styling.

**Risk:** Could become just Risk with GIS dressing unless mechanics meaningfully use real attributes.

### 2. GeoGuessr: ArcGIS Edition

**Pitch:** The tool drops the player somewhere using map data clues; player guesses location by placing a point. Score is based on geodesic distance.

**Variants:**
- Guess city/county/tract from demographic clues.
- Guess watershed from stream network hints.
- Guess state from clipped road/river outlines.
- Guess neighborhood from POI density.

**GIS mechanics:**
- Random feature selection.
- Extent/bookmark manipulation.
- Distance calculation.
- Spatial joins to reveal clues.
- Masking/clipping to hide labels/basemap context.

**Why it fits:**
- Very achievable.
- Fun in a class demo.
- Minimal game-state complexity.

**Core loop:**
1. Generate mystery location/region.
2. Show limited map clues.
3. Player places guess point.
4. Tool computes distance and score.
5. Reveal actual location.

**Risk:** Less ambitious mechanically, but likely to actually work and be polished.

### 3. Minesweeper on a Map

**Pitch:** A grid or real polygon layer hides hazards. Selecting a cell reveals counts of neighboring hazards. Win by flagging all mines.

**GIS mechanics:**
- Generate fishnet grid or use parcels/tracts.
- Spatial adjacency / touches.
- Attribute updates for revealed/flagged/mine/count.
- Symbology as game board.

**Real-world twist options:**
- Environmental hazard sweeper: contaminated parcels.
- Archaeology survey: avoid protected sites.
- Utility repair: locate faults from sensor hints.

**Why it fits:**
- Very clean geoprocessing logic.
- Classic calculator/excel-game energy.
- Easy to make satisfying visually.

**Core loop:**
1. Create board from grid or polygons.
2. Player selects a cell and chooses Reveal/Flag.
3. Tool updates state and neighbor counts.
4. Recursive reveal for zero-neighbor cells.
5. Symbology updates.

**Risk:** If using a plain grid, it may not feel GIS-specific enough. Real geography makes it better.

### 4. Tower Defense: Bufferlands

**Pitch:** Enemies move along a road/stream network. Player places towers as point features. Towers attack enemies within buffer range each tick.

**GIS mechanics:**
- Network/path representation via polylines.
- Points as towers/enemies.
- Buffers for range.
- Intersections for attacks.
- Attribute updates for health, cooldown, money.
- Graduated symbols for damage/range.

**Why it fits:**
- Very game-like and visually compelling.
- Demonstrates buffers, intersections, distances, linear referencing-ish movement.

**Core loop:**
1. Initialize enemy route.
2. Player places tower points.
3. Run `Advance Tick`.
4. Enemies move along path.
5. Towers damage enemies in range.
6. Earn money, spawn next wave.

**Risk:** More engineering. Movement along polylines and repeated map refresh may be fiddly.

### 5. Urban Planner Idle Game

**Pitch:** You manage a city over many turns. Zoning polygons produce money, happiness, traffic, pollution, and population. Geoprocessing computes effects.

**GIS mechanics:**
- Land-use polygons.
- Buffers for school/park/pollution influence.
- Suitability analysis.
- Weighted overlay.
- Network proximity to roads/transit.
- Raster or polygon heatmaps.

**Why it fits:**
- Great GIS legitimacy.
- Easy to keep turn-based.
- Can be simple or deep.

**Core loop:**
1. Select parcels to zone/build.
2. Run `Simulate Year`.
3. Tool calculates growth, revenue, congestion, pollution, satisfaction.
4. Map updates as living city dashboard.

**Risk:** More of a simulation than a game unless win/loss goals are sharp.

### 6. RPG Territory Management: Guildmaster GIS

**Pitch:** The player controls a guild/kingdom across regions. Send parties to zones, collect resources, fight monsters, upgrade settlements.

**GIS mechanics:**
- Regions as territories/dungeons.
- Travel time from network distance.
- Resource suitability from overlays.
- Fog-of-war via visibility fields.
- Random encounters based on terrain/land cover.

**Why it fits:**
- Fun wrapper around actual spatial analysis.
- Flexible data source: land cover, elevation, roads, counties, fictional map.

**Core loop:**
1. Choose mission target region.
2. Run expedition tool.
3. Compute travel cost and encounter odds.
4. Update party health/resources/territory state.
5. Reveal new regions.

**Risk:** Narrative content can balloon. Needs a tight MVP.

### 7. Pandemic / Outbreak Containment

**Pitch:** Disease spreads across polygons or a network. Player deploys limited clinics, quarantines, and travel restrictions.

**GIS mechanics:**
- Adjacency-based spread.
- Network connectivity.
- Buffers for clinic coverage.
- Demographics as vulnerability.
- Hotspot maps.

**Why it fits:**
- Uses GIS naturally.
- Strategic, turn-based, visually clear.

**Core loop:**
1. Infection spreads each turn based on neighbors and population.
2. Player places interventions.
3. Tool calculates new infections/recoveries.
4. Score based on lives saved / cost.

**Risk:** Theme might be sensitive depending class context, but mechanically strong.

### 8. Supply Chain / Logistics RTS-lite

**Pitch:** Manage warehouses, roads, deliveries, and demand zones. Each turn, goods move through the network; disruptions appear.

**GIS mechanics:**
- Service areas.
- Closest facility logic.
- Route cost approximations.
- Demand polygons.
- Capacity constraints.

**Why it fits:**
- Legitimate GIS problem disguised as game.
- Could use real road/demand data.

**Core loop:**
1. Build/upgrade facilities.
2. Assign demand zones.
3. Run delivery tick.
4. Calculate fulfilled demand, cost, delays.
5. Random road closures/events.

**Risk:** If network analyst tools are unavailable, route logic may need simplifying.

### 9. Card Game: Spatial Tactics Deckbuilder

**Pitch:** Cards trigger geoprocessing effects: Buffer, Dissolve, Clip, Erase, Intersect, Spatial Join. You fight for control of a map board.

**GIS mechanics:**
- Each card maps to a GIS operation.
- Player selects targets on map.
- Tool applies effect to territories/entities.
- Attributes track deck/hand/discard.

**Example cards:**
- **Buffer:** Fortify all cells within 2 km.
- **Clip:** Cut enemy influence to a selected district.
- **Dissolve:** Merge adjacent friendly zones for bonus income.
- **Spatial Join:** Steal resources from connected regions.
- **Erase:** Remove hazards from selected area.

**Why it fits:**
- Extremely class-relevant because geoprocessing operations are literally game actions.
- Fun and memorable.

**Risk:** More UI/state complexity; hand/deck management in ArcGIS could be clunky.

### 10. Watershed Dungeon Crawler

**Pitch:** The player is a raindrop traveling downhill through a DEM/stream network, collecting nutrients/avoiding pollution until reaching an outlet.

**GIS mechanics:**
- Flow direction/accumulation if raster tools are available.
- Stream networks.
- Watersheds/catchments.
- Cost paths.
- Terrain/elevation.

**Why it fits:**
- Very geospatially native.
- More original than generic board-game translation.

**Core loop:**
1. Start at random high-elevation cell/point.
2. Player chooses path options or tool advances based on flow direction.
3. Collect/lose points based on land cover and pollution zones.
4. End at water body/outlet.

**Risk:** Depends on raster/Spatial Analyst licensing unless simplified.

## Input/UI patterns worth considering

### Pattern A: One toolbox, many command tools

Create a Python toolbox with tools like:

- `New Game`
- `Take Turn`
- `Reveal Selected`
- `Attack Selected`
- `Place Tower`
- `Advance Tick`
- `Show Score`

Pros:
- Natural ArcGIS workflow.
- Easy to grade/demo.

Cons:
- Lots of repeated tool opening unless scripted well.

### Pattern B: One command tool with an Action dropdown

A single GP tool:

- `Action`: New Game / Move / Attack / Reveal / Flag / Advance Tick
- `Selected Layer`: current game board/entity layer
- Optional parameters depending action

Pros:
- Simpler toolbox.
- Feels like a controller.

Cons:
- Parameter UX may be less elegant.

### Pattern C: Map selection as controller

Player selects features on the map, then runs the relevant action. Selected features are the input.

Pros:
- Very tactile.
- Uses ArcGIS as the interface.

Cons:
- Need clear validation/error messages.

### Pattern D: Feature editing as input

Player edits/creates command features, e.g. tower points or guess points, then runs `Resolve Turn`.

Pros:
- Great for tower defense, GeoGuessr, city-builder.

Cons:
- Editing workflow can be clunky for novice users.

## My ranked shortlist

### Best class-project bet: **Census Conquest**

Reason: It is ambitious enough to be memorable, but it maps cleanly onto polygon layers, adjacency, field calculations, joins, dissolve, and thematic rendering.

MVP scope:
- One map of census tracts/counties.
- Ownership field.
- Resources generated by population/income/etc.
- Attack adjacent territory.
- Win by controlling X% of population or territory.

Stretch:
- Factions.
- Policy cards.
- Unrest/happiness.
- Territory dissolve into empire borders.

### Most fun/polished bet: **Map Minesweeper**

Reason: It has the calculator-game vibe and is easiest to make feel complete.

MVP scope:
- Generate grid or use real polygons.
- Randomly place mines.
- Reveal/flag selected cells.
- Neighbor counts.
- Win/loss states.

Stretch:
- Real GIS theme: environmental survey, disaster search, archaeology, infrastructure faults.
- Difficulty based on terrain/land-use features.

### Most technically impressive bet: **Tower Defense: Bufferlands**

Reason: It makes ArcGIS visibly act like a game engine: entities moving, towers with ranges, map ticks.

MVP scope:
- One polyline route.
- Enemy points advance by step index.
- Tower points with range buffers.
- Damage enemies in range each tick.
- Score and wave counter.

Stretch:
- Multiple tower types.
- Multiple routes.
- Terrain affects speed.
- Range rings as dynamic layers.

### Most GIS-concept elegant: **Geoprocessing Card Battler**

Reason: It turns the curriculum itself into mechanics. The player learns geoprocessing by playing geoprocessing cards.

MVP scope:
- Small polygon board.
- 8-12 cards/actions.
- Each card applies a spatial operation.
- Control/score updates after each card.

Stretch:
- Deckbuilding.
- Enemy AI.
- Scenario puzzles.

## Adversarial critique

The tempting mistake is trying to make ArcGIS Pro into an action game. That will probably be brittle and slow. The strongest idea is not “make a game despite GIS,” but “make spatial analysis be the game mechanic.”

Weakest directions:
- **Full RTS:** likely too much state, too much ticking, too much UI friction.
- **Generic RPG:** narrative and inventory bloat can hide the GIS contribution.
- **Plain grid Minesweeper:** fun, but may not prove enough geoprocessing unless adapted to real geography.
- **Complex deckbuilder:** cool, but card state/UI could eat the project.

Strongest directions:
- **Census Conquest** if you want a polished strategic class project.
- **Map Minesweeper** if you want a guaranteed playable artifact.
- **Tower Defense** if you want to show off technical creativity.
- **Geoprocessing Card Battler** if the grading rubric rewards demonstrating many GP tools.

## Recommended first prototype

Build a tiny vertical slice for **Census Conquest** or **Map Minesweeper** first.

### Option A prototype: Census Conquest in one afternoon

Data:
- 20-100 polygons, either census tracts/counties or a generated hex grid.

Fields:
- `owner`: Neutral / Player / Enemy
- `pop`: population/resource value
- `income`: optional modifier
- `defense`: derived value
- `turn_captured`

Tools:
- `New Game`: initializes fields, picks player/enemy starts.
- `Attack Selected`: validates selected target touches player-owned territory; resolves combat.
- `End Turn`: grants resources and lets enemy expand.

Win condition:
- Control 50% of total population.

### Option B prototype: Map Minesweeper in one afternoon

Data:
- Generated fishnet grid or polygons.

Fields:
- `is_mine`
- `revealed`
- `flagged`
- `neighbor_mines`
- `state_label`

Tools:
- `New Game`: creates board and mines.
- `Reveal Selected`: reveals selected cell(s), computes loss/win.
- `Flag Selected`: toggles flag.

Win condition:
- All non-mine cells revealed or all mines flagged.

## Possible project structure

```text
arcpyGame/
  README.md
  ideas/
    census-conquest.md
    map-minesweeper.md
    tower-defense-bufferlands.md
  toolbox/
    arcpy_game.pyt
  data/
    sample.gdb/
  scripts/
    prototype_logic.py
```

## Immediate next decision

Pick one of these as the first vertical slice:

1. **Census Conquest** — best balance of GIS legitimacy + game feel.
2. **Map Minesweeper** — safest playable prototype.
3. **Tower Defense: Bufferlands** — flashiest but riskier.
4. **Geoprocessing Card Battler** — most conceptually clever for a GIS class.
