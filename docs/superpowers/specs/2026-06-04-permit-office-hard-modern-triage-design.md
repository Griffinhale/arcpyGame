# Permit Office Hard-Modern Triage Design

Date: 2026-06-04
Status: Approved for implementation

## Problem

The Permit Office dashboard now has the right information architecture:
applications and filed reports share one workspace, and selecting an application
controls the map context. The visual and workflow model still fights the goal.

The current screen reads like a paperwork sim:

- A global action bar dominates before the player has read the selected case.
- The selected application is still a permit data sheet, not a decision brief.
- City Health is a co-equal ledger panel instead of a light operational pulse.
- Filed Reports steals focus after normal decisions, interrupting triage.
- The parchment/border visual vocabulary makes tabs, cards, buttons, reports,
  and ledger rows feel equally important.

The desired direction is a serious civic operations dashboard. The game remains
in the rules, consequences, and score moments rather than in decorative paper UI.

## Goals

- Make the selected application the primary triage surface.
- Turn the selected application into a decision brief: consequences first,
  metadata second.
- Move all case controls inside the selected application card.
- Keep normal decisions on the Applications tab.
- After a decision, file the report in the background, auto-select the next open
  application, and update map highlighting for that next case.
- When the queue clears, show a queue-cleared state with End Week primary and a
  3-second auto-close countdown.
- Allow implicit pause and explicit cancellation of that auto-close.
- Apply auto-close to all weeks; the final week files and opens the final audit.
- Compress City Health to a slim pulse rail.
- Hard-modernize the Canvas visual system: neutral operational surfaces,
  restrained semantic color, fewer outlines, calmer spacing.

## Non-Goals

- No migration from Tkinter Canvas to ttk/grid in this pass.
- No new gameplay rules.
- No redesign of ArcGIS map symbology.
- No full accessibility rewrite for keyboard or screen readers; Canvas remains
  the current rendering surface.

## Decisions

| Topic | Decision |
| --- | --- |
| Primary job | Triage one selected application and choose an action. |
| Visual tone | Serious civic operations dashboard. |
| Modernization depth | Hard modernization; current parchment theme is retired. |
| Header | Keep Permit Office name and metrics, but modernize typography/spacing. |
| Application card | Decision brief with action consequences. |
| Case controls | All selected-case controls live inside the application card. |
| Inspection | Optional intelligence; uninspected decisions remain enabled and flagged as uncertain. |
| Application tabs | Compact queue tabs, not mini cards. |
| City Health | Slim pulse rail with four signals and one ticker line. |
| Filed Reports | Read-only history/archive; scorecard and week summaries live there. |
| Normal decisions | Stay on Applications and file report tabs in the background. |
| Next selection | Auto-select next open application and update map highlight. |
| Empty queue | Start a 3-second auto-close state with End Week and Cancel Auto Close. |
| Auto-close pause | Pause implicitly when user leaves Applications or opens the utility menu. |
| Final week | Queue-clear auto-close files final audit and opens the audit report. |

## Information Architecture

Top to bottom:

1. Modern header: product name, week/AP/money/heat/audit/press/deadline.
2. Status strip: one ambient or action-confirmation sentence.
3. Main workspace:
   - Applications and Filed Reports primary tabs.
   - Utility menu in the workspace header.
   - Applications tab shows compact queue tabs and the selected decision brief.
   - Filed Reports tab shows report tabs and selected report body.
4. Slim City Health rail beside the workspace.

No global case-action bar remains. The selected application owns:

- Hide/Show Proposed
- Retarget Map
- Inspect File
- Issue Permit / Respond
- Add Conditions / Settlement
- Deny / Defer

## Decision Brief

The selected application card should read in this order:

1. Title, open status, received badge, risk band.
2. One-line case brief and affected district line.
3. Uninspected uncertainty banner when inspection is missing.
4. Three action consequence lanes:
   - Approve / Respond
   - Add Conditions / Settlement
   - Deny / Defer
5. Secondary case tools: proposed exhibit, retarget, inspect.
6. Primary stamp actions.

Before inspection, consequences are estimates. After inspection, risk/evidence
replaces the uncertainty banner and can sharpen consequence text.

## Controller Behavior

Normal decision flow:

1. Resolve and persist the decision.
2. Append a filed-report tab, but keep `selected_desk_tab = "applications"`.
3. Select the next open application if one exists.
4. Call the existing `select_case_context` path for the next selection so map
   highlighting follows the selected application.
5. If no open applications remain, enter queue-cleared state and schedule
   auto-close after 3 seconds.

Queue-cleared flow:

1. Application workspace shows "Queue cleared".
2. End Week is primary.
3. Cancel Auto Close is secondary only while the countdown is active.
4. Switching to Filed Reports or opening the menu pauses the countdown.
5. Cancel Auto Close clears the countdown and keeps the empty queue state.
6. End Week or countdown expiry calls the existing `advance_turn()` path.
7. On the final week, the final audit report opens in Filed Reports.

## View Model Additions

Additive fields only:

- `action_lanes`: consequence summaries for approve, conditions, deny.
- `queue_cleared`: whether no active applications remain.
- `auto_close_active`: whether countdown is running.
- `auto_close_seconds`: countdown display value.

Existing `report_tabs`, `selected_desk_tab`, and selected item fields remain.

## Testing Strategy

- Model tests for action lanes and queue-cleared fields.
- Controller tests for:
  - normal decisions remain on Applications,
  - report tabs are filed in the background,
  - next open application auto-selects,
  - next selection calls map context,
  - queue clear schedules auto-close,
  - cancel clears the scheduled auto-close,
  - switching to reports pauses auto-close,
  - final week auto-close opens final audit.
- View tests with fake Canvas for:
  - no global case-action bar targets,
  - compact queue tabs,
  - decision lanes,
  - slim pulse rail,
  - queue-cleared state controls.

Manual ArcGIS verification remains required for final visual judgment because
the Canvas is image-like and live Tk font metrics differ from headless tests.
