# Permit Office Refresh Spike Benchmark

Date: 2026-05-26

Purpose: keep the active ArcGIS Pro redraw/cache comparison small enough to interpret.

## Active Comparison Branches

- `codex/spike-pause-drawing-refresh`
  - ArcPy-only candidate.
  - Uses paused map drawing, batched `RefreshLayer`, existing-layer refresh-only rebuilds, and derived-output metadata.
- `codex/spike-sdk-redraw-cache`
  - ArcGIS Pro SDK proof-of-capability.
  - Adds one manual button that clears display cache for Permit Office layers and forces an active map redraw.

## Superseded Branches

- `codex/spike-refresh-only`
  - Superseded by `codex/spike-pause-drawing-refresh`, which carries forward the useful existing-layer refresh-only behavior.
- `codex/spike-render-baseline`
  - Superseded as a separate comparator. If extra setup or callback timing is needed later, fold that instrumentation into the chosen branch rather than benchmarking it separately.
- `codex/spike-stable-filtered-layers`
  - Dropped from the active benchmark because it adds filtered support layers and definition-query state, making redraw results harder to compare.
- `codex/spike-visibility-pool`
  - Dropped from the active benchmark because it adds reusable layer pools and visibility state, making redraw results harder to compare.

## Manual Benchmark Matrix

Run both active branches against the same ArcGIS Pro project shape and record:

- Approve point, approve line, approve zone, toggle exhibit, update from map, and advance turn.
- GP messages with perf logging enabled where available.
- Stale display incidents, flicker or blank time, callback latency, and lock errors.
- Whether existing-layer ArcPy runs log refresh-only instead of remove/add.
- Whether the SDK button clears stale visuals faster or more reliably after normal Permit Office edits.

## Decision Rule

Prefer the simplest branch that reliably removes stale display incidents without visible blanking or new lock errors. Treat the SDK branch as a manual capability test only unless its redraw/cache behavior clearly beats the ArcPy branch.
