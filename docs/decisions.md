# Architecture Decision Records

Concise record of the load-bearing choices and the alternatives tried and
rejected — so they aren't re-litigated from scratch. Each entry: the decision,
why, and what we turned down. Newest spikes fold in their original dated notes.

---

### ADR-1 — Two layers: pure rules + ArcGIS adapter
**Decision:** `toolbox/permit_office/` is ArcPy-free and holds all game logic;
`toolbox/permit_office_arcgis/` holds persistence, geometry, and the Tk UI.
**Why:** the rules are testable in plain Python (fast regression, no ArcGIS
license needed); ArcPy stays a swappable I/O edge.
**Rejected:** logic interleaved with cursors — untestable offline and couples
balance tuning to a live ArcGIS install.

### ADR-2 — The geodatabase *is* the save file
**Decision:** game state lives entirely in feature classes/tables; the dashboard
holds only UI/session bookkeeping that `reload()` re-derives from rows.
**Why:** one source of truth, free crash-resume, and the map and game can't drift
apart. **Rejected:** a separate serialized save alongside the GDB — two states to
keep consistent.

### ADR-3 — Synchronous command flow (for now)
**Decision:** every action runs inline on the Tk thread: command row → reads →
resolve → writes → map refresh → reload. No threads, no async.
**Why:** ArcPy cursor/`mp` thread-safety is fraught; the single-thread model is
simple and correct, and the timer can't interleave with a command.
**Rejected (deferred):** backgrounding I/O with `root.after()` marshalling — real
responsiveness win but real concurrency risk; revisit as a spike only if live
runs show UI-freeze pain.

### ADR-4 — District-readd layer rebuild by default
**Decision:** `rebuild_output_layers()` removes + re-adds the **district family**
(`PermitDistricts` base + prosperity/identity overlays) every rebuild, and keeps
the **feature layers** (points/lines/zones) refresh-only; `force_readd=True` does
a full remove→add of every in-scope layer (New Game / schema / symbology change).
**Why:** `arcpy.RefreshLayer` only redraws the cached renderer — it does **not**
reload GDB attribute writes. The district layers render on attribute values
(`district_type`, `prosperity_band`, `identity_state`) that change every decision
and turn, so refresh-only left them frozen on the new-game snapshot (districts
"not rendering"). Removing + re-adding only the district family restores correct
rendering while still skipping the bulk of the per-turn `addDataFromPath` churn
on the feature layers. **Rejected:** unconditional remove→add of *all* layers
every turn (slow, flicker-prone); pure refresh-only (correctness bug above).
*(Supersedes the 2026-05-27 refresh spike, which mis-measured refresh-only as
reliability-safe; the RefreshLayer-does-not-reload-data behavior was confirmed
later.)*

### ADR-5 — Cursor efficiency: hint + guard, memoize, read-once
**Decision:** single-row cursors carry a `where_clause` **and** keep the in-Python
row check; immutable district geometry is memoized per session; `reload()` makes
a fixed number of cursor opens (batch `proposal_visible_map`, pre-read reuse via
`reload_kwargs`). **Why:** fewer/narrower cursor opens without trusting backend
SQL semantics; correctness is identical whether or not the predicate is honored.
**Rejected:** where-clause with the guard removed (broke when a backend ignored
the predicate); per-item visibility scans (`4 + 3N` opens per reload).

### ADR-6 — No ArcGIS Pro SDK add-in for display
**Decision:** stay on stock ArcPy; don't ship a C# SDK display-cache button.
**Why:** the SDK redraw-cache spike timed *slower* than main and added
build/install/deploy burden outside the dashboard flow.
**Rejected:** SDK display-cache control — retired as a capability proof.

### ADR-7 — No pane automation from Python
**Decision:** startup repairs the GDB and layers and opens the dashboard at a
fixed size; ArcGIS Pro keeps Contents/Geoprocessing pane layout under user
control. **Why:** ArcPy exposes no stable public API to arrange panes; UI/SDK
automation is fragile. **Rejected:** scripted pane layout — solve with setup
instructions if a live demo ever needs it.

### ADR-8 — Unique-value symbology; defer richer renderers
**Decision:** districts render by `district_type`, support layers by
`display_state`, via a `UniqueValueRenderer` (with list/string/CIM field-set
fallbacks for cross-build robustness). **Why:** these channels keep workflow and
identity readable now. **Rejected (deferred):** bivariate activity/exposure
renderer and per-family support layers — overload the same visual channels before
live ArcGIS evidence proves the need.

### ADR-9 — District identity & buyouts: legible first-pass
**Decision:** deterministic refuse → contested → stabilize/convert; conversion
relabels the district and shifts fill; legibility via name/color/news-ticker/
report, not a raw ledger. **Why:** closeable and understandable without exposing
internals. **Rejected (deferred):** multi-bid/round-robin negotiation and ledger-
snapshot RNG keys — larger design, follow-up scope.

### ADR-10 — Small public stat model, hidden internals
**Decision:** the player-facing audit goals are exactly four vitals — **Activity /
Friction / Trust / Exposure** — shown on the City Pulse rail under a folded
**City Health** headline, with **Heat** (stakeholder pressure) and a single
**Pressure** causes-rollup as the at-a-glance risk signals. Everything else —
**services**, dissatisfaction, hazards, housing/affordability, maintenance,
population mix, identity, heat bands, economy detail — is internal/derived and
surfaces only in the **scorecard report and inspected cases**, not the always-on
rail (it still influences the four vitals and the audit score). **Why:** a few
legible goals + rich docket/scorecard detail beat many shallow exposed systems;
the same names are used in the rail, the audit report, and the help overlay.
**Rejected:** keeping Services (or any granular support system) on the always-on
rail; surfacing every internal system as a player-facing stat.

### ADR-11 — Deterministic seeded generation
**Decision:** boards and dockets are generated from an RNG keyed on
`seed:turn:district-mix:stats`; docket sampling is weighted-without-replacement
with reserved scenario-priority slots. **Why:** reproducible demos and locked
regression routes (seed `2026`) while staying responsive to city state.
**Rejected:** unseeded randomness — untestable, unrepeatable demos.

### ADR-12 — File-size budget is a soft target
**Decision:** ~1000 lines is the soft review target; the guardrail test only
trips at a 1500 hard ceiling. **Why:** keep files reviewable without forcing
premature splits or comment-stripping when logic genuinely warrants the length.
**Rejected:** a hard 1050 cap — pushed against documentation and cohesive modules.

### ADR-13 — Seeded proposals, not Feature Set drawing
**Decision:** proposed geometry is generated from filed targets and replaced via
`Retarget Map` from the current district selection; no interactive Feature Set
drawing. **Why:** keeps the map the *input* device and the dashboard the
controller, with deterministic, reproducible exhibits. **Rejected:** freehand
Feature Set drawing — non-deterministic and off the command flow.
