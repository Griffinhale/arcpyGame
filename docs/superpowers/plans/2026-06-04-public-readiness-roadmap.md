# Public-readiness roadmap — closing the open issue set

_Date: 2026-06-04. Owner: Griffin. Status: planning._

Snapshot after `fix: render district state changes and add manual End Week`
(commit 22b2b56). District rendering is live-verified; the open issues below are
sequenced into tracks by dependency and by whether they need a live ArcGIS Pro /
`.gdb` session to land safely.

Open issues: #1, #2, #5, #6, #7, #9, #11.

## Sequencing at a glance

```
Track A  Quick closes      #7  ──▶ (verify + flavor, likely near-done)
                           #2  ──▶ (remaining: action copy, exhibits, panel spike)
Track B  Model foundation  #5 (design spike) ──▶ #1 (revenue + health clarity)
Track C  Map / visual      #9 (symbology spike; render pipeline now trustworthy)
Track D  Depth             #6 (district identity buyout deepening + playtest)
Track E  Performance       #11 ──▶ see render-optimization spike (separate doc)
```

Recommended order: **A → B → C → D**, with **E** interleaved whenever a live
ArcGIS session is already open (its items need live verification anyway). #5 is
the one hard dependency: it must land before #1, because #1 implements the stat
model #5 defines.

---

## Track A — quick closes (do first; small, mostly verification)

### #7 — auto-show final scorecard and ending flavor
**Status: likely 80% done in code.** `FINAL_AUDIT_FLAVOR` (PASS/CONDITIONAL/FAIL)
exists in `dashboard.py`, the inline final-audit receipt auto-shows on manual and
timer close, and repeated close is idempotent (covered by
`test_advance_turn_after_final_audit_is_idempotent`,
`test_deadline_final_week_records_same_inline_final_audit_receipt`).

**To close:**
- [ ] Live-verify the **week counter / status label** reads "12/12 CLOSED" (not
  11) in the end flow — the original report was a week-5/6 off-by-one under the
  old 6-week season; confirm it's gone under the 12-week model.
  (`test_completed_game_reloads_inline_final_audit_receipt` already asserts
  `12/12 CLOSED` in the model — verify it on the live banner.)
- [ ] Confirm flavor text surfaces for all three grades in the inline receipt.
- **DoD:** live screenshot of a closed week-12 PASS/CONDITIONAL/FAIL; no new code
  unless the counter bug reproduces.

### #2 — clarify actions, exhibits, help, session controls
**Status: partially done.** Manual End Week added (this commit); End Game,
start/help flow, no-AP ordinary deny, and "Show/Hide Proposed Feature" copy
already exist.

**Remaining:**
- [ ] Strengthen **Issue / Add Conditions / Deny** differentiation in lane copy
  and action notes, per case family (permit / incident / enforcement /
  maintenance). Pure `desk_model` — testable offline.
- [ ] Audit exhibit controls for the "duplicate/contradict" smell (Show/Hide vs
  Retarget vs the bottom state pill).
- [ ] **Spike:** can ArcGIS Pro Contents/geoprocessing panels be opened/arranged
  from Python via a stable API? Implement if reliable, else document as
  unsupported. (Pairs with the #9 live session.)
- **DoD:** new player can tell which buttons spend AP; exhibit controls
  non-redundant; panel automation implemented-or-documented.

---

## Track B — stat-model foundation (#5 then #1)

### #5 — design spike: simplify the city health and stat model
**Deliverable is a design note, not code-first.** The rename to
Activity/Friction/Trust/Exposure already shipped (see desk tests); #5 is about
deciding which metrics are **player-facing audit goals** vs **hidden derived
causes**, and where heat/friction/pressure sit.

- [ ] Write `docs/superpowers/specs/2026-06-…-city-health-model.md`: the
  player-facing four (Activity/Trust + Friction/Exposure), heat as a pressure
  signal, and which district systems are scorecard-only detail.
- [ ] Reconcile dashboard, scorecard, and report wording to one vocabulary.
- [ ] Tests for any renamed/consolidated desk-model rows.
- **DoD:** design note merged; UI/report language consistent; tests green.
- **Blocks #1.**

### #1 — improve revenue forecasts and city health clarity
Implements the #5 model on the cards.
- [ ] Inspected revenue-producing cases show **revenue / upkeep / net** explicitly
  before approval (at minimum once the inspection packet is filed).
- [ ] Heat row explains likely future consequences (incidents / follow-up
  filings) in City Health.
- [ ] Pressure / housing / long rows clip or wrap without drawing over neighbors
  (the `_Stacker` measured layout already exists — extend coverage).
- [ ] Replace the "Filed marks" block with a clearer legend or compact summary.
- [ ] Desk-model formatting tests for each.
- **DoD:** acceptance criteria in #1 met; offline desk-model tests cover it.

---

## Track C — map / visual (#9)

### #9 — design spike: improve map symbology and city-detail rendering
The render pipeline is now trustworthy (districts repaint live), so this is pure
visual design.
- [ ] Decide the **daily-pressure visual channel**: today daily pressure writes
  `display_state` to the districts FC but no district-family layer renders by it
  (base → `district_type`, overlays → `prosperity_band` / `identity_state`). Add
  a dedicated `display_state`-keyed daily overlay, or fold pressure into an
  existing overlay's semantics.
- [ ] Feature-family symbols (housing/business/civic/industrial/academic/
  natural/special-interest/incident/compliance/maintenance) and distinct line
  symbology (road/transit/utility/procession/proposed).
- [ ] Consider bivariate prosperity × maintenance/culture risk **only if** it
  stays legible in Pro.
- [ ] Update pure symbology tests (`test_permit_office_symbology.py`) for new
  classes/style hints; keep proposed-feature visibility intact.
- **DoD:** symbology spike note with live screenshots; no single visual channel
  overloaded; tests green. Do this in the same live session as #2's panel spike
  and Track E's live items.

---

## Track D — depth (#6)

### #6 — playtest and deepen district identity buyouts
Buyouts already exist (transitions, contested/converted identity, type ledger).
#6 is about making types/cultures *matter* and validating the loop.
- [ ] Prefer human-readable district **names** in dashboard/reports/feature
  attributes while keeping `cell_id` as the stable key.
- [ ] District type/culture distribution influences which proposals appear.
- [ ] Playtest the under-50-prosperity → neighbor buyout/bid/refusal loop; tune
  the deterministic seeded formula.
- [ ] Rules tests: no-bid / single-bid / multi-bid / refusal / success.
- [ ] Schema changes stay backward-compatible with existing saves.
- **DoD:** design doc + rules tests for all five cases; buyouts legible from map +
  text without raw-table inspection.

---

## Track E — performance (#11)

See `docs/superpowers/plans/2026-06-04-render-optimization-spike.md`. Summary:
the district-readd correctness fix added a small per-turn cost (re-adding 3
district layers), so the perf budget is worth re-baselining. The highest-value,
**offline-testable** win is memoizing the scorecard grade off the turn boundary
instead of re-normalizing 25 districts + `deepcopy` on every render. Interleave
the live-verification items (cursor IO, Tkinter caching) with the Track C/#2 live
session.

---

## Milestones

1. **M1 — Beta-polish (Track A):** #7 closed, #2 mostly closed. One live session.
2. **M2 — Coherent model (Track B):** #5 note + #1 implemented. Mostly offline.
3. **M3 — Readable map (Track C + E-live):** #9 symbology + the render-spike live
   items, same session.
4. **M4 — Depth + balance (Track D):** #6 deepened and playtested.

Each milestone ends with `python -m pytest -q` green and, for M1/M3, a recorded
live ArcGIS Pro screenshot set added to `docs/`.
