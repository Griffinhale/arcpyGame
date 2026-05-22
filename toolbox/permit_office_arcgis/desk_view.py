"""Custom Tkinter desk surface for the Permit Office dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import shorten, wrap
from typing import Callable

from .rules_loader import rules


ACTIVE_STATUSES = ("open", "inspected", "active", "carried")


@dataclass(frozen=True)
class DeskCallbacks:
    """UI actions exposed by the dashboard controller."""

    toggle_exhibit: Callable[[], None]
    update_from_map: Callable[[], None]
    inspect: Callable[[], None]
    approve: Callable[[], None]
    approve_mitigated: Callable[[], None]
    deny: Callable[[], None]
    advance_turn: Callable[[], None]
    close: Callable[[], None]


@dataclass(frozen=True)
class DocketRow:
    """One visible in-tray case row."""

    item_id: str
    title: str
    geometry_type: str
    status: str
    selected: bool = False
    priority: int = 0
    due_turn: int = 0


@dataclass(frozen=True)
class CaseField:
    """A labeled line in the permit packet."""

    label: str
    value: str


@dataclass(frozen=True)
class ImpactBucket:
    """One compact permit-impact summary bucket."""

    label: str
    value: str
    tone: str = "neutral"


@dataclass(frozen=True)
class CaseSummary:
    """Structured permit-packet content for the selected case."""

    title: str = "No Active Case"
    item_id: str = ""
    status: str = ""
    category: str = ""
    fields: tuple[CaseField, ...] = ()
    districts: str = "(seeded exhibit; use Update From Map to revise)"
    preview: str = "Select a docket file from the in tray."
    inspection: str = "Inspection addendum not filed."
    action_note: str = ""
    risk_band: str = "unknown"
    impact_buckets: tuple[ImpactBucket, ...] = ()


@dataclass(frozen=True)
class LedgerRow:
    """A compact audit ledger line."""

    label: str
    value: str
    tone: str = "neutral"
    meter: int | None = None


@dataclass(frozen=True)
class DeskViewModel:
    """Everything the desk view needs to draw one frame."""

    docket_rows: tuple[DocketRow, ...] = ()
    selected_item_id: str = ""
    case: CaseSummary = field(default_factory=CaseSummary)
    ledger_rows: tuple[LedgerRow, ...] = ()
    status_text: str = ""
    exhibit_visible: bool = False


def build_desk_model(
    state,
    districts,
    items,
    selected_item_id="",
    status_text="",
    proposal_visible_by_item=None,
) -> DeskViewModel:
    """Format gameplay state into a presentation-only desk model."""

    proposal_visible_by_item = proposal_visible_by_item or {}
    active_items = [item for item in items if item.status in ACTIVE_STATUSES]
    selected = _resolve_selected_item(active_items, selected_item_id)
    selected_id = selected.item_id if selected else ""
    docket_rows = tuple(
        DocketRow(
            item_id=item.item_id,
            title=item.title,
            geometry_type=item.geometry_type,
            status=item.status,
            selected=item.item_id == selected_id,
            priority=item.priority,
            due_turn=item.due_turn,
        )
        for item in active_items
    )
    case = _case_summary(state, districts, selected)
    ledger_rows = _ledger_rows(state, districts)
    status = status_text or "No filed report yet. Select a docket row; use Update From Map only when changing targets."
    exhibit_visible = bool(proposal_visible_by_item.get(selected_id))
    return DeskViewModel(docket_rows, selected_id, case, ledger_rows, status, exhibit_visible)


def open_filed_report(title, report, affected, state):
    """Show a styled receipt after a dashboard action resolves."""

    try:
        import tkinter as tk
    except Exception:
        return

    root = tk.Toplevel()
    root.title("Filed Report")
    root.resizable(False, False)
    root.configure(bg=Palette.DESK)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    width = 820
    height = 620
    canvas = tk.Canvas(root, width=width, height=height, bg=Palette.DESK, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    _draw_receipt_canvas(canvas, width, height, title, report, affected, state)

    close = tk.Button(
        root,
        text="File Receipt",
        command=root.destroy,
        bg=Palette.INK,
        fg=Palette.PAPER,
        activebackground=Palette.BLUE,
        activeforeground=Palette.PAPER,
        relief="flat",
        padx=18,
        pady=7,
        font=("Segoe UI", 9, "bold"),
    )
    canvas.create_window(width - 94, height - 36, window=close)
    root.grab_set()
    root.wait_window()


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
    LEDGER = "#dce7d3"
    LEDGER_LINE = "#a7b699"
    WHITE = "#fbf7eb"


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

        self.canvas = tk.Canvas(root, bg=Palette.DESK, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)

    def render(self, model: DeskViewModel):
        """Store and draw the latest view model."""

        self.model = model
        width = max(self.canvas.winfo_width(), 1180)
        height = max(self.canvas.winfo_height(), 720)
        self._draw(width, height)

    def selected_item_id(self) -> str:
        """Return the currently rendered selected item id."""

        return self.model.selected_item_id

    def _on_configure(self, event):
        """Redraw the canvas when the window size changes."""

        size = (event.width, event.height)
        if size != self._last_size:
            self._last_size = size
            self._draw(max(event.width, 1180), max(event.height, 720))

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
            width = max(self.canvas.winfo_width(), 1180)
            height = max(self.canvas.winfo_height(), 720)
            self._draw(width, height)

    def _on_leave(self, _event):
        """Clear hover state when the pointer leaves the canvas."""

        if self._hover_key:
            self._hover_key = ""
            self.canvas.configure(cursor="")
            width = max(self.canvas.winfo_width(), 1180)
            height = max(self.canvas.winfo_height(), 720)
            self._draw(width, height)

    def _draw(self, width, height):
        """Draw all desk regions for the current view model."""

        c = self.canvas
        c.delete("all")
        self._click_targets = []
        self._draw_background(c, width, height)

        # The desk is arranged as three top panels plus a bottom stamp tray so
        # resizing keeps actions visible while preserving a readable case file.
        margin = 18
        gap = 14
        stamp_h = 146
        top_h = max(450, height - stamp_h - margin * 3)
        left_w = 340
        right_w = 285
        center_w = max(340, width - left_w - right_w - gap * 2 - margin * 2)
        left = (margin, margin, margin + left_w, margin + top_h)
        center = (left[2] + gap, margin, left[2] + gap + center_w, margin + top_h)
        right = (center[2] + gap, margin, width - margin, margin + top_h)
        tray = (margin, margin + top_h + gap, width - margin, height - margin)

        self._draw_in_tray(c, left)
        self._draw_case_file(c, center)
        self._draw_ledger(c, right)
        self._draw_stamp_tray(c, tray)

    def _draw_background(self, c, width, height):
        """Paint the desk surface and non-interactive paper props."""

        c.create_rectangle(0, 0, width, height, fill=Palette.DESK, outline="")
        c.create_rectangle(0, 0, width, 8, fill=Palette.DESK_DARK, outline="")
        c.create_line(24, 58, width - 24, 58, fill="#6d8680", width=1)
        for idx, (x, y, fill) in enumerate(((62, 42, Palette.NOTE), (width - 190, 46, Palette.NOTE_BLUE), (width - 255, height - 86, Palette.FOLDER))):
            c.create_rectangle(x + 4, y + 5, x + 110, y + 58, fill="#334744", outline="")
            c.create_rectangle(x, y, x + 106, y + 54, fill=fill, outline="#b8aa7e")
            c.create_line(x + 10, y + 17, x + 94, y + 17, fill="#a99b73")
            c.create_line(x + 10, y + 29, x + 88, y + 29, fill="#a99b73")
            if idx == 1:
                c.create_text(x + 10, y + 40, text="MAP EXHIBIT", anchor="w", fill=Palette.BLUE, font=self._font(7, "bold"))
        c.create_line(width - 70, 20, width - 40, 20, fill="#b8c9c2", width=3)
        c.create_arc(width - 72, 17, width - 56, 33, start=90, extent=220, outline="#b8c9c2", width=2)

    def _draw_in_tray(self, c, box):
        """Draw docket rows and register their selection hit targets."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 5, y0 + 6, x1 + 5, y1 + 6)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.FOLDER, outline="#9a854b", width=2)
        c.create_rectangle(x0 + 14, y0 - 1, x0 + 116, y0 + 24, fill=Palette.FOLDER, outline="#9a854b", width=2)
        c.create_text(x0 + 18, y0 + 34, text="IN TRAY", anchor="w", fill=Palette.INK, font=self._font(15, "bold"))
        c.create_text(x1 - 16, y0 + 36, text=f"{len(self.model.docket_rows)} OPEN", anchor="e", fill=Palette.MUTED, font=self._font(8, "bold"))

        if not self.model.docket_rows:
            c.create_text(
                x0 + 18,
                y0 + 76,
                text="No active case rows. End the filing day or generate a docket.",
                anchor="nw",
                width=x1 - x0 - 36,
                fill=Palette.MUTED,
                font=self._font(10),
            )
            return

        row_y = y0 + 72
        row_h = min(132, max(116, (y1 - row_y - 18) // max(1, len(self.model.docket_rows))))
        for idx, row in enumerate(self.model.docket_rows):
            # Row state controls the paper lift, color, and click target so the
            # selected case reads as the current physical folder.
            yy = row_y + idx * (row_h - 4)
            selected = row.selected
            hover = self._hover_key == f"docket:{row.item_id}"
            lift = -4 if selected else 0
            fill = Palette.WHITE if selected else "#eadfbc"
            outline = Palette.BLUE if selected else "#aa9864"
            if hover and not selected:
                fill = "#f2e8c8"
            c.create_rectangle(x0 + 18, yy + 7, x1 - 12, yy + row_h + 7, fill="#806f42", outline="")
            c.create_rectangle(x0 + 12, yy + lift, x1 - 18, yy + row_h + lift, fill=fill, outline=outline, width=2 if selected else 1)
            badge_x0 = x1 - 84
            c.create_rectangle(badge_x0, yy + 10 + lift, x1 - 26, yy + 34 + lift, fill=_status_color(row.status), outline="")
            c.create_text((badge_x0 + x1 - 26) // 2, yy + 22 + lift, text=row.status.upper(), anchor="center", fill=Palette.PAPER, font=self._font(7, "bold"))
            title_w = max(120, badge_x0 - x0 - 36)
            title_lines = _fit_lines(row.title, max(18, title_w // 7), 2)
            c.create_text(x0 + 24, yy + 16 + lift, text="\n".join(title_lines), anchor="nw", width=title_w, fill=Palette.INK, font=self._font(10, "bold"))
            c.create_text(x0 + 24, yy + 58 + lift, text=f"{row.geometry_type}  |  {row.item_id}", anchor="w", fill=Palette.MUTED, font=self._font(8))
            flags = []
            if row.priority:
                flags.append(f"priority {row.priority}")
            if row.due_turn:
                flags.append(f"due {row.due_turn}")
            c.create_text(x0 + 24, yy + 80 + lift, text=" / ".join(flags) or "case file pending", anchor="w", fill=Palette.GOLD, font=self._font(8, "bold"))
            if flags:
                c.create_text(x0 + 24, yy + 100 + lift, text="case file pending", anchor="w", fill=Palette.MUTED, font=self._font(7, "bold"))
            bbox = (x0 + 12, yy + lift, x1 - 18, yy + row_h + lift)
            self._add_target("docket", row.item_id, bbox, lambda item_id=row.item_id: self.on_select_item(item_id))

    def _draw_case_file(self, c, box):
        """Draw selected case details as the center packet."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 8, y0 + 10, x1 + 8, y1 + 10)
        c.create_rectangle(x0 + 14, y0 + 8, x1 - 8, y1 - 6, fill="#e7dcc3", outline="#b8aa8d")
        c.create_rectangle(x0 + 6, y0 + 2, x1 - 14, y1 - 12, fill="#eee4c9", outline="#b8aa8d")
        c.create_rectangle(x0, y0, x1 - 22, y1 - 20, fill=Palette.PAPER, outline="#978b75", width=2)
        c.create_polygon(x1 - 52, y0, x1 - 22, y0, x1 - 22, y0 + 30, fill="#dfd3b7", outline="#978b75")

        case = self.model.case
        c.create_text(x0 + 24, y0 + 24, text="CASE FILE", anchor="w", fill=Palette.BLUE, font=self._font(10, "bold"))
        c.create_text(x1 - 52, y0 + 24, text=_clip(case.status.upper(), 16), anchor="e", fill=_status_color(case.status), font=self._font(10, "bold"))
        c.create_text(x0 + 24, y0 + 54, text=_clip(case.title, 62), anchor="w", fill=Palette.INK, font=self._font(17, "bold"))
        c.create_text(x0 + 24, y0 + 86, text=case.item_id or "No case id", anchor="w", fill=Palette.MUTED, font=self._font(9))
        c.create_rectangle(x1 - 128, y0 + 56, x1 - 42, y0 + 88, outline=Palette.RED, width=2)
        c.create_text(x1 - 85, y0 + 72, text="RECEIVED", anchor="center", fill=Palette.RED, font=self._font(9, "bold"))

        content_x = x0 + 24
        content_w = max(240, x1 - x0 - 70)
        y = y0 + 116
        # Header fields stay compact; impact buckets carry the decision math so
        # the case packet does not become a wall of permit prose.
        for field in case.fields[:4]:
            c.create_text(content_x, y, text=field.label.upper(), anchor="nw", fill=Palette.BLUE, font=self._font(6, "bold"))
            c.create_text(content_x + 108, y, text=_clip(field.value, 56), anchor="nw", fill=Palette.INK, font=self._font(8), width=content_w - 108)
            y += 23

        y += 6
        paper_bottom = y1 - 42
        _draw_ruled_block(c, content_x, y, content_x + content_w, y + 44, "SELECTED DISTRICTS", case.districts, Palette.BLUE, self._font)
        y += 56
        y += _draw_impact_buckets(c, content_x, y, content_w, case.impact_buckets, self._font) + 10
        inspection_h = max(46, min(74, paper_bottom - y))
        _draw_ruled_block(c, content_x, y, content_x + content_w, y + inspection_h, "INSPECTION ADDENDUM", _clip(case.inspection, 190), Palette.RED, self._font)

        c.create_line(x0 + 10, y1 - 24, x1 - 34, y1 - 24, fill="#d1c4a8", dash=(3, 5))
        c.create_text(x1 - 42, y1 - 43, text=f"RISK: {case.risk_band.upper()}", anchor="e", fill=_risk_color(case.risk_band), font=self._font(9, "bold"))

    def _draw_ledger(self, c, box):
        """Draw city metrics, heat, population, and incident ledger rows."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 5, y0 + 8, x1 + 5, y1 + 8)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.LEDGER, outline="#87987b", width=2)
        c.create_rectangle(x0, y0, x1, y0 + 54, fill="#cad8c0", outline="#87987b", width=0)
        c.create_text(x0 + 18, y0 + 18, text="AUDIT LEDGER", anchor="w", fill=Palette.INK, font=self._font(13, "bold"))
        c.create_text(x0 + 18, y0 + 38, text="CITY", anchor="w", fill=Palette.GREEN, font=self._font(8, "bold"))
        c.create_line(x0 + 12, y0 + 55, x1 - 12, y0 + 55, fill=Palette.LEDGER_LINE)

        y = y0 + 68
        label_x = x0 + 18
        meter_x0 = x0 + 106
        meter_x1 = x1 - 86
        value_x = x1 - 18
        for idx, row in enumerate(self.model.ledger_rows):
            long_value = _ledger_wraps(row)
            row_h = 48 if long_value else 34
            yy = y
            fill = "#d5e1ca" if idx % 2 else Palette.LEDGER
            c.create_rectangle(x0 + 10, yy - 5, x1 - 10, yy + row_h - 7, fill=fill, outline="")
            c.create_text(label_x, yy, text=row.label.upper(), anchor="nw", width=78, fill=Palette.MUTED, font=self._font(7, "bold"))
            if long_value:
                lines = _fit_lines(row.value, max(20, (x1 - x0 - 38) // 7), 2)
                c.create_text(label_x, yy + 16, text="\n".join(lines), anchor="nw", width=x1 - x0 - 36, fill=_tone_color(row.tone), font=self._font(8, "bold"))
            else:
                c.create_text(value_x, yy, text=_clip(row.value, 16), anchor="ne", fill=_tone_color(row.tone), font=self._font(9, "bold"))
            if row.meter is not None and not long_value:
                meter_y = yy + 18
                c.create_rectangle(meter_x0, meter_y, meter_x1, meter_y + 5, fill="#b8c9ad", outline="")
                c.create_rectangle(meter_x0, meter_y, meter_x0 + int((meter_x1 - meter_x0) * max(0, min(100, row.meter)) / 100), meter_y + 5, fill=_tone_color(row.tone), outline="")
            y += row_h

        c.create_text(x0 + 18, y1 - 42, text="Filed marks", anchor="w", fill=Palette.MUTED, font=self._font(7, "bold"))
        for idx, color in enumerate((Palette.BLUE, Palette.GREEN, Palette.RED)):
            c.create_rectangle(x0 + 18 + idx * 48, y1 - 28, x0 + 52 + idx * 48, y1 - 18, fill=color, outline="")
            c.create_line(x0 + 18 + idx * 48, y1 - 16, x0 + 52 + idx * 48, y1 - 16, fill=color, width=2)

    def _draw_stamp_tray(self, c, box):
        """Draw action buttons, status text, and the close control."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 5, y0 + 6, x1 + 5, y1 + 6)
        c.create_rectangle(x0, y0, x1, y1, fill="#d0c3a6", outline="#8e7f63", width=2)
        c.create_rectangle(x0 + 10, y0 + 10, x1 - 10, y1 - 10, fill="#bda985", outline="#8e7f63")
        c.create_text(x0 + 22, y0 + 20, text="STAMP TRAY", anchor="w", fill=Palette.INK, font=self._font(11, "bold"))
        c.create_text(x0 + 22, y0 + 48, text="FILED REPORT", anchor="w", fill=Palette.BLUE, font=self._font(7, "bold"))
        tray_w = x1 - x0
        button_area_x0 = x0 + max(250, int(tray_w * 0.31))
        status_w = max(210, button_area_x0 - x0 - 42)
        c.create_text(x0 + 22, y0 + 68, text=_clip(self.model.status_text, 170), anchor="nw", width=status_w, fill=Palette.INK, font=self._font(9))

        exhibit_label = "Hide Exhibit" if self.model.exhibit_visible else "Show Exhibit"
        actions = (
            (exhibit_label, Palette.BLUE, self.callbacks.toggle_exhibit),
            ("Update From Map", "#4f7875", self.callbacks.update_from_map),
            ("Inspect File", Palette.GOLD, self.callbacks.inspect),
            ("Issue Permit", Palette.GREEN, self.callbacks.approve),
            ("Issue With Conditions", "#527d65", self.callbacks.approve_mitigated),
            ("Deny", Palette.RED, self.callbacks.deny),
            ("End Filing Day", Palette.INK, self.callbacks.advance_turn),
        )
        button_gap = 8
        usable = x1 - 82 - button_area_x0
        button_w = max(72, min(132, (usable - button_gap * (len(actions) - 1)) // len(actions)))
        button_h = 60
        by = y0 + 42
        # Buttons are stamped onto the tray and registered as hit targets during
        # drawing because the canvas has no native widget-level buttons.
        for idx, (label, color, callback) in enumerate(actions):
            bx = button_area_x0 + idx * (button_w + button_gap)
            hover = self._hover_key == f"action:{label}"
            self._draw_stamp_button(c, bx, by, bx + button_w, by + button_h, label, color, hover, callback)

        close_box = (x1 - 70, y0 + 42, x1 - 22, y0 + 102)
        close_hover = self._hover_key == "action:Close"
        c.create_rectangle(*close_box, fill="#efe5ca" if close_hover else "#dfd1b1", outline=Palette.INK, width=1)
        c.create_text((close_box[0] + close_box[2]) // 2, close_box[1] + 21, text="X", anchor="center", fill=Palette.INK, font=self._font(15, "bold"))
        c.create_text((close_box[0] + close_box[2]) // 2, close_box[1] + 44, text="CLOSE", anchor="center", fill=Palette.MUTED, font=self._font(6, "bold"))
        self._add_target("action", "Close", close_box, self.callbacks.close)

    def _draw_stamp_button(self, c, x0, y0, x1, y1, label, color, hover, callback):
        """Draw one stamp-style action button and register its hit target."""

        c.create_rectangle(x0 + 3, y0 + 4, x1 + 3, y1 + 4, fill="#6f5d44", outline="")
        c.create_rectangle(x0, y0, x1, y1, fill="#f0e4c8" if hover else Palette.PAPER, outline=color, width=3)
        c.create_rectangle(x0 + 8, y0 + 8, x1 - 8, y1 - 8, outline=color, width=1)
        c.create_text((x0 + x1) // 2, y0 + 26, text=_clip(label.upper(), 28), anchor="center", width=max(56, x1 - x0 - 12), fill=color, font=self._font(7, "bold"), justify="center")
        c.create_line(x0 + 16, y1 - 14, x1 - 16, y1 - 14, fill=color, width=2)
        self._add_target("action", label, (x0, y0, x1, y1), callback)

    def _add_target(self, kind, ident, bbox, callback):
        """Record a clickable canvas rectangle for later event dispatch."""

        self._click_targets.append((kind, ident, bbox, callback))

    def _font(self, size, weight="normal"):
        """Return the Segoe UI font tuple used by the desk canvas."""

        return ("Segoe UI", size, weight)


def _resolve_selected_item(items, selected_item_id):
    """Return the requested active item or the first item as a fallback."""

    if selected_item_id:
        for item in items:
            if item.item_id == selected_item_id:
                return item
    return items[0] if items else None


def _case_summary(state, districts, item) -> CaseSummary:
    """Convert a docket item into the structured case packet model."""

    if not item:
        return CaseSummary()

    # Template, archetype, stakeholder, and district context are merged here so
    # the Canvas layer only has presentation-ready text to draw.
    template = rules.TEMPLATES[item.template_id]
    archetype = rules.feature_archetype_for_template(template)
    stakeholder = item.stakeholder or template.stakeholder
    target_rule = item.target_rule or template.target_rule
    heat = state.stakeholder_heat.get(stakeholder, 0)
    target_profiles = [districts[cid] for cid in item.target_cell_ids if cid in districts]
    population_hint = rules.target_population_hint(item, target_profiles)
    preview = item.preview_text or template.preview
    if population_hint:
        preview = f"{preview} {population_hint}"
    cost = f"{template.ap_cost} AP / ${template.money_cost}; conditions +${template.mitigation_cost}"
    fields = (
        CaseField("Contact", template.contact_name or "not assigned"),
        CaseField("Applicant", f"{_display(stakeholder)}; heat {heat}"),
        CaseField("Category", f"{_display(template.category)} / {item.geometry_type}"),
        CaseField("Feature", f"{archetype.label} ({_display(archetype.family)})"),
        CaseField("Service", _display(archetype.service_type or "none")),
        CaseField("Cost", cost),
        CaseField("Target Rule", target_rule or "No targeting rule filed."),
        CaseField("Failure Mode", template.failure_mode or "none filed"),
    )
    action_note = _action_note(template)
    districts_text = ", ".join(item.target_cell_ids) if item.target_cell_ids else "(seeded exhibit; use Update From Map to revise)"
    inspection = _inspection_summary(item)
    impact_buckets = _impact_buckets(state, districts, item, template)
    return CaseSummary(
        title=item.title,
        item_id=item.item_id,
        status=item.status,
        category=template.category,
        fields=fields,
        districts=districts_text,
        preview=preview,
        inspection=inspection,
        action_note=action_note,
        risk_band=item.risk_band or "unknown",
        impact_buckets=impact_buckets,
    )


def _impact_buckets(state, districts, item, template) -> tuple[ImpactBucket, ...]:
    """Build concise impact buckets for the selected case."""

    targets = [districts[cid] for cid in item.target_cell_ids if cid in districts]
    inspection = (item.case_json or {}).get("inspection") if isinstance(item.case_json, dict) else None
    total_money = template.money_cost + template.mitigation_cost
    cost_tone = "bad" if state.ap < template.ap_cost or state.money < template.money_cost else "watch" if state.money < total_money else "neutral"
    cost = f"{template.ap_cost} AP / ${template.money_cost}; conditions +${template.mitigation_cost}"
    city = _city_bucket_value(template)
    city_tone = _delta_tone(template.base_effects | template.spillover_effects)
    target = _target_bucket_value(item, targets)
    target_tone = "neutral" if targets else "watch"

    if inspection:
        people, people_tone = _inspected_people_bucket(template, targets)
        follow_up, follow_tone = _inspection_followup_bucket(inspection, item)
    else:
        people = _qualitative_people_bucket(template)
        people_tone = "neutral"
        follow_up = _qualitative_followup_bucket(template)
        follow_tone = "watch" if template.failure_mode else "neutral"

    return (
        ImpactBucket("Cost", cost, cost_tone),
        ImpactBucket("City", city, city_tone),
        ImpactBucket("Target", target, target_tone),
        ImpactBucket("People", people, people_tone),
        ImpactBucket("Follow-up", follow_up, follow_tone),
    )


def _city_bucket_value(template) -> str:
    """Format city and spillover effects as one compact bucket value."""

    base = _format_effects(template.base_effects)
    spill = _format_effects(template.spillover_effects)
    if spill and spill != "none":
        return f"target {base}; spill {spill}"
    return f"target {base}"


def _target_bucket_value(item, targets) -> str:
    """Format selected target context without long prose."""

    if not item.target_cell_ids:
        return "seeded target pending map update"
    types = sorted({profile.district_type for profile in targets if profile.district_type})
    type_text = "/".join(types[:2]) if types else "filed"
    return f"{len(item.target_cell_ids)} district(s); {type_text}"


def _qualitative_people_bucket(template) -> str:
    """Format pre-inspection people impact qualitatively."""

    supporters = _join_labels(template.supporter_groups[:2])
    objectors = _join_labels(template.concerned_groups[:2])
    if supporters != "none" and objectors != "none":
        return f"{supporters} support; {objectors} object"
    if supporters != "none":
        return f"{supporters} likely support"
    if objectors != "none":
        return f"{objectors} may object"
    return "public comment pending"


def _qualitative_followup_bucket(template) -> str:
    """Format pre-inspection follow-up qualitatively."""

    if template.failure_mode:
        return f"inspect for {template.failure_mode}"
    return "routine filing path"


def _inspected_people_bucket(template, targets) -> tuple[str, str]:
    """Format inspected supporter, objector, and grievance context."""

    supporter = _strongest_group(targets, template.supporter_groups)
    objector = _strongest_group(targets, template.concerned_groups)
    grievance_group, grievance_band = _top_grievance(targets)
    parts = []
    if supporter:
        parts.append(f"{_group_label(supporter)} support")
    if objector:
        parts.append(f"{_group_label(objector)} object")
    if grievance_band:
        parts.append(f"{_group_label(grievance_group)} {rules.GRIEVANCE_BAND_LABELS[grievance_band]}")
    tone = "bad" if grievance_band >= rules.DISSATISFACTION_INCIDENT_THRESHOLD else "watch" if grievance_band >= rules.DISSATISFACTION_AGGRIEVED_THRESHOLD or objector else "neutral"
    return "; ".join(parts) if parts else "population evidence filed", tone


def _inspection_followup_bucket(inspection, item) -> tuple[str, str]:
    """Format inspected risk, evidence, and violations."""

    evidence = inspection.get("evidence") or []
    violations = inspection.get("violations") or []
    risk = str(inspection.get("risk_band") or item.risk_band or "unknown").lower()
    value = f"{risk} risk; {len(evidence)} evidence; {len(violations)} violation(s)"
    return value, _risk_tone(risk)


def _format_effects(effects) -> str:
    """Format metric deltas for a compact bucket."""

    parts = [f"{metric[:4]} {amount:+d}" for metric, amount in sorted((effects or {}).items()) if amount]
    return ", ".join(parts[:3]) if parts else "none"


def _delta_tone(effects) -> str:
    """Return a tone for a metric delta map."""

    effects = effects or {}
    if effects.get("risk", 0) > 0 or effects.get("unrest", 0) > 1:
        return "bad"
    if effects.get("risk", 0) < 0 or effects.get("prosperity", 0) > 0 or effects.get("culture", 0) > 0:
        return "good"
    if any(value for value in effects.values()):
        return "watch"
    return "neutral"


def _risk_tone(risk) -> str:
    """Return the dashboard tone for an inspection risk band."""

    if risk == "high":
        return "bad"
    if risk == "medium":
        return "watch"
    if risk == "low":
        return "good"
    return "neutral"


def _strongest_group(profiles, groups) -> str:
    """Return the strongest configured group across target profiles."""

    scores = []
    for group in groups:
        score = sum(profile.population_mix.get(group, 0) for profile in profiles)
        if score > 0:
            scores.append((score, group))
    return sorted(scores, key=lambda row: (-row[0], row[1]))[0][1] if scores else ""


def _top_grievance(profiles) -> tuple[str, int]:
    """Return the highest dissatisfaction band across target profiles."""

    totals = {group: 0 for group in rules.CITIZEN_GROUPS}
    for profile in profiles:
        for group, band in (profile.dissatisfaction or {}).items():
            if group in totals:
                totals[group] += int(band or 0)
    return sorted(totals.items(), key=lambda row: (-row[1], row[0]))[0]


def _join_labels(groups) -> str:
    """Join group labels for a compact bucket value."""

    labels = [_group_label(group) for group in groups if group]
    if not labels:
        return "none"
    return "/".join(labels[:2])


def _group_label(group) -> str:
    """Return a display label for a citizen or stakeholder group id."""

    return rules.GROUP_LABELS.get(group, str(group).replace("_", " "))


def _ledger_rows(state, districts) -> tuple[LedgerRow, ...]:
    """Build the city ledger rows shown in the dashboard sidebar."""

    heat = rules.heat_summary(state)
    population = rules.population_city_summary(districts)
    incidents = rules.incident_summary(districts)
    return (
        LedgerRow("Turn", f"{state.turn}/{state.max_turns}", "neutral", _meter(state.turn, state.max_turns)),
        LedgerRow("AP", f"{state.ap}/{state.max_ap}", "good" if state.ap else "watch", _meter(state.ap, state.max_ap)),
        LedgerRow("Money", f"${state.money}", "good" if state.money >= 20 else "watch"),
        LedgerRow("Prosperity", str(state.prosperity), "good", state.prosperity),
        LedgerRow("Unrest", str(state.unrest), "bad" if state.unrest >= 50 else "watch", state.unrest),
        LedgerRow("Culture", str(state.culture), "good", state.culture),
        LedgerRow("Risk", str(state.risk), "bad" if state.risk >= 50 else "watch", state.risk),
        LedgerRow("Heat", heat, "bad" if heat != "none" else "neutral"),
        LedgerRow("Population", population, "neutral"),
        LedgerRow("Incidents", incidents, "bad" if incidents != "none" else "neutral"),
    )


def _inspection_summary(item) -> str:
    """Format inspection evidence and violations for the case packet."""

    inspection = (item.case_json or {}).get("inspection") if isinstance(item.case_json, dict) else None
    if not inspection:
        if item.inspected:
            return f"Inspection filed. Risk band: {item.risk_band or 'unknown'}."
        return "Inspection addendum not filed."
    evidence = inspection.get("evidence") or []
    violations = inspection.get("violations") or []
    severities = [record.get("severity", "watch") for record in evidence if isinstance(record, dict)]
    worst = "critical" if "critical" in severities else "warning" if "warning" in severities else "watch"
    notes = []
    for record in evidence[:2]:
        if isinstance(record, dict) and record.get("label"):
            notes.append(f"{record.get('label')}: {record.get('severity', 'watch')}")
    note_text = "; ".join(notes)
    if note_text:
        note_text = f" {note_text}."
    return f"Risk {inspection.get('risk_band', item.risk_band)}; {len(evidence)} evidence item(s), highest {worst}; {len(violations)} violation(s).{note_text}"


def _action_note(template) -> str:
    """Describe how the stamp actions map to this template type."""

    if template.is_incident:
        return "Issue=formal response; Conditions=service settlement; Deny=defer incident."
    if template.is_enforcement:
        return "Issue=enforce; Conditions=settle or retro-permit; Deny=defer."
    return "Issue=approve permit; Conditions=approve with mitigation; Deny=reject."


def _draw_receipt_canvas(c, width, height, title, report, affected, state):
    """Draw the filed-report receipt in a modal canvas."""

    report_lines = _fit_lines(report, 58, 6)
    affected_text = ", ".join(affected) if affected else "(none)"
    c.create_rectangle(0, 0, width, height, fill=Palette.DESK, outline="")
    _shadow_rect(c, 50, 30, width - 44, height - 28)
    c.create_rectangle(42, 22, width - 52, height - 38, fill=Palette.PAPER, outline="#9b8f76", width=2)
    c.create_rectangle(68, 48, width - 78, 86, outline=Palette.RED, width=3)
    c.create_text(width // 2, 67, text="FILED REPORT", anchor="center", fill=Palette.RED, font=("Segoe UI", 15, "bold"))
    c.create_text(72, 108, text=_clip(title, 76), anchor="nw", fill=Palette.INK, font=("Segoe UI", 13, "bold"))
    c.create_line(72, 137, width - 82, 137, fill="#c4b798", dash=(4, 4))
    c.create_text(72, 154, text="\n".join(report_lines), anchor="nw", width=width - 150, fill=Palette.INK, font=("Segoe UI", 10))
    affected_y = 170 + len(report_lines) * 18
    c.create_text(72, affected_y, text=f"Affected districts: {_clip(affected_text, 84)}", anchor="nw", width=width - 160, fill=Palette.BLUE, font=("Segoe UI", 9, "bold"))
    metrics = (
        f"AP {state.ap}/{state.max_ap} | ${state.money} | Prosperity {state.prosperity} | "
        f"Unrest {state.unrest} | Culture {state.culture} | Risk {state.risk} | Heat {rules.heat_summary(state)}"
    )
    c.create_text(72, affected_y + 46, text=_clip(metrics, 120), anchor="nw", width=width - 160, fill=Palette.MUTED, font=("Segoe UI", 9))
    c.create_line(72, height - 78, width - 190, height - 78, fill="#c4b798")
    c.create_text(72, height - 62, text="Clerk initials", anchor="nw", fill=Palette.MUTED, font=("Segoe UI", 7, "bold"))


def _draw_ruled_block(c, x0, y0, x1, y1, label, text, accent, font_factory):
    """Draw a labeled ruled-paper text block."""

    c.create_rectangle(x0, y0, x1, y1, fill="#fbf3dc", outline="#d4c7aa")
    c.create_rectangle(x0, y0, x1, y0 + 20, fill="#efe3c8", outline="#d4c7aa")
    c.create_text(x0 + 8, y0 + 5, text=label, anchor="nw", fill=accent, font=font_factory(7, "bold"))
    for yy in range(y0 + 38, y1 - 6, 18):
        c.create_line(x0 + 8, yy, x1 - 8, yy, fill="#e3d7bd")
    c.create_text(x0 + 10, y0 + 28, text=text, anchor="nw", width=max(80, x1 - x0 - 20), fill=Palette.INK, font=font_factory(9))


def _draw_impact_buckets(c, x, y, width, buckets, font_factory):
    """Draw compact impact buckets in a two-column grid."""

    if not buckets:
        return 0
    gap = 8
    bucket_h = 38
    col_w = max(118, (width - gap) // 2)
    for idx, bucket in enumerate(buckets):
        col = idx % 2
        row = idx // 2
        bx0 = x + col * (col_w + gap)
        by0 = y + row * (bucket_h + 7)
        bx1 = min(x + width, bx0 + col_w)
        by1 = by0 + bucket_h
        tone = _tone_color(bucket.tone)
        c.create_rectangle(bx0, by0, bx1, by1, fill="#f6edd6", outline="#d4c7aa")
        c.create_rectangle(bx0, by0, bx0 + 5, by1, fill=tone, outline="")
        c.create_text(bx0 + 11, by0 + 5, text=bucket.label.upper(), anchor="nw", fill=Palette.MUTED, font=font_factory(6, "bold"))
        c.create_text(bx0 + 11, by0 + 18, text=_clip(bucket.value, max(18, (bx1 - bx0 - 22) // 6)), anchor="nw", fill=Palette.INK, font=font_factory(8, "bold"), width=bx1 - bx0 - 18)
    rows = (len(buckets) + 1) // 2
    return rows * bucket_h + max(0, rows - 1) * 7


def _shadow_rect(c, x0, y0, x1, y1):
    """Draw a simple rectangular paper shadow."""

    c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER_SHADOW, outline="")


def _meter(value, maximum):
    """Convert a value and maximum into a 0-100 meter percentage."""

    try:
        if maximum <= 0:
            return 0
        return int(100 * value / maximum)
    except Exception:
        return 0


def _inside(x, y, bbox):
    """Return whether a point is inside a canvas bounding box."""

    x0, y0, x1, y1 = bbox
    return x0 <= x <= x1 and y0 <= y <= y1


def _display(value):
    """Convert an identifier into title-style display text."""

    text = str(value or "none").replace("_", " ")
    return text[:1].upper() + text[1:]


def _clip(value, width):
    """Shorten text to a single normalized line for canvas rendering."""

    return shorten(" ".join(str(value or "").split()), width=width, placeholder="...")


def _ledger_wraps(row: LedgerRow) -> bool:
    """Return whether a ledger value needs its own wrapped text lane."""

    return row.label.lower() in ("heat", "population", "incidents") and len(str(row.value or "")) > 18


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
