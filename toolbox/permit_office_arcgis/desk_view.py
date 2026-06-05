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
    ReceiptModel,
    ReportTab,
    build_desk_model,
    _hazard_summary,
    _maintenance_summary,
    _service_gap_summary,
)


# Floors used while the window is still sizing; the desk re-flows for a portrait
# pane that fills half of a 1920x1080 monitor beside ArcGIS Pro.
MIN_DESK_W = 1120
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

    DESK = "#e8edf0"
    DESK_DARK = "#1f3f3a"
    PAPER = "#ffffff"
    PAPER_ALT = "#f4f7f5"
    PAPER_SHADOW = "#c2cbc8"
    FOLDER = "#d8e1de"
    NOTE = "#eef4f1"
    NOTE_BLUE = "#e8f1f7"
    INK = "#142421"
    MUTED = "#5d6e69"
    LINE = "#c6d0cc"
    RED = "#b5423f"
    GREEN = "#2f6b53"
    BLUE = "#2f6488"
    GOLD = "#9f7028"
    TEAL = "#3f7470"
    CARD_SHADOW = "#b5c2be"
    LEDGER = "#f7faf8"
    LEDGER_LINE = "#9dafaa"
    WHITE = "#ffffff"


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
        self._fit_cache: dict = {}
        # Per-model lookup maps (label->row, action_id->lane), rebuilt only when
        # the model object changes (see _ensure_lookups).
        self._lookup_model = None
        self._ledger_by_label: dict = {}
        self._lane_by_action: dict = {}
        self._menu_open = False
        self._menu_anchor = None

        self.canvas = tk.Canvas(root, bg=Palette.DESK, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)

    def render(self, model: DeskViewModel):
        """Store and draw the latest view model."""

        self.model = model
        # New frame content: bound the text-fit memo to this model's strings.
        # (Left warm across hover redraws and deadline ticks, which keep the model.)
        self._fit_cache.clear()
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
        if self._menu_open:
            self._menu_open = False
            self._redraw_current()
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
            self._redraw_current()

    def _on_leave(self, _event):
        """Clear hover state when the pointer leaves the canvas."""

        if self._hover_key:
            self._hover_key = ""
            self.canvas.configure(cursor="")
            self._redraw_current()

    def _redraw_current(self):
        """Redraw using the current canvas size."""

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

        self._draw_top_banner(c, width, banner_h)
        status_y0 = banner_h + gap
        self._draw_status_strip(c, (margin, status_y0, width - margin, status_y0 + status_h))

        body_y0 = status_y0 + status_h + gap
        body_y1 = height - margin

        health_w = min(280, max(230, int((width - 2 * margin) * 0.24)))
        health_x1 = width - margin
        health_x0 = health_x1 - health_w
        workspace_x0 = margin
        workspace_x1 = health_x0 - gap

        self._draw_main_workspace(c, (workspace_x0, body_y0, workspace_x1, body_y1))
        self._draw_ledger_rail(c, (health_x0, body_y0, health_x1, body_y1))
        if self._menu_open:
            self._draw_session_menu(c, width)
        if self.model.show_start_help:
            self._draw_start_help_overlay(c, width, height)

    def _draw_background(self, c, width, height):
        """Paint the desk surface (banner draws its own dark band on top)."""

        c.create_rectangle(0, 0, width, height, fill=Palette.DESK, outline="")

    def _draw_top_banner(self, c, width, h):
        """Draw the headline-metrics banner across the desk lip."""

        c.create_rectangle(0, 0, width, h, fill=Palette.DESK_DARK, outline="")
        c.create_rectangle(0, h - 3, width, h, fill=Palette.CARD_SHADOW, outline="")
        c.create_text(28, h // 2, text="PERMIT OFFICE", anchor="w", fill=Palette.PAPER, font=self._font(14, "bold"))
        self._ensure_lookups()
        metrics = self._ledger_by_label
        headlines = HEADLINE_METRICS
        x_start = 310
        right_pad = 216 if self.model.deadline_text else 28
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
        ticker = "  |  ".join(self.model.ticker_items or ())
        base = self.model.status_text or ticker or "Ready."
        text = _clip(base, max(40, (x1 - x0 - 90) // 7))
        c.create_text(x0 + 78, mid, text=text, anchor="w", fill=Palette.PAPER, font=self._font(10))

    def _draw_main_workspace(self, c, box):
        """Draw the primary Applications/Filed Reports tab workspace."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 6, y0 + 8, x1 + 6, y1 + 8)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER_ALT, outline=Palette.LINE, width=2)
        primary_h = 30
        tab_w = 160
        apps_selected = self.model.selected_desk_tab == "applications"
        reports_selected = self.model.selected_desk_tab == "reports"
        self._draw_primary_tab(c, x0 + 12, y0, x0 + 12 + tab_w, y0 + primary_h, "Applications", apps_selected, lambda: self.callbacks.select_desk_tab("applications"))
        self._draw_primary_tab(c, x0 + 12 + tab_w + 8, y0, x0 + 12 + 2 * tab_w + 8, y0 + primary_h, "Filed Reports", reports_selected, lambda: self.callbacks.select_desk_tab("reports"))
        self._draw_menu_button(c, x1 - 52, y0 + 4, x1 - 12, y0 + primary_h - 3)
        content = (x0 + 12, y0 + primary_h + 18, x1 - 12, y1 - 12)
        if reports_selected:
            self._draw_report_tab_content(c, content)
        else:
            self._draw_application_tab_content(c, content)

    def _draw_primary_tab(self, c, x0, y0, x1, y1, label, selected, callback):
        """Draw a primary lower-tab header."""

        fill = Palette.WHITE if selected else Palette.PAPER
        outline = Palette.BLUE if selected else Palette.LINE
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=2 if selected else 1)
        c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=label.upper(), anchor="center", fill=Palette.INK if selected else Palette.MUTED, font=self._font(8, "bold"))
        self._add_target("desk-tab", label, (x0, y0, x1, y1), callback)

    def _draw_application_tab_content(self, c, box):
        """Draw nested application tabs and the selected application packet."""

        x0, y0, x1, y1 = box
        active_id = self.model.selected_item_id
        rows = list(self.model.docket_rows)
        total_open = len(rows)

        c.create_text(x1, y0 + 2, text=f"{total_open} OPEN", anchor="ne", fill=Palette.MUTED, font=self._font(8, "bold"))

        if not rows:
            self._draw_queue_cleared_state(c, box)
            return

        active = next((row for row in rows if row.item_id == active_id), rows[0])
        others = [row for row in rows if row.item_id != active.item_id]

        # Vertical docket stack: the active case stays prominent as the full
        # decision brief, while queued cases collapse into narrow rows beneath it
        # and vanish from the stack as they are resolved. The active card keeps a
        # minimum height so the stack never crowds the decision out.
        row_h = 28
        gap = 6
        header_h = 16
        card_min = 280  # floor height reserved for the active decision card
        # Rows that fit = leftover height after the top inset (16), the active
        # card floor, the queue header, and bottom padding (18), divided by a
        # collapsed row + its gap. Hard-capped at 8 so a huge docket still reads.
        stack_capacity = max(0, (y1 - (y0 + 16) - card_min - header_h - 18) // (row_h + gap))
        visible_count = min(len(others), max(0, stack_capacity), 8)
        stack_overflow = len(others) - visible_count

        if visible_count <= 0:
            self._draw_active_card(c, (x0, y0 + 16, x1, y1))
            return

        stack_h = header_h + visible_count * (row_h + gap)
        card_bottom = y1 - stack_h - 14
        self._draw_active_card(c, (x0, y0 + 16, x1, card_bottom))

        sy = card_bottom + 14
        c.create_text(x0, sy, text=f"QUEUED ({len(others)})", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        if stack_overflow > 0:
            c.create_text(x1, sy, text=f"+{stack_overflow} more queued", anchor="ne", fill=Palette.MUTED, font=self._font(8, "bold"))
        sy += header_h
        for row in others[:visible_count]:
            self._draw_collapsed_docket_row(c, x0, sy, x1, sy + row_h, row)
            sy += row_h + gap

    def _draw_collapsed_docket_row(self, c, x0, y0, x1, y1, row):
        """Draw one collapsed queued docket case as a slim selectable row."""

        hover = self._hover_key == f"docket:{row.item_id}"
        outline = _status_color(row.status)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.WHITE if hover else Palette.PAPER_ALT, outline=Palette.LINE)
        c.create_rectangle(x0, y0, x0 + 4, y1, fill=outline, outline="")
        c.create_text(x0 + 14, (y0 + y1) // 2, text=row.status.upper(), anchor="w", fill=outline, font=self._font(7, "bold"))
        c.create_text(x0 + 96, (y0 + y1) // 2, text=self._fit_px(row.title, 10, "bold", x1 - x0 - 110), anchor="w", fill=Palette.INK, font=self._font(10, "bold"))
        self._add_target("docket", row.item_id, (x0, y0, x1, y1), lambda item_id=row.item_id: self.on_select_item(item_id))

    def _draw_queue_cleared_state(self, c, box):
        """Draw the empty-docket panel: a start prompt before a game exists, or
        the queue-cleared / End Week controls once one is running."""

        x0, y0, x1, y1 = box
        card_y0 = y0 + 34
        _shadow_rect(c, x0 + 4, card_y0 + 5, x1 + 4, y1 + 5)
        c.create_rectangle(x0, card_y0, x1, y1, fill=Palette.PAPER, outline=Palette.LINE, width=1)
        if not self.model.game_active:
            c.create_text(x0 + 24, card_y0 + 26, text="No game yet", anchor="nw", fill=Palette.INK, font=self._font(18, "bold"))
            start_body = (
                "This workspace has no active Permit Office board. Click New Game "
                "to generate a city and start the 12-week season."
            )
            c.create_text(x0 + 24, card_y0 + 66, text=start_body, anchor="nw", fill=Palette.MUTED, font=self._font(11), width=x1 - x0 - 48)
            by0 = y1 - 64
            self._draw_case_action(c, x0 + 24, by0, x0 + 164, by0 + 40, "New Game", Palette.BLUE, self.callbacks.new_game, primary=True)
            return
        c.create_text(x0 + 24, card_y0 + 26, text="Queue cleared", anchor="nw", fill=Palette.INK, font=self._font(18, "bold"))
        body = "All applications have been filed. End Week to process follow-ups."
        if self.model.auto_close_active:
            body = f"{body} Automatic close in {self.model.auto_close_seconds} seconds."
        c.create_text(x0 + 24, card_y0 + 66, text=body, anchor="nw", fill=Palette.MUTED, font=self._font(11), width=x1 - x0 - 48)
        by0 = y1 - 64
        self._draw_case_action(c, x0 + 24, by0, x0 + 164, by0 + 40, "End Week", Palette.INK, self.callbacks.advance_turn, primary=True)
        if self.model.auto_close_active:
            self._draw_case_action(c, x0 + 176, by0, x0 + 344, by0 + 40, "Cancel Auto Close", Palette.MUTED, self.callbacks.cancel_queue_autoclose, primary=False)

    def _draw_report_tab_content(self, c, box):
        """Draw filed-report nested tabs and the selected report body."""

        x0, y0, x1, y1 = box
        tabs = self.model.report_tabs or ()
        if not tabs:
            c.create_rectangle(x0, y0 + 18, min(x1, x0 + 180), y0 + 72, fill=Palette.WHITE, outline=Palette.BLUE, width=2)
            c.create_text(x0 + 10, y0 + 30, text="NO REPORT FILED", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
            c.create_text(x0 + 10, y0 + 50, text="Inspect, issue, deny, end week, or open Scorecard.", anchor="nw", fill=Palette.MUTED, font=self._font(8))
            return
        visible = list(tabs)[-4:]
        gap = 6
        tab_area_h = 62
        tab_w = max(112, (x1 - x0 - gap * (len(visible) - 1)) // max(1, len(visible)))
        tx = x0
        for tab in visible:
            selected = tab.selected
            hover = self._hover_key == f"report:{tab.report_id}"
            fill = Palette.WHITE if selected or hover else Palette.PAPER
            outline = _status_color(tab.status)
            ty0 = y0 + (14 if not selected else 8)
            tx1 = min(x1, tx + tab_w)
            c.create_rectangle(tx, ty0, tx1, y0 + tab_area_h, fill=fill, outline=outline, width=2 if selected else 1)
            c.create_rectangle(tx, ty0, tx1, ty0 + 5, fill=outline, outline="")
            c.create_text(tx + 8, ty0 + 14, text=self._fit_px(tab.title, 9, "bold", tx1 - tx - 16), anchor="nw", fill=Palette.INK, font=self._font(9, "bold"))
            c.create_text(tx + 8, y0 + tab_area_h - 18, text=tab.status.upper(), anchor="nw", fill=Palette.MUTED, font=self._font(7, "bold"))
            self._add_target("report", tab.report_id, (tx, ty0, tx1, y0 + tab_area_h), lambda report_id=tab.report_id: self.callbacks.select_report(report_id))
            tx += tab_w + gap
        selected_report = next((tab for tab in tabs if tab.selected), tabs[-1])
        body_y0 = y0 + tab_area_h + 10
        c.create_rectangle(x0, body_y0, x1, y1, fill=Palette.PAPER, outline=Palette.LINE)
        bx0 = x0 + 14
        bx1 = x1 - 14
        yy = _text_bottom(c, bx0, body_y0 + 10, self._fit_px(selected_report.title, 11, "bold", bx1 - bx0), self._font(11, "bold"), Palette.INK) + 6
        max_lines = max(1, (y1 - yy - 34) // 16)
        line_w = max(24, (bx1 - bx0) // 7)
        body = "\n".join(_fit_lines(selected_report.report, line_w, max_lines))
        _text_bottom(c, bx0, yy, body, self._font(9), Palette.INK)
        if selected_report.metrics:
            self._draw_receipt_metrics(c, bx0, y1 - 28, bx1, selected_report.metrics)

    def _draw_active_card(self, c, box):
        """Draw the selected application as a modern decision brief."""

        x0, y0, x1, y1 = box
        case = self.model.case
        _shadow_rect(c, x0 + 4, y0 + 5, x1 + 4, y1 + 5)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER, outline=Palette.LINE, width=1)

        pad = 22
        body_x0 = x0 + pad
        body_x1 = x1 - pad
        risk_known = (case.risk_band or "unknown").lower() not in ("", "unknown")
        risk_text = "RISK: " + case.risk_band.upper() if risk_known else "RISK: PENDING"
        c.create_text(body_x0, y0 + 18, text="DECISION BRIEF", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        c.create_text(body_x0, y0 + 40, text=self._fit_px(case.title, 16, "bold", body_x1 - body_x0 - 150), anchor="nw", fill=Palette.INK, font=self._font(16, "bold"))
        self._draw_status_badge(c, body_x1 - 132, y0 + 34, body_x1, y0 + 60, risk_text, _risk_color(case.risk_band))
        yy = y0 + 78
        preview_lines = _fit_lines(case.preview, max(44, (body_x1 - body_x0) // 8), 2)
        yy = _text_bottom(c, body_x0, yy, "\n".join(preview_lines), self._font(10), Palette.MUTED, width=body_x1 - body_x0) + 14
        c.create_text(body_x0, yy, text="Affected districts", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        yy = _text_bottom(c, body_x0, yy + 16, self._fit_px(case.districts, 11, "bold", body_x1 - body_x0), self._font(11, "bold"), Palette.INK) + 14
        inspected = bool(case.inspection) and not case.inspection.lower().startswith("no inspection")
        note = case.inspection if inspected else "Uninspected: decision impacts are estimates. Inspect File may reveal violations or stronger stakeholder reactions."
        note_color = Palette.RED if inspected and case.risk_band == "high" else Palette.GOLD if not inspected else Palette.BLUE
        note_h = 42
        c.create_rectangle(body_x0, yy, body_x1, yy + note_h, fill="#fff8e9" if not inspected else Palette.NOTE_BLUE, outline="")
        c.create_rectangle(body_x0, yy, body_x0 + 4, yy + note_h, fill=note_color, outline="")
        note_lines = _fit_lines(note, max(30, (body_x1 - body_x0 - 24) // 7), 2)
        c.create_text(body_x0 + 12, yy + 8, text="\n".join(note_lines), anchor="nw", fill=Palette.INK, font=self._font(9, "bold"))
        yy += note_h + 14

        if case.economy:
            econ_qualifier = "filed" if inspected else "est."
            econ_text = f"Budget ({econ_qualifier}): {case.economy}" if case.economy != "no recurring budget" else "Budget: no recurring revenue or upkeep"
            econ_color = Palette.GREEN if "net +" in case.economy else Palette.RED if "net -" in case.economy else Palette.MUTED
            c.create_text(body_x0, yy, text=self._fit_px(econ_text, 9, "bold", body_x1 - body_x0), anchor="nw", fill=econ_color, font=self._font(9, "bold"))
            yy += 16
        if case.action_note:
            c.create_text(body_x0, yy, text=self._fit_px(case.action_note, 8, "normal", body_x1 - body_x0), anchor="nw", fill=Palette.MUTED, font=self._font(8))
            yy += 16
        yy += 2

        lanes = self.model.action_lanes
        lane_gap = 8
        lane_h = min(92, max(72, (y1 - yy - 92 - lane_gap * max(0, len(lanes) - 1)) // max(1, len(lanes))))
        for lane in self.model.action_lanes:
            self._draw_decision_lane(c, body_x0, yy, body_x1, yy + lane_h, lane)
            yy += lane_h + lane_gap
        controls_y = min(y1 - 58, yy + 12)
        self._draw_case_controls(c, body_x0, controls_y, body_x1, y1 - 18)

    def _draw_status_badge(self, c, x0, y0, x1, y1, text, color):
        """Draw a restrained status badge."""

        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER_ALT, outline=color, width=1)
        c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=self._fit_px(text, 8, "bold", x1 - x0 - 10), anchor="center", fill=color, font=self._font(8, "bold"))

    def _draw_decision_lane(self, c, x0, y0, x1, y1, lane):
        """Draw one decision consequence lane."""

        tone = _tone_color(lane.tone)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER_ALT, outline=Palette.LINE)
        lane_tone = tone if lane.enabled else Palette.MUTED
        c.create_rectangle(x0, y0, x0 + 4, y1, fill=lane_tone, outline="")
        label_w = min(220, max(176, int((x1 - x0) * 0.18)))
        city_w = min(260, max(190, int((x1 - x0) * 0.25)))
        c.create_text(x0 + 14, y0 + 11, text=lane.label, anchor="nw", fill=Palette.INK if lane.enabled else Palette.MUTED, font=self._font(11, "bold"))
        cost_text = lane.cost if lane.enabled else lane.disabled_reason or lane.cost
        c.create_text(x0 + 14, y0 + 38, text=self._fit_px(cost_text, 9, "bold", label_w - 22), anchor="nw", fill=lane_tone, font=self._font(9, "bold"))
        city_x = x0 + label_w
        local_x = city_x + city_w + 10
        c.create_text(city_x, y0 + 10, text="City", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        c.create_text(city_x, y0 + 29, text="\n".join(_fit_lines(lane.city_effect, max(20, (city_w - 10) // 7), 2)), anchor="nw", fill=Palette.INK, font=self._font(9))
        c.create_text(local_x, y0 + 10, text="Local", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        c.create_text(local_x, y0 + 29, text="\n".join(_fit_lines(lane.local_effect, max(30, (x1 - local_x - 14) // 7), 2)), anchor="nw", fill=Palette.INK, font=self._font(9))

    def _draw_case_controls(self, c, x0, y0, x1, y1):
        """Draw selected-case map, inspect, and stamp controls inside the card."""

        exhibit_label = "Hide Proposed Feature" if self.model.exhibit_visible else "Show Proposed Feature"
        self._ensure_lookups()
        lanes = self._lane_by_action
        controls = (
            (exhibit_label, Palette.BLUE, self.callbacks.toggle_exhibit, False, True),
            ("Retarget Map", Palette.TEAL, self.callbacks.update_from_map, False, True),
            ("Inspect File", Palette.GOLD, self.callbacks.inspect, False, True),
            tuple(),
            (lanes.get("approve").label if lanes.get("approve") else "Issue Permit", Palette.GREEN, self.callbacks.approve, True, lanes.get("approve").enabled if lanes.get("approve") else True),
            (lanes.get("approve_mitigated").label if lanes.get("approve_mitigated") else "Add Conditions", "#527d65", self.callbacks.approve_mitigated, True, lanes.get("approve_mitigated").enabled if lanes.get("approve_mitigated") else True),
            (lanes.get("deny").label if lanes.get("deny") else "Deny", Palette.RED, self.callbacks.deny, True, lanes.get("deny").enabled if lanes.get("deny") else True),
        )
        concrete = [row for row in controls if row]
        gap = 8
        chip_w = max(96, (x1 - x0 - gap * (len(concrete) - 1)) // max(1, len(concrete)))
        chip_h = min(38, y1 - y0)
        cx = x0
        for label, color, callback, primary, enabled in concrete:
            self._draw_case_action(c, cx, y0, min(x1, cx + chip_w), y0 + chip_h, label, color, callback, primary, enabled)
            cx += chip_w + gap

    def _draw_case_action(self, c, x0, y0, x1, y1, label, color, callback, primary=False, enabled=True):
        """Draw an in-card action button and register it."""

        hover = self._hover_key == f"case-action:{label}"
        fill = color if primary and enabled else Palette.PAPER_ALT
        text_color = Palette.WHITE if primary and enabled else color if enabled else Palette.MUTED
        outline = color if enabled and not hover else Palette.INK if enabled else Palette.LINE
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=2 if hover else 1)
        c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=label, anchor="center", fill=text_color, font=self._font(8, "bold"), width=x1 - x0 - 8)
        if enabled:
            self._add_target("case-action", label, (x0, y0, x1, y1), callback)

    def _draw_ledger_rail(self, c, box):
        """Draw the slim city pulse rail for triage context."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 4, y0 + 6, x1 + 4, y1 + 6)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.LEDGER, outline=Palette.LINE, width=1)
        c.create_text(x0 + 14, y0 + 18, text="CITY PULSE", anchor="w", fill=Palette.INK, font=self._font(11, "bold"))
        c.create_line(x0 + 14, y0 + 38, x1 - 14, y0 + 38, fill=Palette.LINE)

        inner_x0 = x0 + 14
        inner_x1 = x1 - 14
        self._ensure_lookups()
        by_label = self._ledger_by_label

        # Headline: one City Health gauge folds the four core metrics together.
        y = y0 + 50
        health = by_label.get("Health")
        if health:
            tone = _tone_color(health.tone)
            c.create_text(inner_x0, y, text="CITY HEALTH", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
            c.create_text(inner_x1, y - 2, text=_clip(health.value, 18), anchor="ne", fill=tone, font=self._font(13, "bold"))
            bar_y0 = y + 20
            pct = max(0, min(100, int(health.meter or 0)))
            c.create_rectangle(inner_x0, bar_y0, inner_x1, bar_y0 + 9, fill="#dce5e1", outline="")
            if pct:
                c.create_rectangle(inner_x0, bar_y0, inner_x0 + int((inner_x1 - inner_x0) * pct / 100), bar_y0 + 9, fill=tone, outline="")
            y = bar_y0 + 9 + 14

        # Heat as the leading indicator of trouble brewing into later filings.
        heat = by_label.get("Heat")
        if heat:
            heat_tone = _tone_color(heat.tone)
            c.create_text(inner_x0, y, text="HEAT", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
            c.create_text(inner_x1, y, text=_clip(heat.value, 20), anchor="ne", fill=heat_tone, font=self._font(9, "bold"))
            hint = "drives later incidents & enforcement" if heat.value != "none" else "calm; no escalation brewing"
            c.create_text(inner_x0, y + 15, text=self._fit_px(hint, 8, "normal", inner_x1 - inner_x0), anchor="nw", fill=Palette.MUTED, font=self._font(8))
            y += 36
        c.create_line(inner_x0, y, inner_x1, y, fill=Palette.LINE)
        y += 12

        # Core-metric breakdown beneath the headline.
        pulse = [by_label[name] for name in ("Activity", "Trust", "Friction", "Exposure", "Pressure") if name in by_label]
        for row in pulse:
            if y + 48 > y1 - 54:
                break
            y = self._draw_pulse_row(c, inner_x0, inner_x1, y, row) + 12

        ticker = self.model.ticker_items[0] if self.model.ticker_items else "City desk quiet."
        c.create_line(inner_x0, y1 - 58, inner_x1, y1 - 58, fill=Palette.LINE)
        c.create_text(inner_x0, y1 - 44, text="WIRE", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        c.create_text(inner_x0, y1 - 27, text=self._fit_px(ticker, 8, "normal", inner_x1 - inner_x0), anchor="nw", fill=Palette.MUTED, font=self._font(8))

    def _draw_pulse_row(self, c, x0, x1, y, row):
        """Draw one city pulse signal."""

        tone = _tone_color(row.tone)
        c.create_text(x0, y, text=row.label.upper(), anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        c.create_text(x1, y, text=_clip(row.value, 20), anchor="ne", fill=tone, font=self._font(9, "bold"))
        bar_y0 = y + 20
        pct = max(0, min(100, int(row.meter or 0)))
        c.create_rectangle(x0, bar_y0, x1, bar_y0 + 7, fill="#dce5e1", outline="")
        if pct:
            c.create_rectangle(x0, bar_y0, x0 + int((x1 - x0) * pct / 100), bar_y0 + 7, fill=tone, outline="")
        return bar_y0 + 7

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

    def _draw_menu_button(self, c, x0, y0, x1, y1):
        """Draw the compact utility menu trigger."""

        hover = self._hover_key == "session:Menu"
        fill = Palette.WHITE if hover or self._menu_open else Palette.PAPER
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=Palette.BLUE, width=2)
        mid = (y0 + y1) // 2
        line_x0 = x0 + 11
        line_x1 = x1 - 11
        for offset in (-5, 0, 5):
            c.create_line(line_x0, mid + offset, line_x1, mid + offset, fill=Palette.BLUE, width=2)
        self._menu_anchor = (x0, y0, x1, y1)
        self._add_target("session", "Menu", (x0, y0, x1, y1), self._toggle_session_menu)

    def _toggle_session_menu(self):
        """Open or close the utility command dropdown."""

        self._menu_open = not self._menu_open
        if self._menu_open:
            self.callbacks.pause_queue_autoclose()
        self._redraw_current()

    def _draw_session_menu(self, c, width):
        """Draw dropdown utility actions over the desk surface."""

        entries = (
            ("End Week", Palette.INK, self.callbacks.advance_turn),
            ("New Game", Palette.BLUE, self.callbacks.new_game),
            ("Scorecard", Palette.GOLD, self.callbacks.scorecard),
            ("Help", Palette.TEAL, self.callbacks.show_help),
            ("End Game", Palette.MUTED, self.callbacks.end_game),
        )
        anchor = getattr(self, "_menu_anchor", None)
        if anchor:
            ax0, _ay0, ax1, ay1 = anchor
            x1 = min(width - 18, ax1)
            x0 = max(18, x1 - 176)
            if x0 < ax0 - 176:
                x0 = max(18, ax0 - 176)
                x1 = x0 + 176
            y0 = ay1
        else:
            x1 = width - 32
            x0 = x1 - 176
            y0 = 142
        row_h = 34
        y1 = y0 + row_h * len(entries)
        _shadow_rect(c, x0 + 5, y0 + 6, x1 + 5, y1 + 6)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER, outline=Palette.INK, width=2)
        for idx, (label, color, callback) in enumerate(entries):
            ry0 = y0 + idx * row_h
            ry1 = ry0 + row_h
            hover = self._hover_key == f"session:{label}"
            c.create_rectangle(x0, ry0, x1, ry1, fill=Palette.WHITE if hover else Palette.PAPER, outline=Palette.LINE)
            c.create_rectangle(x0, ry0, x0 + 5, ry1, fill=color, outline="")
            c.create_text(x0 + 14, (ry0 + ry1) // 2, text=label.upper(), anchor="w", fill=color, font=self._font(8, "bold"))
            self._add_target("session", label, (x0, ry0, x1, ry1), self._close_menu_callback(callback))

    def _close_menu_callback(self, callback):
        """Wrap a menu callback so the dropdown closes before the action runs."""

        def _wrapped():
            self._menu_open = False
            callback()

        return _wrapped

    def _draw_session_button(self, c, x0, y0, x1, y1, label, color, callback):
        """Draw a compact dashboard-level command button."""

        hover = self._hover_key == f"session:{label}"
        fill = Palette.WHITE if hover else Palette.PAPER
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=color, width=2)
        c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=label.upper(), anchor="center", fill=color, font=self._font(8, "bold"))
        self._add_target("session", label, (x0, y0, x1, y1), callback)

    def _draw_start_help_overlay(self, c, width, height):
        """Draw the in-window start/help sheet."""

        ow = min(620, width - 80)
        oh = min(520, height - 120)
        x0 = (width - ow) // 2
        y0 = (height - oh) // 2
        x1 = x0 + ow
        y1 = y0 + oh
        _shadow_rect(c, x0 + 8, y0 + 10, x1 + 8, y1 + 10)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER, outline=Palette.INK, width=2)
        c.create_rectangle(x0, y0, x1, y0 + 46, fill=Palette.BLUE, outline="")
        title = "START PERMIT OFFICE" if not self.model.docket_rows else "PERMIT OFFICE HELP"
        c.create_text(x0 + 22, y0 + 23, text=title, anchor="w", fill=Palette.PAPER, font=self._font(15, "bold"))
        body_x0 = x0 + 26
        body_x1 = x1 - 26
        y = y0 + 66
        lines = (
            "Review applications, inspect only what needs attention, then issue, add conditions, deny, or let filings expire.",
            "AP is institutional attention. Inspect File, Issue Permit, and Add Conditions spend AP; Deny costs 0 AP.",
            "Score optimization means stabilize Activity, Trust, Services, and money while limiting Friction and Exposure.",
            "Show Proposed Feature highlights only the selected application's map exhibit. Retarget Map replaces it from selected districts.",
            "End Week closes the filing window. Unresolved cases can expire, create pressure, or return as follow-up filings.",
            "Filed Reports and Scorecard live in the report tabs at the bottom of the desk.",
            "End Game closes this dashboard and leaves the geodatabase ready to resume on the next launch.",
        )
        for line in lines:
            y = _text_bottom(c, body_x0, y, line, self._font(10), Palette.INK, width=body_x1 - body_x0) + 12
        bw = 150
        self._draw_session_button(c, body_x0, y1 - 56, body_x0 + bw, y1 - 22, "New Game", Palette.BLUE, self.callbacks.new_game)
        self._draw_session_button(c, body_x0 + bw + 12, y1 - 56, body_x0 + 2 * bw + 12, y1 - 22, "Help", Palette.MUTED, self.callbacks.show_help)

    def _add_target(self, kind, ident, bbox, callback):
        """Record a clickable canvas rectangle for later event dispatch."""

        self._click_targets.append((kind, ident, bbox, callback))

    def _font(self, size, weight="normal"):
        """Return the Segoe UI font tuple used by the desk canvas."""

        return ("Segoe UI", size, weight)

    def _ensure_lookups(self):
        """Rebuild the per-model lookup maps only when the model object changed.

        The label->ledger-row and action_id->lane maps are pure functions of the
        current model, so they are cached by model identity and reused across
        hover/deadline redraws (which keep the same model) instead of rebuilt by
        each draw method every frame.
        """

        if self._lookup_model is self.model:
            return
        model = self.model
        self._ledger_by_label = {row.label: row for row in model.ledger_rows}
        self._lane_by_action = {lane.action_id: lane for lane in model.action_lanes}
        self._lookup_model = model

    def _fit_px(self, text, size, weight, max_px):
        """Truncate text with an ellipsis so it renders within ``max_px`` pixels.

        Memoized on ``(text, size, weight, max_px)``: the fit is a pure function of
        its args (runtime font metrics are fixed), so the hover/redraw path reuses
        results instead of re-running the binary search every frame. The cache is
        cleared on model swap (`render`) to bound memory to one frame's strings.
        """

        text = " ".join(str(text or "").split())
        key = (text, size, weight, max_px)
        cached = self._fit_cache.get(key)
        if cached is not None:
            return cached
        result = self._fit_px_compute(text, size, weight, max_px)
        self._fit_cache[key] = result
        return result

    def _fit_px_compute(self, text, size, weight, max_px):
        """Run the (uncached) text-fit for already-normalized ``text``."""

        measure = self._px_measurer(size, weight)
        if measure is None:
            return _clip(text, max(4, int(max_px // (size * 0.62))))
        if measure(text) <= max_px:
            return text
        # Binary-search the largest prefix length whose text+"..." still fits.
        # Invariant: lo = a known-fitting length, hi = an upper bound; the
        # `mid = (lo+hi+1)//2` rounding-up biases toward lo so the loop can't
        # stall when hi == lo+1. Measuring per-candidate (not estimating) keeps
        # it exact across proportional fonts.
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
    bucket_h = 56
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
        c.create_text(bx0 + 12, by0 + 19, text="\n".join(value_lines), anchor="nw", fill=Palette.INK, font=font_factory(8, "bold"))
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
    if value in ("week", "filed", "scorecard"):
        return Palette.BLUE if value != "scorecard" else Palette.GOLD
    return Palette.MUTED


def _risk_color(exposure):
    """Map inspection exposure bands to a palette color."""

    value = (exposure or "").lower()
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
