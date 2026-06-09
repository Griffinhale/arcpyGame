# ArcGIS Pro smoke checklist (beta)

Run this in a live ArcGIS Pro session before tagging a beta. It validates the
ArcGIS-side behavior the offline pytest suite cannot (real `.gdb` writes, layer
repaint, symbology, resume). Each item lists the action and the pass condition.
Capture a screenshot for the starred (*) items.

Toolbox: `toolbox/arcpy_permit_office.pyt` -> "Permit Office Prototype".
Tip: keep the Geoprocessing message log open; several checks read its tagged
lines (`[WORKSPACE]`, `[REBUILD]`, `[DASH]`, `[SYM]`).

## 0. Pre-flight
- [ ] ArcGIS Pro module cache is fresh: the `.pyt` reload loop at the top of
      `arcpy_permit_office.pyt` lists every `permit_office_arcgis/*` module in use
      (no new modules were added this round, so no change is expected).
- [ ] `python -m pytest -q` is green on the dev box (offline baseline).

## 1. Workspace resolution (respects the optional param)
- [ ] Run with **Game Workspace empty**. Log shows
      `[WORKSPACE] no workspace given; using project default: ...\data\permit_office.gdb`
      and the existing save resumes (or a start screen appears if none).
- [ ] Run with **Game Workspace = a fresh/empty folder or .gdb**. Log shows
      `[WORKSPACE] using provided game workspace: <that path>` and a NEW game is
      offered/started there. It must NOT load the project-default game.
- [ ] Re-run pointing at the same provided workspace: it resumes that game (not
      the default).

## 2. Cold-start resume *
- [ ] Close Pro entirely, reopen, run the tool against an existing save.
- [ ] The dashboard resumes at the correct week (e.g. `11/12`), the docket is
      populated, and the map shows the full board (districts + features).
- [ ] **Regression (grievance crash):** resume a save whose selected case targets
      two or more districts that share an aggrieved citizen group. The desk opens
      without an `IndexError` in `target_population_hint`; the case brief reads
      e.g. "Existing grievance file: renters are aggrieved."

## 3. District + feature repaint *
- [ ] Approve a case. The affected district family repaints (base
      `district_type`, prosperity overlay, identity overlay) and any new/updated
      feature shows. Log shows `[REBUILD] ... mode=district-readd ...` and, with
      perf enabled, `experiment_predrawn-rehydrate=...`.
- [ ] Advance a week (or let the deadline fire). Districts whose state changed
      repaint; converted/contested districts show their new fill + name.
- [ ] Confirm the board never goes blank / lines-only after an action (the
      Phase-2 dirty-readd and volatile-overlay experiments could leave the board
      stale/incomplete -- rehydrate must keep a complete district board visible).

## 4. Symbology (#9) *
- [ ] On launch the log emits the six `[SYM] set ... unique-value symbology on ...`
      lines (PermitDistricts/Points/Lines/Zones + District Prosperity + District
      Identity).
- [ ] District base renders by `district_type`; the Prosperity overlay by
      `prosperity_band`; the Identity overlay by `identity_state`.
- [ ] Feature layers render by `display_state`; proposed-feature exhibits stay
      visible when toggled on and hide when toggled off.

## 5. Daily-pressure channel
- [ ] Advance through a work-week's days. Daily pressure writes `display_state`
      to districts; confirm the chosen daily overlay reads as intended (or note
      it as a #9 follow-up if no dedicated daily channel renders yet).

## 6. District identity / buyouts (#6) legibility
- [ ] Play several weeks. When a low-prosperity district is contested/converted,
      the ticker + filed report name the district and the rival bidder(s) in plain
      names (no raw `D0000` ids in any player-facing text).
- [ ] A converted district shows its new type-flavored name and new fill, and its
      docket starts surfacing new-type-flavored proposals over time.

## 7. Audit-grade cache (item B)
- [ ] Make a decision: the City Pulse **Audit** row updates mid-week to reflect
      the new grade (cache invalidates on decision/turn writes).
- [ ] Select different docket rows / retarget from the map without deciding: the
      Audit grade stays put and the desk still feels responsive (selection-only
      reloads reuse the cached grade instead of recomputing the scorecard).

## 8. Legacy .gdb migration
- [ ] Open an older save (pre-rename `.gdb` if available). It loads without error;
      legacy city-health columns backfill (see `migrate_legacy_city_health_fields`)
      and no new persisted fields are required (this round added none).

## 9. End-of-game flow (#7)
- [ ] Reach week 12 / deadline. The inline final-audit receipt auto-shows with
      PASS/CONDITIONAL/FAIL flavor; the week label reads `12/12 CLOSED`. Repeated
      End Week after close is idempotent (no duplicate receipts).

## 10. Pacing and redraw budget
- [ ] Start a game with `PERMIT_OFFICE_PERF=1`. Confirm the filing deadline is
      2:30 and each office day lasts about 30 seconds.
- [ ] Let the week advance from Monday to Tuesday. Confirm the desk status names
      rising pressure, and the log does not show a district re-add unless a
      configured checkpoint is reached.
- [ ] Let the week advance to a configured checkpoint. Confirm the log includes
      `[REBUILD] targeted=['PermitDistricts'] mode=district-readd dirty=districts`.
- [ ] Record timings for a normal decision and a checkpoint tick:
      `experiment_predrawn-rehydrate` and total `rebuild`. If rehydrate reports a
      warning and falls back, record `remove`, `add`, `refresh` too.

## 11. Redraw experiments
- [ ] Default path: leave **Redraw Experiment = None** and confirm district-dirty
      redraws still use `predrawn-rehydrate` in the perf log.
- [ ] Volatile overlay experiment: keep as a probe only. Confirm whether it still
      drops non-overlay districts; do not promote unless the full board remains
      visible.
- [ ] ArcGIS alternative-path experiment: test definition query swap, layer-file
      apply, CIM renderer edit, in-memory layer, and apply-symbology-from-layer.
      Record whether each path reloads changed visual state correctly.
- [ ] Pre-drawn visibility swap experiment: confirm it is still fast, but reject
      it as default if district symbology stays stale.
- [ ] Pre-drawn rehydrate path: record seed cost, hot-path cost, resume behavior,
      Contents clutter, and runtime swap timing. Current live evidence promoted
      it as default because it preserved district symbology with lower rebuild
      cost than district-family remove+add.
- [ ] Promote no experiment unless it preserves visual correctness after GDB
      writes and reduces live redraw time versus the baseline.

---
**On any failure:** capture the Geoprocessing message log + a screenshot, note the
exact step, and file it. Items 2 (grievance), 1 (workspace), 3 (repaint), and 7
(grade cache) cover changes made this session and are the highest-priority checks.
