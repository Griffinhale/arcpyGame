# Permit Office Desk UI Cleanup - Design

Date: 2026-06-01
Status: Proposed (awaiting review)

## Problem

The Permit Office dashboard is a single hand-drawn Tkinter `Canvas`
(`PermitDeskView._draw` in `toolbox/permit_office_arcgis/desk_view.py`). Every
label, panel, and button is positioned with absolute pixel math and small fonts
(6-9pt). Text overlaps across regions because:

1. **No layout engine.** Each region advances `y += <fixed height>`. When real
   content (impact buckets, inspection addendum, ruled blocks, city-health rows)
   is taller than its guessed budget, the next region draws on top of it. The
   clearest example is `inspection_h = max(46, chip_strip_y0 - y - 22)`: it
   clamps to 46 even after `y` has already passed the chip strip, so the
   addendum collides with the button row.
2. **Designed for ~1320px landscape.** Banner metric spacing, the 230px City
   Health rail, and the card body assume a wide window. Narrower windows clip
   text and let panels bleed together.
3. **Tiny type plus heavy truncation.** Pervasive `_clip`/`shorten` produces
   "..." everywhere, which reads as cramped and hard to engage with.

The Filed Report is a separate blocking modal (`open_filed_report`,
`grab_set` + `wait_window`), so playing requires two windows.

## Goals

- No region can overlap another, at any window size.
- Readable type and comfortable spacing; less truncation.
- Single screen: fold the Filed Report into the dashboard as an always-visible,
  non-blocking inline panel; delete the modal.
- Fit a portrait ~960 x 1040 window (half of a 1920x1080 monitor, ArcGIS Pro on
  the other half) without collisions, and not break when larger.
- Keep the paper-desk theme (stamped index card, ruled paper, status-keyed
  color bands) - it is what makes the game engaging.

## Non-Goals

- No rebuild on ttk/grid widgets (would discard the paper-desk theme).
- No change to gameplay rules or the view *model* contract
  (`build_desk_model` and helpers) beyond additive, backward-compatible fields.
- No new helper module (keeps the `arcpy_permit_office.pyt` reload loop and the
  ArcGIS module-cache workflow untouched).

## Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Rendering approach | Keep Canvas; add a measured vertical-flow layout | Preserves theme; makes overlap structurally impossible |
| Window orientation | Portrait ~960 x 1040 primary; degrade gracefully wider/narrower | Matches side-by-side-with-ArcGIS workflow |
| Filed Report | Inline, non-blocking bottom panel; modal removed | Single-screen play |
| Card density | Readability first (fewer fields, 10-11pt body) | Engagement over density |
| Code location | Stay within `desk_view.py` / `dashboard.py` | Avoid reload-loop + module-cache gotcha |
| Source encoding | ASCII only | Project constraint |

## Architecture

### 1. Measured flow layout (the core fix)

Add a tiny private layout helper inside `desk_view.py` - no new module. The
contract: **a block draws itself within a given x-range starting at a given top
`y`, and returns the y of its actual bottom edge.** A `Stacker` tracks the
current y and inserts padding between blocks:

```
class _Stacker:
    def __init__(self, canvas, x0, x1, top, pad):
        ...
    def add(self, draw_fn) -> int:
        # draw_fn(canvas, x0, x1, y) -> bottom_y
        bottom = draw_fn(self.canvas, self.x0, self.x1, self.y)
        self.y = bottom + self.pad
        return bottom
    def remaining(self, hard_bottom) -> int:
        return hard_bottom - self.y
```

- Fixed-height blocks (banner, action bar, receipt header) return
  `top + known_height`.
- Variable blocks (case fields, inspection addendum, status text, city-health
  rows) measure real height with `canvas.bbox(item_id)` - the same technique the
  current receipt code already uses (`c.bbox(rid)`) - and clip to a max when a
  hard bottom is supplied, emitting a graceful "..." / "+N more" footer instead
  of spilling.

This converts "guess a height and hope" into "draw, measure, then place the next
thing," so overlap cannot occur.

### 2. Region budgeting (portrait re-flow)

`_draw(width, height)` computes a fixed top and a fixed bottom stack, then gives
the leftover vertical space to the flexible middle. Top to bottom:

```
+-----------------------------------------------+  width ~960
| PERMIT OFFICE   WK AP $ HEAT AUDIT   DEADLINE  |  banner   (fixed ~64)
+------------------------------+----------------+
|  ACTIVE CASE CARD            |  CITY HEALTH    |  body row (flexible:
|   status band + title        |   ledger rows,  |   height = total
|   applicant / category       |   bigger,       |   - banner
|   selected districts         |   clipped with  |   - rolodex
|   impact buckets (2-col)     |   "+N more"     |   - action bar
|   inspection addendum        |                 |   - receipt
|   RISK                       |                 |   - paddings)
+------------------------------+----------------+
|  ROLODEX  queued cases (horizontal strip)      |  fixed ~120
+-----------------------------------------------+
|  [Show Exhibit][Update][Inspect][Issue]...     |  action bar (fixed ~60)
+-----------------------------------------------+
|  FILED REPORT  result + affected + metrics     |  receipt   (fixed ~150)
+-----------------------------------------------+
```

- The body row is split into a case-card column (~62% width) and a city-health
  column (~38%, min ~250px). Each column runs its own `_Stacker` bounded by the
  body row's height, so neither column can overflow into the rolodex/action bar.
- The case card uses readability-first content: item id, top 3 fields, selected
  districts, impact buckets (2-col grid), inspection addendum (gets the column's
  remaining measured space), and the risk tag. Body text moves to ~10pt, section
  labels to ~8pt.
- City-health rows render at larger type; rows that do not fit the column are
  replaced by a "+N more" footer rather than being drawn past the boundary.
- Rolodex moves below the body to use the extra portrait height; it keeps the
  edge-tab stack look but with a fixed, clipped height.
- Action bar spans full width with larger chips (taller, wider hit targets) for
  easier engagement.

### 3. Inline Filed Report panel

Replace the modal:

- `DeskViewModel` gains an additive, optional `receipt` field (default `None`)
  carrying title, report text, affected districts, and a metric snapshot
  (week/AP/$/net/heat) - the same data the modal drew.
- The controller stores `self.last_receipt` and passes it into
  `build_desk_model` on every `reload()`, so the panel persists across redraws.
- Decision handlers (`inspect`, `apply_decision`, `deny`,
  `_finish_decision`) set `self.last_receipt` instead of calling
  `open_effect_report`. The bottom receipt panel draws the latest result with
  wrapped, clipped text and the metric strip, accent-colored by result type
  (reusing `_receipt_accent`).
- `open_filed_report` / `open_effect_report` and the modal-specific
  `_draw_receipt_canvas` plumbing are removed (the receipt drawing logic is
  adapted into the inline panel).

#### Consequence: `perf_block("receipt")`

A recorded memory notes that the `receipt` perf block intentionally measures
human dwell time on the modal (`grab_set` + `wait_window`). Removing the modal
makes that block a fast inline draw, so it no longer measures click latency. This
is accepted as part of the single-screen goal. The decision handlers will drop
the now-meaningless `perf_block("receipt")` wrapper, and the memory note will be
updated/retired.

## Data Flow

```
controller.reload()
  read_state / read_districts / read_docket / read_active_features
  build_desk_model(..., receipt=self.last_receipt)   # additive arg
    -> DeskViewModel(docket_rows, case, ledger_rows, status, ..., receipt)
  view.render(model)
    _draw(width, height)
      banner (fixed)            -> Stacker/known height
      body row (flexible)       -> 2 columns, each a bounded _Stacker
      rolodex (fixed, clipped)
      action bar (fixed)
      receipt panel (fixed)     <- model.receipt
```

Decision action (e.g. approve):
```
apply_decision()
  ... resolve + persist (unchanged) ...
  self.last_receipt = ReceiptModel(title, filed_report, affected, snapshot)
  self.reload()        # inline panel updates in place; no second window
```

## Error Handling

- Missing/empty content (no active case, no queued cases, no receipt yet) draws
  the existing placeholder strings inside their bounded blocks; placeholders are
  clipped like any other content.
- If `canvas.bbox` returns `None` (item not yet laid out), blocks fall back to a
  conservative fixed height (mirrors the receipt code's existing
  `(c.bbox(rid) or (...))[3]` guard), so a measurement miss never crashes a
  redraw.
- A column whose content exceeds its budget clips and shows a "+N more" / "..."
  affordance; it never draws past its hard bottom.

## Testing

- All existing tests target the view *model* (`build_desk_model`, summary
  helpers, `HEADLINE_METRICS`); none touch drawing. The model contract is
  preserved, and the new `receipt` field is additive with a default, so the
  suite stays green.
- New pure tests:
  - `build_desk_model(..., receipt=...)` round-trips the receipt into the model;
    default is `None`.
  - A headless `_Stacker` unit test (no Tk window): a fake canvas records
    `create_*` calls and bbox stubs; assert that for representative content each
    block's top is at or below the previous block's returned bottom + padding
    (i.e. no overlap) and that nothing is placed past the supplied hard bottom.
- Manual verification in ArcGIS Pro at ~960x1040 and maximized: confirm no
  overlap, readable type, inline receipt updates after inspect/approve/deny with
  no second window.

## Risks

- **Canvas still requires manual placement.** Mitigated by centralizing
  placement in `_Stacker` so spacing is computed from measured content once,
  not re-guessed per region.
- **`desk_view.py` growth.** The file is already large; the receipt drawing
  moves in while the modal scaffolding moves out, so net growth is modest. If it
  becomes unwieldy later, splitting is a separate change (would require adding
  the new module to the `.pyt` reload loop).
- **Behavioral change to perf logging.** Documented above; intentional.
