# Live ArcGIS Redraw Experiment Notes

Canonical notes for redraw experiments that changed or nearly changed the map
refresh strategy. Scratch specs/plans stay in ignored `docs/superpowers/`; this
file records only live findings that should survive.

## 2026-06-08 rehydrate/swap benchmark

**Setup:** ArcGIS Pro live run, `Log Refresh Timings` enabled, saved
`permit_office.gdb`, `Redraw Benchmark Runs = 1`.

### Baselines

- Old district-family remove/add was correct but commonly spent about 4-5s in
  rebuild work.
- `predrawn-rehydrate` preserved district correctness and reduced hot redraws,
  but point decisions still paid for `PermitPoints` remove/add.
- Pure `predrawn-swap` remained the fastest path (`~0.4-0.7s` benchmark rebuilds)
  but can hold stale district symbology because it does not re-read district
  attributes from the GDB.
- `volatile-overlay` was rejected as a default because it can leave the board
  incomplete/filtered.

### Variant results

- `predrawn-rehydrate-smart-features` was the strongest correctness-safe
  candidate. It rehydrates districts but strips `PermitPoints` out of the live
  remove/add scope, relying on `RefreshLayer('PermitPoints')` for point redraws.
  Live benchmark: `districts+points` rebuilt in `1.789s`, versus roughly
  `2.85-3.83s` for normal rehydrate in the same session.
- `predrawn-swap-refresh` was very fast (`~1.0-1.3s` rebuilds during benchmark
  and normal play). During play it did not obviously corrupt the board, but after
  closing/completion the map showed red/gray district display-state styling over
  the whole board. Treat this as a correctness bug, not a default candidate.
- `hybrid-rehydrate-districts-swap-points` did not win. Initial point snapshot
  seeding and all-layer cases were slower than smart-features (`~3.3-3.9s` in
  benchmark), so keep it only as a diagnostic experiment.
- `predrawn-rehydrate-template-style` and hidden-first rehydrate remained viable
  probes but did not beat `predrawn-rehydrate-smart-features` for point decisions.
- `style-cache` did not deliver reliable savings because removing/re-adding the
  layer loses the Python-side style marker.

### Decision

Do not promote `predrawn-swap-refresh` yet, despite good timings. Promote only a
path that preserves visual correctness after decisions, week advance, and
dashboard close/completion. Current next promotion candidate:
`predrawn-rehydrate-smart-features`.

Keep the fast swap probes in the GP dropdown for diagnosis, but prune them from
default behavior until the close-state red/gray rendering bug is understood.
