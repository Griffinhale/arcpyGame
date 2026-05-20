# Permit Office Demo Script

Purpose: rehearse the seed `2026` Permit Office demo inside ArcGIS Pro as a six-turn office run, not a sandbox tour.

## Objective

Show the core dashboard-map loop in a stable order:

- Point, line, and polygon proposals appear by turn 3.
- The player inspects one case, approves one case, approves one case with mitigation, denies cases, and processes one generated follow-up.
- The final audit is `CONDITIONAL`, with positive money and remaining service, incident, displacement, and maintenance findings.

## Setup

1. Open ArcGIS Pro and add `toolbox/arcpy_permit_office.pyt`.
2. Run `Permit Office Prototype` with action `Ping Environment`.
   - Expected result: the GP pane confirms the workspace and loaded docket templates.
3. Run action `New Game` with random seed `2026`.
   - Expected result: `PermitDistricts`, `PermitPoints`, `PermitLines`, and `PermitZones` are added to the map.
4. Open the `PermitDistricts` attribute table or labels enough to identify these route districts:
   - `D0102` Civic Green, mercantile
   - `D0101` Lower Annex, civic
   - `D0004` Glass Row, industrial
   - `D0104` Civic Market, industrial
   - `D0200` Old Yard, natural
   - `D0304` Glass Steps, natural
   - `D0000` Civic Green, residential
   - `D0001` Cinder Yard, mercantile
5. Run action `Open Dashboard`.

## Steps

For each decision, click the listed docket row first. The row selects its seeded proposal and target districts on the map. If the listed district selection differs from the seeded target, select the listed district or districts on the map and click `Update From Map`, then click the listed dashboard action. Items marked `Advance` are intentionally left open until `Advance Turn`.

| Turn | Docket item | District selection | Action | Expected result |
| --- | --- | --- | --- | --- |
| 1 | Street Vendor Compact | `D0102` | Inspect, then `Approve + Mitigate` | `PermitPoints` gets an active vendor point. AP drops for inspection and approval. Report emphasizes mitigated nuisance risk, prosperity, culture, and any computed spillover. |
| 1 | Connector Corridor Pilot | `D0101`, `D0102` | `Approve` | `PermitLines` gets an active corridor. Report shows access/prosperity gain and risk relief. |
| 1 | Licensed Procession Route | none | Advance | Leaving it open adds small celebrant heat when the turn advances. |
| 2 | Utility Expansion Trench | `D0004`, `D0104` | `Approve` | `PermitLines` gets an active utility trench. Report shows industrial service/risk improvement. |
| 2 | Contractor Renovation Waiver | `D0000` | `Deny` | No permit feature is activated. Report shows avoided project risk and contractor heat. |
| 2 | Public Art and Museum Grant | none | Advance | Arts heat is acceptable; save budget for the reserve and follow-up. |
| 3 | Maintenance Order: Vendor Market | `D0102` | `Approve` | Generated follow-up appears in the docket. Report shows the vendor market condition repaired and a new due turn. |
| 3 | Natural Reserve Conversion | `D0200`, `D0304` | `Approve` | `PermitZones` gets an active protected reserve polygon. Report shows culture gain and risk relief. |
| 3 | Mixed-Use Rezoning Petition | none | Advance | Developers gain heat, preserving the audit tradeoff. |
| 4 | Civic Incident Response: Commuters | `D0001` | `Approve` | `PermitPoints` gets an incident marker. Report shows unrest/risk relief and names commuters as the target group. |
| 4 | Child Development Park Annex | `D0000` | `Deny` | No annex point is activated. Report shows family heat and budget restraint. |
| 4 | Street Vendor Compact | `D0102` | `Deny` | Avoids duplicating the already active vendor market. Vendor heat rises. |
| 5 | Maintenance Order: Vendor Market | none | Advance | Leave this open to preserve final cash; it becomes a scorecard maintenance finding. |
| 5 | Civic Incident Response: Families | none | Advance | Leave unresolved as an audit beat. |
| 5 | Connector Corridor Pilot | none | Advance | Optional show/hide only. Do not approve; budget is reserved for a stable scorecard. |
| 6 | Maintenance Order: Connector Corridor | none | Advance | Leave unresolved as the visible maintenance backlog. |
| 6 | Civic Incident Response: Commuters | none | Advance | Final unresolved civic file remains in the audit. |
| 6 | Civic Incident Response: Families | none | Advance | Final unresolved civic file remains in the audit. |

After turn 6, run `Show Scorecard`.

## Expected Result

- Layer changes:
  - `PermitPoints`: active vendor point and responded civic incident marker.
  - `PermitLines`: active connector corridor and utility trench.
  - `PermitZones`: active protected reserve polygon.
  - Later maintenance/civic cards seed proposed rows automatically; unresolved proposals can remain visible or be hidden with `Hide Exhibit`.
- Report beats:
  - Turn 1: inspection risk band appears on the vendor card; mitigated approval shows prosperity/culture with reduced nuisance.
  - Turn 2: utility approval visibly lowers risk; contractor denial creates a clean tradeoff.
  - Turn 3: vendor maintenance proves the docket is generated from active city state; reserve approval shows the first polygon.
  - Turn 4: civic incident response lowers unrest/risk; two denials show AP/budget triage.
  - Turn 5 and 6: advancing unresolved items creates an intentional audit backlog rather than a failure cascade.
- Final scorecard:
  - Expected grade: `CONDITIONAL`.
  - Expected stable summary from pure rules: `score=56`, money `15`, prosperity `60`, unrest `21`, culture `46`, risk `7`.
  - Expected findings: citywide service gap, visible civic incident files, displacement pressure, and active feature maintenance review; `0 critical`.

## Failure Notes

- If an exhibit does not draw immediately, use the layer refresh or reopen the dashboard; proposed geometry is seeded from filed targets and replaced only by `Update From Map`.
- If the wrong item is selected, close the dashboard without advancing, reopen it, and reselect the docket row.
- If money is lower than expected, skip optional exhibit toggles and leave turn 5 and turn 6 items unresolved. The rehearsed ending depends on not spending the last reserve.
- If the final scorecard differs, rerun `New Game` with seed `2026`; route order depends on that seed and the generated active-feature follow-ups.
- Live ArcGIS Pro smoke verification is still manual; pure Python regression coverage locks the route state and scorecard outcome.
