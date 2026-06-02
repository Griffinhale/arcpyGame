"""Custom Tkinter desk surface for the Permit Office dashboard."""

from __future__ import annotations

from dataclasses import replace
from textwrap import shorten, wrap
from typing import Callable

from .rules_loader import rules
from .desk_model import (
    HEADLINE_METRICS,
    DeskCallbacks,
    DeskViewModel,
    LedgerRow,
    ReceiptModel,
    build_desk_model,
    _hazard_summary,
    _maintenance_summary,
    _service_gap_summary,
)


# Floors used while the window is still sizing; the desk re-flows for a portrait
# pane that fills half of a 1920x1080 monitor beside ArcGIS Pro.
MIN_DESK_W = 900
MIN_DESK_H = 860


def receipt_metrics(state):
    """Return the compact (label, value) metric snapshot for a filed receipt."""

    return (
        ("WEEK", f"{state.turn}/{state.max_turns}"),
        ("AP", f"{state.ap}/{state.max_ap}"),
        ("$", str(state.money)),
        ("NET", f"{state.last_net:+d}"),
        ("HEAT", str(rules.heat_summary(state))),
    )


class Palette:
    """Desk colors gathered in one place for Canvas rendering."""

    DESK = "#4f6b65"
    DESK_DARK = "#2f4844"
    PAPER = "#f4ecd8"
    PAPER_ALT = "#e7efd9"
    PAPER_SHADOW = "#2a3837"
    FOLDER = "#c3b172"
    NOTE = "#f6e28d"
    NOTE_BLUE = "#d9e7ef"
    INK = "#263238"
    MUTED = "#5f685f"
    LINE = "#b7ad92"
    RED = "#a9433d"
    GREEN = "#3f7059"
    BLUE = "#335f82"
    GOLD = "#a77c37"
    TEAL = "#4f7875"
    CARD_SHADOW = "#3a5450"
    LEDGER = "#dce7d3"
    LEDGER_LINE = "#a7b699"
    WHITE = "#fbf7eb"


class _Stacker:
    """Place canvas blocks top-to-bottom, measuring real heights to avoid overlap.

    Each block is a callable ``draw_fn(canvas, x0, x1, y, max_y) -> bottom_y``.
    The stacker advances past the measured bottom (clamped to ``bottom``) and
    inserts ``pad`` before the next block, so no block can ever be drawn over its
    neighbour or past the region's hard bottom edge.
    """

    def __init__(self, canvas, x0, x1, top, bottom, pad=8):
        """Bind the stacker to a canvas column with a hard top and bottom."""

        self.canvas = canvas
        self.x0 = x0
        self.x1 = x1
        self.y = top
        self.bottom = bottom
        self.pad = pad

    def room(self):
        """Return the vertical space left before the hard bottom edge."""

        return self.bottom - self.y

    def add(self, draw_fn, min_h=0):
        """Draw one block from the current y and advance; skip if no room.

        Returns the block's bottom y, or ``None`` when less than ``min_h`` space
        remains so callers can render an overflow affordance instead.
        """

        if self.room() < max(1, min_h):
            return None
        bottom = draw_fn(self.canvas, self.x0, self.x1, self.y, self.bottom)
        bottom = min(int(bottom), self.bottom)
        self.y = bottom + self.pad
        return bottom


def _text_bottom(c, x, y, text, font, fill, width=None, anchor="nw", justify="left"):
    """Draw a text item and return its real bottom y (measured, never guessed)."""

    kwargs = {"text": text, "anchor": anchor, "fill": fill, "font": font, "justify": justify}
    if width is not None:
        kwargs["width"] = width
    item = c.create_text(x, y, **kwargs)
    box = c.bbox(item)
    return box[3] if box else y + font[1] + 6


class PermitDeskView:
    """Canvas-based dashboard view for the overworked permit clerk desk."""

    def __init__(self, root, callbacks: DeskCallbacks, on_select_item: Callable[[str], None]):
        """Create the canvas and bind mouse events to view callbacks."""

        import tkinter as tk

        self.root = root
        self.callbacks = callbacks
        self.on_select_item = on_select_item
        self.model = DeskViewModel()
        self._click_targets: list[tuple[str, str, tuple[int, int, int, int], Callable[[], None]]] = []
        self._hover_key = ""
        self._last_size = (0, 0)
        self._font_cache: dict = {}

        self.canvas = tk.Canvas(root, bg=Palette.DESK, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)

    def render(self, model: DeskViewModel):
        """Store and draw the latest view model."""

        self.model = model
        width = max(self.canvas.winfo_width(), MIN_DESK_W)
        height = max(self.canvas.winfo_height(), MIN_DESK_H)
        self._draw(width, height)

    def selected_item_id(self) -> str:
        """Return the currently rendered selected item id."""

        return self.model.selected_item_id

    def update_deadline(self, text: str, meter: int, running: bool, status_text: str | None = None):
        """Update the live filing-deadline presentation without reloading ArcGIS rows."""

        if (
            self.model.deadline_text == text
            and self.model.deadline_meter == meter
            and self.model.deadline_running == running
            and (status_text is None or self.model.status_text == status_text)
        ):
            return
        next_status = self.model.status_text if status_text is None else status_text
        self.model = replace(
            self.model,
            status_text=next_status,
            deadline_text=text,
            deadline_meter=meter,
            deadline_running=running,
        )
        width = max(self.canvas.winfo_width(), MIN_DESK_W)
        height = max(self.canvas.winfo_height(), MIN_DESK_H)
        self._draw(width, height)

    def _on_configure(self, event):
        """Redraw the canvas when the window size changes."""

        size = (event.width, event.height)
        if size != self._last_size:
            self._last_size = size
            self._draw(max(event.width, MIN_DESK_W), max(event.height, MIN_DESK_H))

    def _on_click(self, event):
        """Dispatch a click to the topmost registered hit target."""

        for _kind, _ident, bbox, callback in reversed(self._click_targets):
            if _inside(event.x, event.y, bbox):
                callback()
                return "break"
        return None

    def _on_motion(self, event):
        """Update hover state and cursor for registered hit targets."""

        hover = ""
        for kind, ident, bbox, _callback in reversed(self._click_targets):
            if _inside(event.x, event.y, bbox):
                hover = f"{kind}:{ident}"
                break
        if hover != self._hover_key:
            self._hover_key = hover
            self.canvas.configure(cursor="hand2" if hover else "")
            width = max(self.canvas.winfo_width(), MIN_DESK_W)
            height = max(self.canvas.winfo_height(), MIN_DESK_H)
            self._draw(width, height)

    def _on_leave(self, _event):
        """Clear hover state when the pointer leaves the canvas."""

        if self._hover_key:
            self._hover_key = ""
            self.canvas.configure(cursor="")
            width = max(self.canvas.winfo_width(), MIN_DESK_W)
            height = max(self.canvas.winfo_height(), MIN_DESK_H)
            self._draw(width, height)

    def _draw(self, width, height):
        """Lay out fixed banner/status/rolodex/action/receipt bands around a flexible body.

        Bands are budgeted from the top and the bottom so the flexible body row
        in the middle (case card + city-health rail) gets exactly the leftover
        space. Every band clips its own content, so regions never overlap.
        """

        c = self.canvas
        c.delete("all")
        self._click_targets = []
        self._draw_background(c, width, height)

        margin = 20
        gap = 14

        banner_h = 64
        status_h = 28
        short = height < 940
        action_h = 56 if short else 62
        receipt_h = (168 if short else 190) if self.model.receipt else 98
        rolodex_h = 92 if short else 132

        self._draw_top_banner(c, width, banner_h)
        status_y0 = banner_h + gap
        self._draw_status_strip(c, (margin, status_y0, width - margin, status_y0 + status_h))

        # Everything is top-anchored: the case card + action bar + rolodex + receipt
        # cluster under the banner, and any extra height on a tall pane becomes a
        # single clean strip of desk surface at the very bottom (not a gap in the
        # middle). The body is capped so the card never stretches mostly-empty, and
        # the action bar sits directly under it so the decision buttons stay near
        # the case you are judging.
        body_y0 = status_y0 + status_h + gap
        fixed_below = gap + action_h + gap + rolodex_h + gap + receipt_h
        body_h = (height - margin) - body_y0 - fixed_below
        body_h = max(240, min(600, body_h))
        body_y1 = body_y0 + body_h
        action_y0 = body_y1 + gap
        action_y1 = action_y0 + action_h
        rolodex_y0 = action_y1 + gap
        rolodex_y1 = rolodex_y0 + rolodex_h
        receipt_y0 = rolodex_y1 + gap
        receipt_y1 = receipt_y0 + receipt_h

        health_w = max(250, int((width - 2 * margin) * 0.36))
        health_x1 = width - margin
        health_x0 = health_x1 - health_w
        card_x0 = margin
        card_x1 = health_x0 - gap

        self._draw_active_card(c, (card_x0, body_y0, card_x1, body_y1))
        self._draw_ledger_rail(c, (health_x0, body_y0, health_x1, body_y1))
        self._draw_action_bar(c, (margin, action_y0, width - margin, action_y1))
        self._draw_rolodex_stack(c, (margin, rolodex_y0, width - margin, rolodex_y1))
        self._draw_receipt_panel(c, (margin, receipt_y0, width - margin, receipt_y1))

    def _draw_background(self, c, width, height):
        """Paint the desk surface (banner draws its own dark band on top)."""

        c.create_rectangle(0, 0, width, height, fill=Palette.DESK, outline="")

    def _draw_top_banner(self, c, width, h):
        """Draw the headline-metrics banner across the desk lip."""

        c.create_rectangle(0, 0, width, h, fill=Palette.DESK_DARK, outline="")
        c.create_rectangle(0, h - 3, width, h, fill=Palette.CARD_SHADOW, outline="")
        c.create_text(24, h // 2, text="PERMIT OFFICE", anchor="w", fill=Palette.PAPER, font=self._font(15, "bold"))
        metrics = {row.label: row for row in self.model.ledger_rows}
        headlines = HEADLINE_METRICS
        x_start = 240
        right_pad = 196 if self.model.deadline_text else 28
        spacing = max(70, (width - x_start - right_pad) // len(headlines))
        x = x_start
        for key, display in headlines:
            row = metrics.get(key)
            if row is None:
                continue
            tone = _tone_color(row.tone)
            c.create_text(x, h // 2 - 11, text=display, anchor="w", fill=Palette.LEDGER_LINE, font=self._font(8, "bold"))
            c.create_text(x, h // 2 + 9, text=_clip(row.value, 10), anchor="w", fill=Palette.PAPER if tone == Palette.INK else tone, font=self._font(12, "bold"))
            x += spacing
        if self.model.deadline_text:
            self._draw_deadline_clock(c, width, h)

    def _draw_deadline_clock(self, c, width, h):
        """Draw the live filing deadline in the top banner."""

        x1 = width - 20
        x0 = x1 - 190
        y0 = 10
        y1 = h - 9
        meter = max(0, min(100, int(self.model.deadline_meter or 0)))
        fill = Palette.GOLD if meter >= 75 else Palette.PAPER if self.model.deadline_running else Palette.LEDGER_LINE
        c.create_rectangle(x0, y0, x1, y1, outline=fill, width=1)
        c.create_text(x0 + 10, y0 + 5, text="FILING DEADLINE", anchor="nw", fill=Palette.LEDGER_LINE, font=self._font(7, "bold"))
        c.create_text(x0 + 10, y0 + 20, text=_clip(self.model.deadline_text, 22), anchor="nw", fill=Palette.PAPER, font=self._font(9, "bold"))
        # Thin progress bar pinned to the inner bottom edge, clear of the text.
        c.create_rectangle(x0 + 1, y1 - 4, x0 + 1 + int((x1 - x0 - 2) * meter / 100), y1 - 1, fill=fill, outline="")

    def _draw_status_strip(self, c, box):
        """Draw the one-line ambient status (office-day note, selection, errors)."""

        x0, y0, x1, y1 = box
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.DESK_DARK, outline="")
        mid = (y0 + y1) // 2
        c.create_text(x0 + 12, mid, text="STATUS", anchor="w", fill=Palette.LEDGER_LINE, font=self._font(8, "bold"))
        text = _clip(self.model.status_text or "Ready.", max(40, (x1 - x0 - 90) // 7))
        c.create_text(x0 + 78, mid, text=text, anchor="w", fill=Palette.PAPER, font=self._font(10))

    def _draw_rolodex_stack(self, c, box):
        """Draw the horizontal edge-tab stack of queued (non-active) docket items."""

        x0, y0, x1, y1 = box
        active_id = self.model.selected_item_id
        queue = [row for row in self.model.docket_rows if row.item_id != active_id]
        total_open = len(self.model.docket_rows)

        c.create_text(x0 + 4, y0 + 4, text="ROLODEX", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        c.create_text(x0 + 76, y0 + 4, text=f"{total_open} OPEN", anchor="nw", fill=Palette.MUTED, font=self._font(7))

        if not queue:
            c.create_text(x0 + 4, y0 + 22, text="No queued cases. End the filing week to draw fresh dockets.", anchor="nw", fill=Palette.MUTED, font=self._font(9))
            return

        tab_h = 28
        v_offset = 24
        indent = 10
        max_visible = max(1, (y1 - y0 - 20) // v_offset)
        max_visible = min(max_visible, 5)
        visible = queue[:max_visible]
        overflow = len(queue) - len(visible)

        tab_count = len(visible)
        stack_h = tab_h + (tab_count - 1) * v_offset
        stack_y_start = y0 + 20  # top-anchor so tabs sit under the rolodex header

        # Draw deepest (oldest) first so newer tabs overlap them.
        for i, row in enumerate(reversed(visible)):
            depth = tab_count - 1 - i  # 0 = closest to active card, larger = further back
            tx0 = x0 + indent * depth
            tx1 = x1 - indent * depth
            ty0 = stack_y_start + i * v_offset
            ty1 = ty0 + tab_h
            hover = self._hover_key == f"docket:{row.item_id}"
            fill = "#f8f1d8" if hover else self._layer_shade(depth)
            c.create_rectangle(tx0, ty0, tx1, ty1, fill=fill, outline=Palette.LINE, width=1)
            c.create_rectangle(tx0, ty0, tx0 + 14, ty1, fill=_status_color(row.status), outline="")
            c.create_text(tx0 + 22, ty0 + 7, text=f"[{row.status.upper()}]", anchor="nw", fill=Palette.MUTED, font=self._font(7, "bold"))
            title_w = max(60, tx1 - tx0 - 220)
            c.create_text(tx0 + 92, ty0 + 7, text=_clip(row.title, max(14, title_w // 7)), anchor="nw", fill=Palette.INK, font=self._font(9, "bold"))
            c.create_text(tx1 - 10, ty0 + 7, text=row.item_id, anchor="ne", fill=Palette.MUTED, font=self._font(8))
            self._add_target("docket", row.item_id, (tx0, ty0, tx1, ty1), lambda item_id=row.item_id: self.on_select_item(item_id))

        if overflow > 0:
            more_y1 = stack_y_start - 4
            more_y0 = more_y1 - 18
            if more_y0 >= y0 + 18:
                mx0 = x0 + indent * tab_count
                mx1 = x1 - indent * tab_count
                c.create_rectangle(mx0, more_y0, mx1, more_y1, fill=Palette.LEDGER, outline=Palette.LINE)
                c.create_text((mx0 + mx1) // 2, (more_y0 + more_y1) // 2, text=f"+ {overflow} earlier case(s)", anchor="center", fill=Palette.MUTED, font=self._font(7, "bold"))

    def _layer_shade(self, depth):
        """Return a paper tone that darkens with depth into the stack."""

        shades = (Palette.PAPER, Palette.PAPER_ALT, "#dfd7be", "#cdc6ad", "#b9b59c")
        return shades[min(depth, len(shades) - 1)]

    def _draw_active_card(self, c, box):
        """Draw the foreground index card with packet content using a measured stack."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 6, y0 + 8, x1 + 6, y1 + 8)

        case = self.model.case
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER, outline=Palette.LINE, width=2)

        # Title band uses the case status as its keyed color so the card reads
        # like a stamped index card the moment it's pulled forward.
        title_h = 52
        band_color = _status_color(case.status) if case.status else Palette.BLUE
        c.create_rectangle(x0, y0, x1, y0 + title_h, fill=band_color, outline="")
        pill_x0 = x0 + 16
        pill_w = 92
        pill_h = 22
        pill_y0 = y0 + (title_h - pill_h) // 2
        c.create_rectangle(pill_x0, pill_y0, pill_x0 + pill_w, pill_y0 + pill_h, fill=Palette.INK, outline="")
        c.create_text(pill_x0 + pill_w // 2, pill_y0 + pill_h // 2, text=_clip(case.status.upper() or "-", 12), anchor="center", fill=Palette.PAPER, font=self._font(9, "bold"))
        stamp_w = 96
        stamp_h = 28
        stamp_x1 = x1 - 16
        stamp_x0 = stamp_x1 - stamp_w
        stamp_y0 = y0 + (title_h - stamp_h) // 2
        c.create_rectangle(stamp_x0, stamp_y0, stamp_x1, stamp_y0 + stamp_h, outline=Palette.PAPER, width=2)
        c.create_text((stamp_x0 + stamp_x1) // 2, stamp_y0 + stamp_h // 2, text="RECEIVED", anchor="center", fill=Palette.PAPER, font=self._font(9, "bold"))
        # Title stays a single clipped line so it never wraps out of the band or
        # runs under the RECEIVED stamp.
        title_left = pill_x0 + pill_w + 14
        title_room = max(40, stamp_x0 - 12 - title_left)
        c.create_text(title_left, y0 + title_h // 2, text=self._fit_px(case.title, 15, "bold", title_room), anchor="w", fill=Palette.PAPER, font=self._font(15, "bold"))

        body_x0 = x0 + 22
        body_x1 = x1 - 22
        stack = _Stacker(c, body_x0, body_x1, y0 + title_h + 14, y1 - 16, pad=10)

        risk_known = (case.risk_band or "unknown").lower() not in ("", "unknown")
        risk_text = "RISK: " + case.risk_band.upper() if risk_known else "RISK: PENDING"
        has_preview = bool(case.preview) and not case.preview.startswith("Select a docket item")

        def _subtitle(cc, sx0, sx1, sy, smax):
            """One-line 'what they want' hook drawn under the case title."""

            cc.create_text(sx0, sy, text=self._fit_px(case.preview, 9, "italic", sx1 - sx0), anchor="nw", fill=Palette.BLUE, font=self._font(9, "italic"))
            return sy + 16

        def _id_line(cc, sx0, sx1, sy, smax):
            """Case id on the left, risk tag on the right (muted until inspected)."""

            cc.create_text(sx0, sy, text=case.item_id or "No case id", anchor="nw", fill=Palette.MUTED, font=self._font(10))
            cc.create_text(sx1, sy, text=risk_text, anchor="ne", fill=_risk_color(case.risk_band), font=self._font(10, "bold"))
            return sy + 18

        def _fields(cc, sx0, sx1, sy, smax):
            """Top three packet fields at readable size, each measured."""

            yy = sy
            for fld in case.fields[:3]:
                if yy + 16 > smax:
                    break
                cc.create_text(sx0, yy + 1, text=fld.label.upper(), anchor="nw", fill=Palette.BLUE, font=self._font(8, "bold"))
                bottom = _text_bottom(cc, sx0 + 116, yy, _clip(fld.value, 80), self._font(10), Palette.INK, width=sx1 - sx0 - 116)
                yy = max(yy + 18, bottom + 4)
            return yy

        def _districts(cc, sx0, sx1, sy, smax):
            """Selected-districts ruled block, clamped to the stack bottom."""

            bh = min(54, smax - sy)
            if bh < 24:
                return sy
            _draw_ruled_block(cc, sx0, sy, sx1, sy + bh, "SELECTED DISTRICTS", case.districts, Palette.BLUE, self._font, max_y=smax)
            return sy + bh

        def _buckets(cc, sx0, sx1, sy, smax):
            """Two-column impact buckets; only rows that fit are drawn."""

            used = _draw_impact_buckets(cc, sx0, sy, sx1 - sx0, case.impact_buckets, self._font, max_y=smax)
            return sy + used

        if has_preview:
            stack.add(_subtitle)
        stack.add(_id_line)
        stack.add(_fields)
        stack.add(_districts, min_h=30)
        stack.add(_buckets, min_h=60)

        # Fill the remaining card space: the inspection addendum once a case has
        # been inspected, otherwise the request narrative (so the space carries
        # story instead of an empty form). A one-line action legend pins the foot.
        legend_h = 24 if case.action_note else 0
        fill_bottom = stack.bottom - legend_h
        inspected = bool(case.inspection) and not case.inspection.lower().startswith("no inspection")
        room = fill_bottom - stack.y
        if room > 46:
            if inspected:
                _draw_ruled_block(c, body_x0, stack.y, body_x1, fill_bottom, "INSPECTION ADDENDUM", case.inspection, Palette.RED, self._font, max_y=fill_bottom)
            else:
                _draw_ruled_block(c, body_x0, stack.y, body_x1, fill_bottom, "REQUEST", case.preview, Palette.BLUE, self._font, max_y=fill_bottom)
        elif not inspected and room > 16:
            c.create_text(body_x0, stack.y, text=self._fit_px("Not yet inspected - use Inspect File to gather evidence.", 9, "normal", body_x1 - body_x0), anchor="nw", fill=Palette.MUTED, font=self._font(9))
        if case.action_note:
            c.create_text(body_x0, stack.bottom - 2, text=self._fit_px(case.action_note, 8, "bold", body_x1 - body_x0), anchor="sw", fill=Palette.MUTED, font=self._font(8, "bold"))

    def _draw_action_bar(self, c, box):
        """Lay out grouped response chips: map tools | inspect | decisions | turn.

        The three decision chips (Issue / Conditions / Deny) render filled as the
        primary path; utilities stay outlined. Wider gaps separate the groups so
        the eye lands on the decision you are there to make.
        """

        x0, y0, x1, y1 = box
        exhibit_label = "Hide Exhibit" if self.model.exhibit_visible else "Show Exhibit"
        groups = (
            ((exhibit_label, Palette.BLUE, self.callbacks.toggle_exhibit, False),
             ("Update Map", Palette.TEAL, self.callbacks.update_from_map, False)),
            (("Inspect File", Palette.GOLD, self.callbacks.inspect, False),),
            (("Issue Permit", Palette.GREEN, self.callbacks.approve, True),
             ("Mitigate", "#527d65", self.callbacks.approve_mitigated, True),
             ("Deny", Palette.RED, self.callbacks.deny, True)),
            (("End Week", Palette.INK, self.callbacks.advance_turn, False),),
        )
        total = sum(len(g) for g in groups)
        intra, inter = 8, 22
        intra_count = sum(len(g) - 1 for g in groups)
        inter_count = len(groups) - 1
        chip_w = max(76, (x1 - x0 - intra * intra_count - inter * inter_count) // total)
        chip_h = min(50, y1 - y0)
        chip_y0 = y0 + (y1 - y0 - chip_h) // 2
        x = x0
        for gi, group in enumerate(groups):
            for ci, (label, color, callback, primary) in enumerate(group):
                hover = self._hover_key == f"action:{label}"
                self._draw_card_chip(c, x, chip_y0, x + chip_w, chip_y0 + chip_h, label, color, hover, callback, primary=primary)
                x += chip_w + (intra if ci < len(group) - 1 else 0)
            if gi < len(groups) - 1:
                x += inter

    def _draw_card_chip(self, c, x0, y0, x1, y1, label, color, hover, callback, primary=False):
        """Draw one action chip and register its hit target.

        ``primary`` chips are filled with their accent (white label) to mark the
        main decision path; the rest are outlined.
        """

        if primary:
            fill = color
            outline = Palette.PAPER if hover else color
            text_color = Palette.PAPER
            outline_w = 3 if hover else 2
        else:
            fill = Palette.WHITE if hover else Palette.PAPER
            outline = color
            text_color = color
            outline_w = 2
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=outline_w)
        text = _clip(label.upper(), max(8, (x1 - x0) // 6))
        c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=text, anchor="center", fill=text_color, font=self._font(9, "bold"), justify="center", width=x1 - x0 - 8)
        self._add_target("action", label, (x0, y0, x1, y1), callback)
        self._add_target("action", label, (x0, y0, x1, y1), callback)

    def _draw_ledger_rail(self, c, box):
        """Draw the city-health rail: a vitals meter block plus scannable system rows."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 4, y0 + 6, x1 + 4, y1 + 6)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.LEDGER, outline="#87987b", width=2)
        c.create_rectangle(x0, y0, x1, y0 + 34, fill="#cad8c0", outline="#87987b")
        c.create_text(x0 + 14, y0 + 17, text="CITY HEALTH", anchor="w", fill=Palette.INK, font=self._font(11, "bold"))
        c.create_line(x0 + 10, y0 + 35, x1 - 10, y0 + 35, fill=Palette.LEDGER_LINE)

        inner_x0 = x0 + 14
        inner_x1 = x1 - 14
        legend_h = 32
        hard_bottom = y1 - legend_h
        y = y0 + 44

        # Vitals: the four core meters that have no home in the banner.
        by_label = {row.label: row for row in self.model.ledger_rows}
        vitals = [by_label[name] for name in ("Prosperity", "Unrest", "Culture", "Risk") if name in by_label]
        if vitals:
            c.create_text(inner_x0, y, text="VITALS", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
            y += 18
            for row in vitals:
                y = self._draw_vital_meter(c, inner_x0, inner_x1, y, row) + 12
            y += 2
            c.create_line(x0 + 10, y, x1 - 10, y, fill=Palette.LEDGER_LINE)
            y += 10

        # System rows: label + left-grouped value so each reads as one unit.
        banner_labels = {"Week", "AP", "Money", "Prosperity", "Unrest", "Culture", "Risk", "Heat"}
        rows = [r for r in self.model.ledger_rows if r.label not in banner_labels]
        value_x = inner_x0 + 104
        shown = 0
        for idx, row in enumerate(rows):
            long_value = _ledger_wraps(row)
            row_h = 38 if long_value else 26
            if y + row_h > hard_bottom:
                break
            fill = "#d5e1ca" if idx % 2 else Palette.LEDGER
            c.create_rectangle(x0 + 8, y - 3, x1 - 8, y + row_h - 6, fill=fill, outline="")
            c.create_text(inner_x0, y, text=row.label.upper(), anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
            if long_value:
                lines = _fit_lines(row.value, max(16, (inner_x1 - inner_x0) // 7), 2)
                c.create_text(inner_x0, y + 14, text="\n".join(lines), anchor="nw", fill=_tone_color(row.tone), font=self._font(9, "bold"))
            else:
                value = _fit_lines(row.value, max(10, (inner_x1 - value_x) // 6), 1)[0]
                c.create_text(value_x, y, text=value, anchor="nw", fill=_tone_color(row.tone), font=self._font(10, "bold"))
            y += row_h
            shown += 1
        overflow = len(rows) - shown
        if overflow > 0 and y + 16 <= hard_bottom:
            c.create_text(inner_x0, y + 1, text=f"+ {overflow} more on scorecard", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))

        c.create_text(inner_x0, y1 - 17, text="Filed marks", anchor="w", fill=Palette.MUTED, font=self._font(8, "bold"))
        for idx, color in enumerate((Palette.BLUE, Palette.GREEN, Palette.RED)):
            sx = x0 + 100 + idx * 30
            c.create_rectangle(sx, y1 - 23, sx + 22, y1 - 11, fill=color, outline="")

    def _draw_vital_meter(self, c, x0, x1, y, row):
        """Draw one labeled vitals gauge (label, numeric value, proportional bar)."""

        tone = _tone_color(row.tone)
        c.create_text(x0, y, text=row.label.upper(), anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        c.create_text(x1, y, text=_clip(row.value, 6), anchor="ne", fill=tone, font=self._font(9, "bold"))
        bar_y0 = y + 15
        pct = max(0, min(100, int(row.meter or 0)))
        c.create_rectangle(x0, bar_y0, x1, bar_y0 + 6, fill="#c4d2b8", outline="")
        if pct:
            c.create_rectangle(x0, bar_y0, x0 + int((x1 - x0) * pct / 100), bar_y0 + 6, fill=tone, outline="")
        return bar_y0 + 6

    def _draw_receipt_panel(self, c, box):
        """Draw the inline filed-report receipt plus the session-control sidebar."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 4, y0 + 6, x1 + 4, y1 + 6)
        side_w = max(150, int((x1 - x0) * 0.24))
        side_x0 = x1 - side_w
        rx1 = side_x0 - 12

        receipt = self.model.receipt
        accent = _receipt_accent(receipt.report) if receipt else Palette.BLUE
        c.create_rectangle(x0, y0, rx1, y1, fill=Palette.PAPER, outline=Palette.LINE, width=2)
        band_h = 30
        c.create_rectangle(x0, y0, rx1, y0 + band_h, fill=accent, outline="")
        c.create_text(x0 + 14, y0 + band_h // 2, text="FILED REPORT", anchor="w", fill=Palette.PAPER, font=self._font(10, "bold"))
        if receipt:
            c.create_rectangle(rx1 - 78, y0 + 5, rx1 - 12, y0 + band_h - 5, outline=Palette.PAPER, width=2)
            c.create_text(rx1 - 45, y0 + band_h // 2, text="FILED", anchor="center", fill=Palette.PAPER, font=self._font(9, "bold"))

        bx0 = x0 + 16
        bx1 = rx1 - 16
        if not receipt:
            c.create_text(bx0, y0 + band_h + 14, text="No report filed yet. Inspect, issue, or deny a case to file one.", anchor="nw", fill=Palette.MUTED, font=self._font(10), width=bx1 - bx0)
        else:
            metric_h = 34
            report_bottom = y1 - metric_h - 12
            yy = _text_bottom(c, bx0, y0 + band_h + 12, _clip(receipt.title, 90), self._font(11, "bold"), Palette.INK) + 7
            line_w = max(28, (bx1 - bx0) // 7)
            # Reserve the last line for the affected-districts row.
            max_lines = max(1, (report_bottom - yy) // 17 - 1)
            body = "\n".join(_fit_lines(receipt.report, line_w, max_lines))
            yy = _text_bottom(c, bx0, yy, body, self._font(10), Palette.INK) + 6
            if yy + 14 <= report_bottom:
                affected = ", ".join(receipt.affected) if receipt.affected else "(none)"
                _text_bottom(c, bx0, yy, _clip("Affected districts: " + affected, 120), self._font(9, "bold"), Palette.BLUE)
            self._draw_receipt_metrics(c, bx0, y1 - metric_h, bx1, receipt.metrics)

        self._draw_session_sidebar(c, (side_x0, y0, x1, y1))

    def _draw_receipt_metrics(self, c, x0, y0, x1, metrics):
        """Draw the compact metric strip pinned to the foot of the receipt."""

        if not metrics:
            return
        c.create_line(x0, y0 - 4, x1, y0 - 4, fill="#c4b798")
        mw = (x1 - x0) // max(1, len(metrics))
        for idx, (label, value) in enumerate(metrics):
            mx = x0 + idx * mw
            c.create_text(mx, y0, text=label, anchor="nw", fill=Palette.MUTED, font=self._font(7, "bold"))
            c.create_text(mx, y0 + 13, text=_clip(value, 9), anchor="nw", fill=Palette.INK, font=self._font(10, "bold"))

    def _draw_session_sidebar(self, c, box):
        """Draw New Game / Scorecard controls and the exhibit pill beside the receipt."""

        x0, y0, x1, y1 = box
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER_ALT, outline=Palette.LINE, width=2)
        pad = 12
        bx0 = x0 + pad
        bx1 = x1 - pad
        bh = 30
        gap = 8
        self._draw_session_button(c, bx0, y0 + pad, bx1, y0 + pad + bh, "New Game", Palette.BLUE, self.callbacks.new_game)
        self._draw_session_button(c, bx0, y0 + pad + bh + gap, bx1, y0 + pad + 2 * bh + gap, "Scorecard", Palette.GOLD, self.callbacks.scorecard)
        exhibit = self.model.exhibit_visible
        pill_label = "EXHIBIT ON" if exhibit else "EXHIBIT OFF"
        pill_color = Palette.GREEN if exhibit else Palette.MUTED
        py1 = y1 - pad
        py0 = py1 - 24
        c.create_rectangle(bx0, py0, bx1, py1, fill=Palette.PAPER, outline=pill_color, width=2)
        c.create_text((bx0 + bx1) // 2, (py0 + py1) // 2, text=pill_label, anchor="center", fill=pill_color, font=self._font(8, "bold"))

    def _draw_session_button(self, c, x0, y0, x1, y1, label, color, callback):
        """Draw a compact dashboard-level command button."""

        hover = self._hover_key == f"session:{label}"
        fill = Palette.WHITE if hover else Palette.PAPER
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=color, width=2)
        c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=label.upper(), anchor="center", fill=color, font=self._font(8, "bold"))
        self._add_target("session", label, (x0, y0, x1, y1), callback)

    def _add_target(self, kind, ident, bbox, callback):
        """Record a clickable canvas rectangle for later event dispatch."""

        self._click_targets.append((kind, ident, bbox, callback))

    def _font(self, size, weight="normal"):
        """Return the Segoe UI font tuple used by the desk canvas."""

        return ("Segoe UI", size, weight)

    def _fit_px(self, text, size, weight, max_px):
        """Truncate text with an ellipsis so it renders within ``max_px`` pixels.

        Uses real Tk font metrics when available, falling back to a conservative
        character estimate (so headless rendering and tests still work).
        """

        text = " ".join(str(text or "").split())
        measure = self._px_measurer(size, weight)
        if measure is None:
            return _clip(text, max(4, int(max_px // (size * 0.62))))
        if measure(text) <= max_px:
            return text
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if measure(text[:mid] + "...") <= max_px:
                lo = mid
            else:
                hi = mid - 1
        return (text[:lo] + "...") if lo else "..."

    def _px_measurer(self, size, weight):
        """Return a cached Tk font ``measure`` callable, or None if unavailable."""

        cache = getattr(self, "_font_cache", None)
        if cache is None:
            cache = self._font_cache = {}
        key = (size, weight)
        if key not in cache:
            try:
                import tkinter.font as tkfont

                cache[key] = tkfont.Font(root=self.root, family="Segoe UI", size=size, weight=weight)
            except Exception:
                cache[key] = None
        font = cache[key]
        return font.measure if font is not None else None


def _receipt_accent(report):
    """Map the result text to the filed-report title band color."""

    lower = (report or "").lower()
    if lower.startswith(("approved with", "approved (")):
        return "#527d65"
    if lower.startswith(("approved", "issued")):
        return Palette.GREEN
    if lower.startswith(("denied", "deny")):
        return Palette.RED
    if lower.startswith(("inspected", "inspection")):
        return Palette.GOLD
    return Palette.BLUE


def _draw_ruled_block(c, x0, y0, x1, y1, label, text, accent, font_factory, max_y=None):
    """Draw a labeled ruled-paper block, pre-wrapping text so it never overruns.

    ``max_y`` clamps the block bottom; the body is wrapped to the exact number of
    lines that fit, so canvas text can never spill past the block.
    """

    if max_y is not None:
        y1 = min(y1, max_y)
    if y1 - y0 < 24:
        y1 = y0 + 24
    c.create_rectangle(x0, y0, x1, y1, fill="#fbf3dc", outline="#d4c7aa")
    c.create_rectangle(x0, y0, x1, y0 + 20, fill="#efe3c8", outline="#d4c7aa")
    c.create_text(x0 + 8, y0 + 5, text=label, anchor="nw", fill=accent, font=font_factory(8, "bold"))
    for yy in range(y0 + 40, y1 - 6, 18):
        c.create_line(x0 + 8, yy, x1 - 8, yy, fill="#e3d7bd")
    line_w = max(16, (x1 - x0 - 22) // 7)
    max_lines = max(1, (y1 - (y0 + 28)) // 18)
    body = "\n".join(_fit_lines(text, line_w, max_lines))
    c.create_text(x0 + 10, y0 + 26, text=body, anchor="nw", fill=Palette.INK, font=font_factory(10))


def _draw_impact_buckets(c, x, y, width, buckets, font_factory, max_y=None):
    """Draw compact impact buckets in a two-column grid, stopping at ``max_y``."""

    if not buckets:
        return 0
    gap = 8
    bucket_h = 64
    col_w = max(118, (width - gap) // 2)
    drawn = 0
    for idx, bucket in enumerate(buckets):
        col = idx % 2
        row = idx // 2
        by0 = y + row * (bucket_h + 7)
        by1 = by0 + bucket_h
        if max_y is not None and by1 > max_y:
            break
        bx0 = x + col * (col_w + gap)
        bx1 = min(x + width, bx0 + col_w)
        tone = _tone_color(bucket.tone)
        c.create_rectangle(bx0, by0, bx1, by1, fill="#f6edd6", outline="#d4c7aa")
        c.create_rectangle(bx0, by0, bx0 + 5, by1, fill=tone, outline="")
        c.create_text(bx0 + 12, by0 + 6, text=bucket.label.upper(), anchor="nw", fill=Palette.MUTED, font=font_factory(7, "bold"))
        # Pre-wrap to a bounded two lines so the value never bleeds into the row below.
        value_lines = _fit_lines(bucket.value, max(18, (bx1 - bx0 - 24) // 6), 2)
        c.create_text(bx0 + 12, by0 + 20, text="\n".join(value_lines), anchor="nw", fill=Palette.INK, font=font_factory(9, "bold"))
        drawn = idx + 1
    rows = (drawn + 1) // 2
    return rows * bucket_h + max(0, rows - 1) * 7


def _shadow_rect(c, x0, y0, x1, y1):
    """Draw a simple rectangular paper shadow."""

    c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER_SHADOW, outline="")


def _inside(x, y, bbox):
    """Return whether a point is inside a canvas bounding box."""

    x0, y0, x1, y1 = bbox
    return x0 <= x <= x1 and y0 <= y <= y1


def _clip(value, width):
    """Shorten text to a single normalized line for canvas rendering."""

    return shorten(" ".join(str(value or "").split()), width=width, placeholder="...")


def _ledger_wraps(row: LedgerRow) -> bool:
    """Return whether a ledger value needs its own wrapped text lane."""

    return row.label.lower() in ("heat", "pressure", "services", "hazards", "housing", "population", "incidents") and len(str(row.value or "")) > 18


def _fit_lines(value, line_width, max_lines):
    """Wrap text to a bounded number of lines for fixed-size canvas panels."""

    lines = wrap(" ".join(str(value or "").split()), width=line_width)
    if len(lines) <= max_lines:
        return lines
    return lines[: max_lines - 1] + [_clip(f"{lines[max_lines - 1]} ...", line_width)]


def _status_color(status):
    """Map docket or feature status to a palette color."""

    value = (status or "").lower()
    if value in ("open", "carried"):
        return Palette.BLUE
    if value in ("inspected", "settled", "maintained"):
        return Palette.GOLD
    if value in ("active", "approved", "responded", "enforced"):
        return Palette.GREEN
    if value in ("denied", "deferred", "failed"):
        return Palette.RED
    return Palette.MUTED


def _risk_color(risk):
    """Map inspection risk bands to a palette color."""

    value = (risk or "").lower()
    if value == "high":
        return Palette.RED
    if value == "medium":
        return Palette.GOLD
    if value == "low":
        return Palette.GREEN
    return Palette.MUTED


def _tone_color(tone):
    """Map ledger row tone names to palette colors."""

    if tone == "good":
        return Palette.GREEN
    if tone == "bad":
        return Palette.RED
    if tone == "watch":
        return Palette.GOLD
    return Palette.INK
