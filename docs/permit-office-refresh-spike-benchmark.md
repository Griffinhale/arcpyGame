# Permit Office Refresh Spike Benchmark

Date: 2026-05-27

Purpose: record the redraw/cache spike interpretation and keep future refresh work tied to game reliability rather than speculative performance work.

## Comparison Branches Evaluated

- `codex/spike-pause-drawing-refresh`
  - ArcPy-only candidate.
  - Uses paused map drawing, batched `RefreshLayer`, existing-layer refresh-only rebuilds, and derived-output metadata.
- `codex/spike-sdk-redraw-cache`
  - ArcGIS Pro SDK proof-of-capability.
  - Adds one manual button that clears display cache for Permit Office layers and forces an active map redraw.

## Dropped Branches

- `codex/spike-refresh-only`
  - Superseded by `codex/spike-pause-drawing-refresh`, which carries forward the useful existing-layer refresh-only behavior.
- `codex/spike-render-baseline`
  - Superseded as a separate comparator. If extra setup or callback timing is needed later, fold that instrumentation into the chosen branch rather than benchmarking it separately.
- `codex/spike-stable-filtered-layers`
  - Dropped from the active benchmark because it adds filtered support layers and definition-query state, making redraw results harder to compare.
- `codex/spike-visibility-pool`
  - Dropped from the active benchmark because it adds reusable layer pools and visibility state, making redraw results harder to compare.

## Manual Benchmark Matrix

If reproducing the comparison, run both evaluated branches against the same ArcGIS Pro project shape and record:

- Approve point, approve line, approve zone, toggle exhibit, update from map, and advance turn.
- GP messages with perf logging enabled where available.
- Stale display incidents, flicker or blank time, callback latency, and lock errors.
- Whether existing-layer ArcPy runs log refresh-only instead of remove/add.
- Whether the SDK button clears stale visuals faster or more reliably after normal Permit Office edits.

## Recorded Result

Timing interpretation from the May 2026 spike:

| Strategy | Timing Result | Game-Wide Ramification | Decision |
| --- | --- | --- | --- |
| Current `main` rebuild/refresh path | Close to the ArcPy refresh strategy | The active dashboard turn path is not obviously losing most of its time to removable layer churn. | Keep as the baseline until live smoke testing proves a reliability problem. |
| ArcPy refresh-only / pause-drawing strategy | Close to `main` | Useful as a reliability candidate if it reduces stale display, blanking, or lock behavior, but not justified as a broad speed rewrite from timing alone. | Keep as a targeted fallback branch. |
| ArcGIS Pro SDK display-cache button | Slower in timing results | Adds C# build/install/deployment burden and stays outside the dashboard command flow. It does not improve the normal per-turn user path enough to justify carrying it. | Retire as a capability proof, not an active product dependency. |

The exact timing values were not committed here, so this document records the decision-level interpretation rather than pretending the repo has a numeric benchmark log.

## Decision Rule

Prefer the simplest branch that reliably removes stale display incidents without visible blanking or new lock errors. Current timing does not justify the SDK path. Any future refresh work should be validated against approve point, approve line, approve zone, toggle exhibit, update from map, and advance turn, because each path mutates a different layer set.

## Implementation Implications

- Keep pure rules unchanged. Refresh strategy belongs in `toolbox/permit_office_arcgis/geometry.py` and `dashboard.py`, not in `toolbox/permit_office/`.
- Keep the dashboard command flow synchronous for now: command row, reads, pure-rule resolution, writes, map update, receipt, dashboard reload.
- Treat `PERMIT_OFFICE_PERF` and the `Log Refresh Timings` tool parameter as the diagnostic path for future work.
- Optimize only after a live ArcGIS Pro run records stale visuals, flicker/blank time, lock errors, or callback latency that affects the demo.
