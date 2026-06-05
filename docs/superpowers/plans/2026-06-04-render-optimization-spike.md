# Render-optimization spike (#11)

_Date: 2026-06-04. Status: spike — verified findings + sequenced plan, no code yet._

## Why now

Two forces meet here:

1. The district-readd correctness fix (commit 22b2b56, ADR-4) **added** per-turn
   cost: every rebuild now removes + re-adds the 3 district-family layers
   (`addDataFromPath` ×3) instead of a bare `RefreshLayer`. That is correct and
   non-negotiable — but it spends part of the budget the original refresh-only
   optimization was trying to save.
2. The #11 sweep already catalogued per-render and per-IO waste, deferred only
   because the suite mocks ArcPy/Tkinter.

**Hard guardrail for every item below:** do not re-introduce the rendering
correctness bug. Any layer whose *rendered* attribute can change must still be
removed + re-added (or otherwise force the data to reload) before its repaint —
`RefreshLayer` alone is never sufficient for attribute changes.

## Verified findings (read against current code, not just the sweep)

| Claim | Verified at | Status |
|---|---|---|
| Scorecard re-normalizes 25 districts + `deepcopy` on **every** `build_desk_model` | `desk_model.py:836` (`rules.scorecard(state, deepcopy(districts), …)` inside `_ledger_rows`) | ✅ confirmed — top win |
| `_fit_px` re-runs the text-fit binary search every frame, no memo | `desk_view.py:770-795` | ✅ confirmed |
| `_draw_*` rebuild `action_id→lane` / `label→row` dicts per frame | e.g. `desk_view.py:545` (`lanes = {lane.action_id: lane …}`) | ✅ confirmed |
| District-readd re-adds the family even when no rendered field changed | `dashboard.py rebuild_output_layers` (this commit) + `_decision_layer_names` always includes `DISTRICTS` | ✅ new cost, addressable |
| Cursor IO items (`write_district_updates`, `write_active_features`, `selected_cell_ids`, …) | `store.py` / `geometry.py` line refs in #11 | ⏳ not re-read this pass; trust #11, verify against live `.gdb` |

## Sequenced plan (by value × verifiability)

### Phase 1 — offline-testable, highest value (no live session needed)

1. **Memoize the scorecard grade off the turn boundary.** `_ledger_rows` only
   needs the *grade* for the "Audit" row, yet recomputes the full audit (loop +
   `normalize_profile` + aggregation) and throws away a `deepcopy` on every
   reload/hover-driven render. **Fix:** compute the grade once on turn-advance,
   stash it on `CityState` (or memoize on `(state, districts)` identity),
   invalidate on turn boundary. **Test:** Audit row matches turn-advance output
   across a full 12-week seed-2026 route and updates each week. *(This alone is
   likely the single biggest real win and needs no live ArcGIS.)*
2. **Pure `desk_model` constant-factor items** (#10/#17/#33/#34 in #11):
   forecast computed once per build, `max`/`heapq` single-winner instead of
   `sorted()[0]`, replace-only the changed report tab, reuse the `active_items`
   count + frozenset `ACTIVE_STATUSES`. All covered by the existing suite.
3. **`read_state` double-subscript** (`store.py`) — trivial, pure, testable.

**Exit Phase 1:** `python -m pytest -q` green; optionally capture a before/after
`PERMIT_OFFICE_PERF=1` tree on a scripted reload to quantify (1) and (2).

### Phase 2 — dirty-district readd (the cost this fix added)

4. **Only re-add the district family when a rendered field actually changed.**
   The rendered district fields are `district_type`, `prosperity_band`,
   `identity_state` (per `RENDER_FIELD_BY_LAYER_KEY`). Have
   `write_district_updates` report whether any of those changed; when none did,
   fall back to refresh-only for districts that turn. **Risk:** this is exactly
   where the original bug lived — the dirty check must be conservative (any doubt
   → readd). **Test:** a turn that changes `identity_state` triggers readd; a
   turn that changes only a non-rendered field (e.g. `buyout_pressure`) does not.
   Pair with a live check before trusting it.

### Phase 3 — live UI verification (Tkinter; needs a real window)

5. **Cache `_draw_*` lookup dicts on the model**, rebuild on model swap only.
6. **Memoize `_fit_px`** on `(text, size, weight, max_px)`, clear on model
   change. ~1 redraw/s + per hover today.
7. **Drop the residual `reload` proposal-visible comprehension** if
   `build_desk_model` tolerates missing keys as False.

**Exit Phase 3:** live UI feels no worse (ideally smoother) on hover/redraw;
`PERMIT_OFFICE_PERF=1` shows reduced per-frame time.

### Phase 4 — adapter cursor / IO (needs a live `.gdb`, ideally a legacy one)

8. `write_district_updates`: scope normalize + JSON encode to a **dirty set**
   (normalize idempotency already proven offline for seed-2026).
9. `write_active_features`: `WHERE IN` the matched ids / skip cursors on classes
   with no matches.
10. `selected_cell_ids`: try the known `cell_id` column directly, fall back to
    `ListFields` only on cursor error.
11. `_suggest_targets`: `heapq.nsmallest(2, …)` for POINT/POLYGON (LINE keeps the
    full sort) — **must not change RNG draw order.**
12. `_clamped_int_map` / `encode_*`: hoist frozensets, drop the redundant inner
    sort — verify no decode caller relies on dict iteration order.

**Exit Phase 4:** behavior identical against an existing `.gdb` (saved-game
round-trip + a walked week); perf tree shows reduced write/IO time.

## Notes / caveats

- The #11 sweep is partly LLM-sourced: re-verify each complexity claim against
  the code before acting (the rules-layer `sorted()[0]→min()` items were correct
  only as `min`, not `max`). Phase-1/2 claims above were re-read this pass; the
  Phase-4 line refs were not and should be confirmed when the `.gdb` is open.
- Phases 1–2 are mergeable from this dev box. Phases 3–4 should ride the same
  live ArcGIS session as roadmap Track C (#9) and Track A (#2 panel spike) so one
  session clears multiple live-verification debts.
