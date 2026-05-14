# GUI-Era Concept Reopen

Date: 2026-05-14

Purpose: reopen the original arcpyGame concept shortlist after the GUI validation spike showed that a short-lived Tkinter control surface can record durable commands, sessions, and dry-run context from ArcGIS Pro.

Ranking lens: most novel game. Reliability and GIS pedagogy still matter, but the tiebreaker is whether the concept becomes a memorable game because the GUI reduces interaction friction.

## What Changed

The original shortlist assumed the GP pane was the only practical controller. That made card hands, action dashboards, resource displays, and placement-heavy ideas look expensive.

The GUI spike changes that assumption in a narrow way:

- It can make action choice, costs, cooldowns, score, turn state, and selected target context much clearer.
- It can persist commands before apply, which makes recovery and idempotency realistic.
- It can act as a command chooser even if live map redraw waits until the dialog closes.
- It does not make ArcGIS Pro a real-time renderer or remove Spatial Analyst / Network Analyst risk.

## Re-Rank Matrix

Scores are 1-5. Higher is better, except dependency risk where 5 means low risk.

| Rank | Concept | Novelty | Game Feel | GIS Fit | GUI Benefit | ArcPy Feasibility | Demo Reliability | Dependency Risk | Verdict |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Spatial Tactics / GP Card Battler | 5 | 4 | 5 | 5 | 3 | 3 | 4 | Reopen as the strongest novelty target. Avoid literal deckbuilding at first. |
| 2 | Containment Commander plus Spatial Tactics powers | 4 | 4 | 5 | 4 | 4 | 4 | 5 | Best hybrid: keeps current architecture while making the final game more distinctive. |
| 3 | Bufferlands / tower tactics | 5 | 5 | 4 | 4 | 3 | 2 | 4 | Reopen only as turn-based tactics, not real-time tower defense. |
| 4 | GeoGuessr ArcGIS Edition | 4 | 4 | 3 | 4 | 4 | 4 | 4 | More viable with placement/guess GUI, but still needs stronger GP-driven clues to be the main project. |
| 5 | Watershed Dungeon Crawler | 5 | 4 | 5 | 2 | 2 | 2 | 1 | Still risky. GUI does not solve raster/hydrology dependency and prep risk. |
| 6 | Census / District Conquest | 3 | 3 | 5 | 3 | 5 | 5 | 5 | Strong alternate, but less novel unless wrapped as a tactics scenario. |
| 7 | Urban Planner / Habitat Corridor | 3 | 3 | 5 | 3 | 4 | 4 | 3 | Feasible, but risks feeling like a dashboard simulation. |
| 8 | RescueOps / Supply Chain | 4 | 4 | 4 | 3 | 2 | 2 | 1 | Compelling theme, but true routing/network logic remains the blocker. |
| 9 | Guildmaster GIS RPG | 4 | 3 | 3 | 3 | 3 | 2 | 3 | GUI helps menus, but narrative/inventory bloat remains likely. |
| 10 | Plain Survey Sweeper | 2 | 3 | 3 | 2 | 5 | 5 | 5 | Keep as fallback and architecture proof, not the novelty winner. |

## Recommendation

Pivot the target concept from "Survey Sweeper into plain Containment" to a hybrid:

**Survey Sweeper fallback -> Spatial Tactics: Containment Board.**

Use the existing board/state/selection architecture, but present the final game as a tactical GIS action game:

- The board has a spreading threat, assets, and turn pressure.
- The GUI control panel shows available GP powers, AP cost, cooldown, selected target count, support layer readiness, and last command.
- Player moves are framed as spatial operations: Buffer Shield, Spatial Join Harvest, Intersect Strike, Suppress Hotspot, and later Clip Quarantine or Dissolve Safe Zone if time allows.
- The first implementation is not a full deckbuilder. It is a fixed action loadout with card-like presentation.

This keeps the safe path intact while giving the final demo a more novel identity.

## Reopened Spike Cases

Add these focused checks to the GUI spike before committing to the pivot:

1. **Spatial Tactics control panel**
   - GUI shows selected targets, support layer, radius, AP/cost placeholders, and action buttons.
   - Records a command row for a card-like action without applying final game rules.
   - Validates targeted selection, support layer, and radius requirements per action.

2. **Placement/guess flow**
   - Add optional `GPFeatureRecordSetLayer` input for drawn placement.
   - Validate whether a drawn point/line/polygon can be counted and logged.
   - Use this as evidence for GeoGuessr, Buffer Defense placement, and treatment/barrier drawing.

3. **Dashboard viability**
   - GUI displays score/turn/action context from current inputs and last command rows.
   - Decide whether it can be the final player control surface or only a command chooser.

## Still Deferred

These remain deferred unless the reopened spike proves unusually strong:

- real-time tower defense ticks,
- literal shuffled deck/hand/discard mechanics,
- live Network Analyst routing,
- live Spatial Analyst hydrology or cost surfaces,
- large boards or many per-turn geoprocessing operations,
- RPG inventory/quest systems.

## Decision Gate

After the reopened GUI spike, choose one:

- **Keep baseline:** Survey Sweeper fallback, deterministic Containment target, one Buffer Defense stretch.
- **Hybrid pivot:** Survey Sweeper fallback, Spatial Tactics: Containment Board target, card-like GUI loadout.
- **Novelty pivot:** Spatial Tactics/Card Battler as primary, with Survey Sweeper only as technical proof.

Default if evidence is mixed: hybrid pivot.
