# District Identity, Spread, and Buyouts Design

Date: 2026-06-03

Related issue: [#6](https://github.com/Griffinhale/arcpyGame/issues/6)

## Purpose

Districts should stop feeling like interchangeable `D0002` cells. They should act like named parts of the city with visible identity, local momentum, and neighboring pressure. The player should not directly manage factions. Instead, the city should reveal identity shifts through map symbology, filed reports, proposed permits, and occasional follow-up cases.

The target feel is a permit-office game where AP means institutional attention. The player cannot handle every docket item. What they inspect, approve, mitigate, deny, and ignore should all shape the simulation.

## Approved Direction

- Use a 12-week civic season instead of the current 6-week demo pacing.
- Keep AP scarce: more docket items appear than the player can fully handle.
- Prefer a hybrid buyout model:
  - Visible layer: districts change identity/type on the map.
  - Hidden layer: district types/cultures have abstract capital, appetite, fatigue, and overextension pressure.
- Keep the hidden layer mostly out of the dashboard.
- Use identity-first map symbology:
  - District fill primarily shows district type/identity.
  - Vulnerability, contested status, and recent conversion are secondary signals.
- Use a one-week contested transition before a successful buyout fully converts a district.
- Use mixed expiration by docket template:
  - Some ignored items are missed windows.
  - Some become city momentum.
  - Bad momentum can later spawn different follow-up dockets.
- Treat informal or "ghost" map features as a playtest variable, not a guaranteed first-pass requirement.

## Current Code Fit

The design should build on existing hooks rather than introduce a parallel engine.

- `CityState` currently owns turn count, AP, money, city metrics, heat, and daily pressure.
- `DistrictProfile` already owns district name, type, prosperity, unrest, culture, risk, adjacency, housing, hazards, public profile, and `display_state`.
- `DocketTemplate` already owns category, effects, AP/money cost, stakeholder, failure behavior, fit types, and optional expiration.
- `advance_turn_result` already resolves unresolved docket items, recurring systems, incidents, economy, audits, and final-week status.
- `profiles.generate_docket` already centralizes docket generation and should become the main place where district identity affects proposals.
- `symbology_config.py` already supports unique-value district rendering, currently keyed by `display_state`.

## Season And Attention

The 12-week season exists to support warning, response, and consequence.

Recommended pacing:

- `CityState.max_turns = 12`.
- Baseline AP: `max_ap = 2`.
- Visible docket rows: usually 3-4 per week.
- Deny should cost 0 AP.
- Inspect, issue, and mitigation should still cost AP.
- Some weeks may contain mandatory follow-up rows, but those should replace ordinary proposal rows rather than simply increasing workload.

Mid-season audit:

- Current audit snapshot logic is tied to week 3.
- In a 12-week season, move the main mid-season audit checkpoint to week 6.
- Final audit should file at week 12 and auto-open the scorecard as a separate UI issue.

## District Identity

Each district keeps `cell_id` as its stable save/feature key. The player-facing name should be the district's human name.

Existing generated names should remain valid, but the identity system should add state for:

- Current dominant type: the existing `district_type`.
- Prior type: the type before a buyout transition.
- Identity state: `stable`, `vulnerable`, `contested`, `converted`, or `overextended`.
- Contesting neighbor: the winning bidder's `cell_id`, if any.
- Contesting type: the winning bidder's district type/culture.
- Transition due turn: the week when a contested district will convert if not interrupted.
- Buyout pressure: hidden numeric signal used for reports and symbology.
- Last buyout report: compact text for map popups and filed reports.

Persist renderer/query state as explicit district fields. Use a compact district-state JSON field only for secondary report details that do not drive map styling. Do not rely on `last_report` as the only persistence mechanism for buyout state.

## Hidden Type Ledger

The hidden ledger is not a player-facing faction table. It should explain why types expand, stall, or overreach.

Per district type/culture, track:

- `capital`: abstract ability to bid and absorb new territory.
- `appetite`: willingness to expand this week.
- `fatigue`: accumulated penalty from repeated expansion or recent losses.
- `holdings`: count of districts currently dominated by that type.
- `overextension`: pressure created when a type expands faster than its prosperity can support.

Suggested persistence:

- Store the ledger as a JSON value in `PermitGameState` under a key like `type_ledger`.
- Rebuild missing ledger values from districts on load for backward compatibility.
- Keep values deterministic from city seed and current game state.

Player visibility:

- Do not add a dashboard ledger table.
- Allow filed reports, map notes, and the ticker to mention qualitative pressure, such as "Market offices are spreading along weak residential edges."
- City Health may show at most one short sentence about dominant pressure, not a new stat grid.

## Buyout Eligibility

At week close, after unresolved docket expiration/momentum and recurring systems have updated districts, identify eligible targets.

A district is eligible when:

- `prosperity < 50`.
- It has at least one adjacent district.
- It is not already in `contested` transition.
- It is not protected by a current critical incident or explicit template effect.

Candidate bidders are adjacent districts where:

- Bidder prosperity is greater than target prosperity by at least 8.
- Bidder type differs from target type.
- Bidder type ledger has positive capital and appetite.
- Bidder is not itself contested.

## Bid And Refusal Formula

Use seeded deterministic RNG so the same seed and same choices produce the same result.

Recommended RNG key:

```text
seed + week + target_cell_id + sorted(candidate_cell_ids) + target_prosperity + ledger snapshot hash
```

Target leverage:

```text
leverage = clamp(0, 100,
  target.prosperity
  + target.services / 2
  + target.culture / 3
  - target.unrest / 2
  - target.risk / 3
)
```

Bid strength:

```text
base_bid = bidder.prosperity
  + ledger.capital / 3
  + ledger.appetite
  - ledger.fatigue
  - ledger.overextension
  + adjacency_bonus
  + rng(-8, 8)
```

Refusal threshold:

```text
refusal_threshold = 35 + leverage / 2 + rng(-10, 10)
```

Result:

- If no bid clears threshold, no transition starts.
- If one bidder clears threshold, start a contested transition.
- If multiple bidders clear threshold, choose the highest bid.
- Deduct a portion of the winning bid from hidden capital.
- Increase winner fatigue and overextension.
- Add a filed report describing winner, target, leverage, and why it happened.

These constants are starting values only. They should be playtested against the new 12-week pacing.

## Contested Transition

A successful buyout should not immediately flip the district.

Week N:

- Buyout bid succeeds during week close.
- District identity state becomes `contested`.
- Map shows the target with its current type fill and a contested/vulnerability outline.
- Filed report names the winning neighbor/type and explains the pending conversion.

Week N+1:

- The district remains targetable by normal docket items.
- Approving stabilizing services, civic responses, mitigation, or relevant permits can reduce pressure.
- Ignoring or mishandling relevant items can increase pressure.

Week N+1 close:

- If pressure is still high, convert the district:
  - `prior_type = old district_type`
  - `district_type = contesting_type`
  - `identity_state = converted`
  - rename or suffix the district using a type-specific naming table
  - adjust prosperity/unrest/risk/culture with transition effects
  - update ledger holdings, fatigue, and overextension
- If pressure is reduced enough, cancel the transition:
  - `identity_state = stable`
  - clear contesting fields
  - bidder loses some capital or appetite
  - target gets a temporary resilience note

## Docket Generation

Docket variability should come partly from the board.

For ordinary proposal slots:

1. Build a weighted pool from all eligible templates.
2. Weight templates by district type holdings and target fit:
   - More mercantile districts increase business/development proposals.
   - More industrial districts increase utility, maintenance, inspection, and worker proposals.
   - More civic/academic districts increase public service, culture, transit, and incident proposals.
   - More natural districts increase reserve, buffer, hazard, and conservation proposals.
3. Add pressure modifiers:
   - Low prosperity increases development, fee, buyout, and enforcement pressure.
   - High unrest increases civic incident and mitigation pressure.
   - High risk increases utility, fire, inspection, and maintenance pressure.
4. Shuffle final docket order with seed, week, and current city state.
5. Reserve slots for mandatory follow-ups, but avoid allowing follow-ups to clog the entire week.

Target selection should also prefer districts whose type, pressure, and adjacency match the template.

## Docket Expiration

Replace the current parity-based carry/expire behavior with explicit template policy.

Add a template-level expiration policy such as:

- `missed_window`: original item expires; opportunity is lost; heat and ledger shift.
- `city_momentum`: original item expires; district pressure, hidden ledger, and any template-specific map state change.
- `momentum_with_followup_risk`: original item expires; momentum may later spawn incident, enforcement, inspection, or maintenance.
- `mandatory_followup`: only for critical systems that truly must return, such as maintenance or project steps.

The user-approved default is a mix of missed window and city momentum, with follow-ups spawned only when unattended momentum goes badly.

Docket cards should hint at expiration without adding dashboard overload:

- "Filing window closes this week."
- "If ignored, district momentum may continue without permit review."
- "If unmanaged, may return as incident or inspection."

## Momentum And Ghost Features

Momentum means the city moved without the office.

First-pass default:

- Use district pressure and map symbology for most momentum.
- Do not draw a feature for every ignored permit.

Playtest variable:

- Some templates may create informal or ghost features, such as an unpermitted market, construction site, or event residue.
- Ghost features must be limited by template and should use clear `display_state` values like `informal`, `unpermitted`, or `provisional`.
- If playtesting shows clutter, keep the effect as district pressure/report text only.

## Map Symbology

The base district map should be identity-first.

Preferred rendering:

- Primary fill: `district_type`.
- Secondary state: outline, hatch, marker, or label class for `vulnerable`, `contested`, `converted`, and `overextended`.
- Current incidents, hazards, service gaps, and housing pressure must still be visible, but they should not erase district identity permanently.

Implementation implication:

- Current district rendering is unique-value and keyed by `display_state`.
- Prefer a second district overlay layer for pressure/transition state so the base district layer can render `district_type`.
- If ArcGIS layer management makes the overlay unreliable, fall back to a switchable renderer between `district_type` and `display_state`, with identity as default.
- Avoid using `display_state` alone for all meanings because it already carries incident, hazard, service gap, housing pressure, grievance, and daily docket pressure.

## Reports And Ticker

Filed reports should carry most of the hidden-system explanation.

Buyout report should include:

- Target district name.
- Winning neighbor/type.
- Whether the target accepted, refused, or entered contested transition.
- One plain-language reason:
  - "low prosperity left the district with little leverage"
  - "Market capital is high along the corridor"
  - "service gaps weakened the local board"
  - "overextended bidders declined to counter"

Ticker messages should be absurd but value-driven:

- Use real district names, prosperity, unrest, risk, type, and contested state.
- Keep messages decorative, not required for strategy.
- Avoid adding new stats to the dashboard to explain the hidden ledger.

## Winning And Balance

The 12-week season and AP scarcity should be balanced so winning is slightly more likely than losing under reasonable play.

Balance goals:

- Ignoring everything should fail.
- Responding to every profitable proposal should create risk and overextension problems.
- Responding to selected high-pressure items should stabilize enough districts to win.
- Buyouts should sometimes help the city by improving weak districts, but excessive expansion should create overextension and new follow-ups.

Initial playtest targets:

- In a default seed, average unresolved items per week: 1-2.
- At least one buyout warning should appear in most runs.
- Most runs should see 0-3 full conversions, not the entire board flipping.
- Reasonable play should land near a conditional/pass audit, not inevitable failure.

## Acceptance Criteria

- District dashboard/map labels use human-readable names while preserving stable `cell_id` keys.
- A 12-week season runs to a week-12 final audit without the week counter getting stuck.
- Docket generation order and template mix vary by seed and by district type distribution.
- More districts of a type naturally increase related proposal frequency.
- Unresolved docket items use explicit expiration policy instead of parity-based carry/expire behavior.
- Ignored items can expire, create momentum, or spawn later different follow-up cases according to template policy.
- Low-prosperity districts can enter a contested buyout transition from adjacent stronger districts.
- Buyout bidding is deterministic for a seed and current game state.
- Buyout reports explain accepted, refused, and converted outcomes in player-readable text.
- Map defaults to district identity and uses secondary symbology for contested/vulnerable pressure.
- Hidden ledger does not require a new dashboard table.
- Ghost/informal features are template-limited and can be disabled if playtesting shows clutter.

## Test Plan

Pure rules tests:

- No eligible target: no buyout report and no district identity changes.
- Eligible target with no valid bidders: no transition.
- Single bidder clears threshold: contested transition starts.
- Multiple bidders clear threshold: highest deterministic bid wins.
- Target refuses: bidder capital/appetite changes, target remains stable.
- Contested district stabilizes before due turn: transition cancels.
- Contested district remains weak: district converts at due turn.
- Conversion updates type, prior type, name/report fields, ledger holdings, fatigue, and overextension.
- Expiration policy `missed_window`: original item expires and does not return.
- Expiration policy `city_momentum`: original item expires and district pressure changes.
- Expiration policy `momentum_with_followup_risk`: bad momentum can spawn a different follow-up item.
- Docket generation varies by seed and district type distribution while remaining deterministic.

ArcGIS/store tests or smoke checks:

- New fields or JSON state survive save/load from existing geodatabases.
- Missing ledger/identity fields backfill safely for older saves.
- District symbology remains readable with identity fill plus contested/vulnerable state.
- Proposed/active support feature layers do not become visually ambiguous with ghost features enabled.

Playtest checks:

- Does the player understand why a district became contested?
- Does 2 AP with 3-4 docket rows feel like meaningful attention scarcity or arbitrary deprivation?
- Do ignored items feel consequential without clogging the docket?
- Does map-first pressure stay readable without dashboard tables?
- Do ghost features improve legibility or make the map too busy?
- Does the default seed become winnable with reasonable play?

## Scope Boundaries

Included:

- District identity fields and naming behavior.
- Hidden type ledger.
- Buyout eligibility, bidding, refusal, contested transition, and conversion.
- Docket weighting by district type and pressure.
- Explicit unresolved-item expiration behavior.
- Map-first reporting/symbology requirements.
- Tests and playtest questions.

Not included in this spec:

- Full dashboard redesign.
- Full city health stat simplification.
- Final scorecard auto-open behavior.
- Complete map symbology redesign for every support feature class.
- Start/help screen implementation.

Those remain related issues and should be planned separately or as dependent follow-ups.
