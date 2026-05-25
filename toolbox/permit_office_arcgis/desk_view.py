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

    width = 860
    height = 600
    canvas = tk.Canvas(root, width=width, height=height, bg=Palette.DESK, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    _draw_receipt_canvas(canvas, width, height, title, report, affected, state)

    close = tk.Button(
        root,
        text="FILE RECEIPT",
        command=root.destroy,
        bg=Palette.INK,
        fg=Palette.PAPER,
        activebackground=Palette.BLUE,
        activeforeground=Palette.PAPER,
        relief="flat",
        padx=22,
        pady=9,
        font=("Segoe UI", 9, "bold"),
    )
    canvas.create_window(width - 110, height - 38, window=close)
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
    TEAL = "#4f7875"
    CARD_SHADOW = "#3a5450"
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
        """Lay out top banner, rolodex stack, active card, ledger rail, and status panel."""

        c = self.canvas
        c.delete("all")
        self._click_targets = []
        self._draw_background(c, width, height)
        banner_h = 54
        self._draw_top_banner(c, width, banner_h)

        margin = 18
        gap = 14
        ledger_w = 230
        ledger_h = 158

        rail_x0 = width - margin - ledger_w
        rail_x1 = width - margin
        rail_y0 = banner_h + margin
        rail_y1 = height - margin
        self._draw_ledger_rail(c, (rail_x0, rail_y0, rail_x1, rail_y0 + ledger_h))
        self._draw_status_panel(c, (rail_x0, rail_y0 + ledger_h + 12, rail_x1, rail_y1))

        card_x0 = margin
        card_x1 = rail_x0 - gap
        card_y1 = height - margin
        card_h = min(580, max(360, height - banner_h - 2 * margin - 60))
        card_y0 = card_y1 - card_h
        self._draw_rolodex_stack(c, (card_x0, banner_h + margin, card_x1, card_y0 - 8))
        self._draw_active_card(c, (card_x0, card_y0, card_x1, card_y1))

    def _draw_background(self, c, width, height):
        """Paint the desk surface (banner draws its own dark band on top)."""

        c.create_rectangle(0, 0, width, height, fill=Palette.DESK, outline="")

    def _draw_top_banner(self, c, width, h):
        """Draw the headline-metrics banner across the desk lip."""

        c.create_rectangle(0, 0, width, h, fill=Palette.DESK_DARK, outline="")
        c.create_rectangle(0, h - 3, width, h, fill=Palette.CARD_SHADOW, outline="")
        c.create_text(22, h // 2, text="PERMIT OFFICE", anchor="w", fill=Palette.PAPER, font=self._font(13, "bold"))
        metrics = {row.label: row for row in self.model.ledger_rows}
        headlines = (("Turn", "DAY"), ("AP", "AP"), ("Money", "$"), ("Prosperity", "PROS"), ("Unrest", "UNREST"), ("Culture", "CULT"), ("Risk", "RISK"), ("Heat", "HEAT"))
        x_start = 280
        right_pad = 30
        spacing = max(78, (width - x_start - right_pad) // len(headlines))
        x = x_start
        for key, display in headlines:
            row = metrics.get(key)
            if row is None:
                continue
            c.create_text(x, h // 2 - 9, text=display, anchor="w", fill=Palette.LEDGER_LINE, font=self._font(7, "bold"))
            c.create_text(x, h // 2 + 8, text=_clip(row.value, 12), anchor="w", fill=Palette.PAPER, font=self._font(11, "bold"))
            x += spacing

    def _draw_rolodex_stack(self, c, box):
        """Draw the horizontal edge-tab stack of queued (non-active) docket items."""

        x0, y0, x1, y1 = box
        active_id = self.model.selected_item_id
        queue = [row for row in self.model.docket_rows if row.item_id != active_id]
        total_open = len(self.model.docket_rows)

        c.create_text(x0 + 4, y0 + 4, text="ROLODEX", anchor="nw", fill=Palette.MUTED, font=self._font(8, "bold"))
        c.create_text(x0 + 76, y0 + 4, text=f"{total_open} OPEN", anchor="nw", fill=Palette.MUTED, font=self._font(7))

        if not queue:
            c.create_text(x0 + 4, y0 + 22, text="No queued cases. End the filing day to draw fresh dockets.", anchor="nw", fill=Palette.MUTED, font=self._font(9))
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
        """Draw the foreground index card with packet content and chip strip."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 8, y0 + 10, x1 + 8, y1 + 10)

        case = self.model.case
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER, outline=Palette.LINE, width=2)

        # Title band uses the case status as its keyed color so the card reads
        # like a stamped index card the moment it's pulled forward.
        title_h = 56
        band_color = _status_color(case.status) if case.status else Palette.BLUE
        c.create_rectangle(x0, y0, x1, y0 + title_h, fill=band_color, outline="")
        pill_x0 = x0 + 16
        pill_w = 96
        pill_h = 22
        pill_y0 = y0 + (title_h - pill_h) // 2
        c.create_rectangle(pill_x0, pill_y0, pill_x0 + pill_w, pill_y0 + pill_h, fill=Palette.INK, outline="")
        c.create_text(pill_x0 + pill_w // 2, pill_y0 + pill_h // 2, text=_clip(case.status.upper() or "—", 12), anchor="center", fill=Palette.PAPER, font=self._font(8, "bold"))
        c.create_text(pill_x0 + pill_w + 14, y0 + title_h // 2, text=_clip(case.title, 56), anchor="w", fill=Palette.PAPER, font=self._font(15, "bold"))
        stamp_w = 104
        stamp_h = 28
        stamp_x1 = x1 - 16
        stamp_x0 = stamp_x1 - stamp_w
        stamp_y0 = y0 + (title_h - stamp_h) // 2
        c.create_rectangle(stamp_x0, stamp_y0, stamp_x1, stamp_y0 + stamp_h, outline=Palette.PAPER, width=2)
        c.create_text((stamp_x0 + stamp_x1) // 2, stamp_y0 + stamp_h // 2, text="RECEIVED", anchor="center", fill=Palette.PAPER, font=self._font(9, "bold"))

        body_x0 = x0 + 22
        body_x1 = x1 - 22
        chip_h = 56
        chip_strip_y0 = y1 - chip_h - 12
        y = y0 + title_h + 10
        c.create_text(body_x0, y, text=case.item_id or "No case id", anchor="nw", fill=Palette.MUTED, font=self._font(9))
        y += 18
        for fld in case.fields[:3]:
            c.create_text(body_x0, y, text=fld.label.upper(), anchor="nw", fill=Palette.BLUE, font=self._font(6, "bold"))
            c.create_text(body_x0 + 108, y, text=_clip(fld.value, 64), anchor="nw", fill=Palette.INK, font=self._font(9), width=body_x1 - body_x0 - 108)
            y += 22
        y += 4

        districts_h = 56
        _draw_ruled_block(c, body_x0, y, body_x1, y + districts_h, "SELECTED DISTRICTS", case.districts, Palette.BLUE, self._font)
        y += districts_h + 8
        y += _draw_impact_buckets(c, body_x0, y, body_x1 - body_x0, case.impact_buckets, self._font) + 8
        inspection_h = max(46, chip_strip_y0 - y - 22)
        _draw_ruled_block(c, body_x0, y, body_x1, y + inspection_h, "INSPECTION ADDENDUM", _clip(case.inspection, 220), Palette.RED, self._font)
        c.create_text(x1 - 22, chip_strip_y0 - 6, text=f"RISK: {case.risk_band.upper()}", anchor="se", fill=_risk_color(case.risk_band), font=self._font(9, "bold"))

        self._draw_chip_strip(c, x0, chip_strip_y0, x1, y1)

    def _draw_chip_strip(self, c, x0, y0, x1, y1):
        """Lay out the 8 response chips along the card's lower edge."""

        exhibit_label = "Hide Exhibit" if self.model.exhibit_visible else "Show Exhibit"
        actions = (
            (exhibit_label, Palette.BLUE, self.callbacks.toggle_exhibit),
            ("Update Map", Palette.TEAL, self.callbacks.update_from_map),
            ("Inspect File", Palette.GOLD, self.callbacks.inspect),
            ("Issue Permit", Palette.GREEN, self.callbacks.approve),
            ("Conditions", "#527d65", self.callbacks.approve_mitigated),
            ("Deny", Palette.RED, self.callbacks.deny),
            ("End Day", Palette.INK, self.callbacks.advance_turn),
        )
        gap = 8
        inner_x0 = x0 + 22
        inner_x1 = x1 - 22
        chip_w = max(72, (inner_x1 - inner_x0 - gap * (len(actions) - 1)) // len(actions))
        chip_h = 44
        chip_y0 = y0 + (y1 - y0 - chip_h) // 2
        for idx, (label, color, callback) in enumerate(actions):
            cx0 = inner_x0 + idx * (chip_w + gap)
            cx1 = cx0 + chip_w
            hover = self._hover_key == f"action:{label}"
            self._draw_card_chip(c, cx0, chip_y0, cx1, chip_y0 + chip_h, label, color, hover, callback)

    def _draw_card_chip(self, c, x0, y0, x1, y1, label, color, hover, callback):
        """Draw one action chip on the active card and register its hit target."""

        fill = Palette.WHITE if hover else Palette.PAPER
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=color, width=2)
        text = _clip(label.upper(), max(8, (x1 - x0) // 6))
        c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=text, anchor="center", fill=color, font=self._font(8, "bold"), justify="center", width=x1 - x0 - 8)
        self._add_target("action", label, (x0, y0, x1, y1), callback)

    def _draw_ledger_rail(self, c, box):
        """Draw the right-rail city health panel (rows not surfaced in the banner)."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 4, y0 + 6, x1 + 4, y1 + 6)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.LEDGER, outline="#87987b", width=2)
        c.create_rectangle(x0, y0, x1, y0 + 32, fill="#cad8c0", outline="#87987b")
        c.create_text(x0 + 14, y0 + 16, text="CITY HEALTH", anchor="w", fill=Palette.INK, font=self._font(10, "bold"))
        c.create_line(x0 + 10, y0 + 33, x1 - 10, y0 + 33, fill=Palette.LEDGER_LINE)

        banner_labels = {"Turn", "AP", "Money", "Prosperity", "Unrest", "Culture", "Risk", "Heat"}
        rows = [r for r in self.model.ledger_rows if r.label not in banner_labels]
        y = y0 + 42
        label_x = x0 + 12
        value_x = x1 - 12
        for idx, row in enumerate(rows):
            long_value = _ledger_wraps(row)
            row_h = 36 if long_value else 26
            if y + row_h > y1 - 28:
                break
            fill = "#d5e1ca" if idx % 2 else Palette.LEDGER
            c.create_rectangle(x0 + 8, y - 4, x1 - 8, y + row_h - 6, fill=fill, outline="")
            c.create_text(label_x, y, text=row.label.upper(), anchor="nw", width=110, fill=Palette.MUTED, font=self._font(7, "bold"))
            if long_value:
                lines = _fit_lines(row.value, max(16, (x1 - x0 - 28) // 7), 2)
                c.create_text(label_x, y + 14, text="\n".join(lines), anchor="nw", fill=_tone_color(row.tone), font=self._font(8, "bold"))
            else:
                c.create_text(value_x, y, text=_clip(row.value, 14), anchor="ne", fill=_tone_color(row.tone), font=self._font(9, "bold"))
            y += row_h
        c.create_text(x0 + 12, y1 - 22, text="Filed marks", anchor="w", fill=Palette.MUTED, font=self._font(7, "bold"))
        for idx, color in enumerate((Palette.BLUE, Palette.GREEN, Palette.RED)):
            sx = x0 + 86 + idx * 32
            c.create_rectangle(sx, y1 - 26, sx + 22, y1 - 14, fill=color, outline="")

    def _draw_status_panel(self, c, box):
        """Draw the filed-report status panel and exhibit pill under the ledger."""

        x0, y0, x1, y1 = box
        _shadow_rect(c, x0 + 4, y0 + 6, x1 + 4, y1 + 6)
        c.create_rectangle(x0, y0, x1, y1, fill=Palette.PAPER_ALT, outline=Palette.LINE, width=2)
        c.create_text(x0 + 14, y0 + 12, text="FILED REPORT", anchor="nw", fill=Palette.BLUE, font=self._font(8, "bold"))
        lines = _fit_lines(self.model.status_text or "No filed report yet.", max(20, (x1 - x0 - 28) // 7), 4)
        c.create_text(x0 + 14, y0 + 30, text="\n".join(lines), anchor="nw", fill=Palette.INK, font=self._font(9), width=x1 - x0 - 28)
        exhibit = self.model.exhibit_visible
        pill_label = "EXHIBIT ON" if exhibit else "EXHIBIT OFF"
        pill_color = Palette.GREEN if exhibit else Palette.MUTED
        pill_w = 96
        pill_h = 20
        pill_x0 = x0 + 14
        pill_y0 = y1 - 28
        c.create_rectangle(pill_x0, pill_y0, pill_x0 + pill_w, pill_y0 + pill_h, fill=Palette.PAPER, outline=pill_color, width=2)
        c.create_text(pill_x0 + pill_w // 2, pill_y0 + pill_h // 2, text=pill_label, anchor="center", fill=pill_color, font=self._font(7, "bold"))

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
        CaseField("Applicant", f"{_display(stakeholder)}; heat {heat}"),
        CaseField("Category", f"{_display(template.category)} / {item.geometry_type}"),
        CaseField("Feature", f"{archetype.label} ({_display(archetype.family)})"),
        CaseField("Contact", template.contact_name or "not assigned"),
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
    cost = _cost_bucket_value(template)
    city = _city_forecast_bucket(template, targets, mitigated=False)
    city_tone = _delta_tone(template.base_effects | template.spillover_effects)
    target = _target_bucket_value(item, targets)
    target_tone = "neutral" if targets else "watch"
    recurring = _recurring_bucket_value(template)
    recurring_tone = _recurring_tone(template)

    if inspection:
        risk, risk_tone = _inspection_followup_bucket(inspection, item)
    else:
        risk = _qualitative_followup_bucket(template)
        risk_tone = "watch" if template.failure_mode else "neutral"

    return (
        ImpactBucket("Cost", cost, cost_tone),
        ImpactBucket("City Effect", city, city_tone),
        ImpactBucket("Budget", recurring, recurring_tone),
        ImpactBucket("Risk", risk, risk_tone),
    )


def _cost_bucket_value(template) -> str:
    """Format direct decision costs for all stamp choices."""

    return f"Issue {template.ap_cost}AP/${template.money_cost}; conditions +${template.mitigation_cost}; deny 1AP"


def _city_forecast_bucket(template, targets, mitigated: bool) -> str:
    """Forecast likely immediate metric effects before a decision is filed."""

    if not targets:
        base = rules._mitigate(template.base_effects) if mitigated else template.base_effects
        spill = rules._mitigate(template.spillover_effects) if mitigated else template.spillover_effects
        base_text = _format_effects(base)
        spill_text = _format_effects(spill)
        if spill_text != "none":
            return f"target {base_text}; spill {spill_text}"
        return f"target {base_text}"

    archetype = rules.feature_archetype_for_template(template)
    total = {metric: 0 for metric in rules.CORE_METRICS}
    for profile in targets:
        delta = rules._district_adjusted_effects(template.base_effects, profile.district_type, template.category)
        delta = rules._land_use_adjusted_effects(delta, profile, archetype)
        rules._merge_delta(delta, rules._service_coverage_effect(archetype, profile, "target"))
        if mitigated:
            delta = rules._mitigate(delta)
        for metric in rules.CORE_METRICS:
            total[metric] = total.get(metric, 0) + delta.get(metric, 0)
    averaged = {metric: round(value / max(1, len(targets))) for metric, value in total.items()}
    return _format_effects(averaged)


def _recurring_bucket_value(template) -> str:
    """Format recurring feature revenue and upkeep forecast."""

    archetype = rules.feature_archetype_for_template(template)
    operating = rules.operating_rule_for_feature(archetype.archetype_id)
    revenue = operating.revenue_per_turn
    upkeep = operating.upkeep_per_turn
    net = revenue - upkeep
    if revenue or upkeep:
        return f"rev ${revenue}/turn, upkeep ${upkeep}/turn, net ${net:+d}"
    return "no recurring budget"


def _recurring_tone(template) -> str:
    """Return dashboard tone for recurring budget forecast."""

    archetype = rules.feature_archetype_for_template(template)
    operating = rules.operating_rule_for_feature(archetype.archetype_id)
    net = operating.revenue_per_turn - operating.upkeep_per_turn
    if net > 0:
        return "good"
    if net < 0:
        return "watch"
    return "neutral"


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
    warnings = sum(1 for record in evidence if isinstance(record, dict) and record.get("severity") in ("warning", "critical"))
    value = f"{risk} risk; {warnings}/{len(evidence)} flagged evidence; {len(violations)} violation(s)"
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
    """Draw the filed-report receipt as a stamped permit card."""

    accent = _receipt_accent(report)
    margin = 28
    c.create_rectangle(0, 0, width, height, fill=Palette.DESK, outline="")
    _shadow_rect(c, margin + 8, margin + 10, width - margin + 8, height - margin + 10)
    c.create_rectangle(margin, margin, width - margin, height - margin, fill=Palette.PAPER, outline=Palette.LINE, width=2)
    band_h = 56
    c.create_rectangle(margin, margin, width - margin, margin + band_h, fill=accent, outline="")
    c.create_text(margin + 22, margin + band_h // 2, text="FILED REPORT", anchor="w", fill=Palette.PAPER, font=("Segoe UI", 14, "bold"))
    stamp_x1 = width - margin - 22
    stamp_x0 = stamp_x1 - 104
    stamp_y0 = margin + (band_h - 30) // 2
    c.create_rectangle(stamp_x0, stamp_y0, stamp_x1, stamp_y0 + 30, outline=Palette.PAPER, width=2)
    c.create_text((stamp_x0 + stamp_x1) // 2, stamp_y0 + 15, text="FILED", anchor="center", fill=Palette.PAPER, font=("Segoe UI", 10, "bold"))
    body_x0 = margin + 24
    body_x1 = width - margin - 24
    y = margin + band_h + 20
    c.create_text(body_x0, y, text=_clip(title, 72), anchor="nw", fill=Palette.INK, font=("Segoe UI", 14, "bold"))
    y += 32
    c.create_line(body_x0, y, body_x1, y, fill="#c4b798", dash=(4, 4))
    y += 12
    # Pre-wrap and let Tk respect newlines (passing width= triggers a double-wrap that shifts the layout).
    rid = c.create_text(body_x0, y, text="\n".join(_fit_lines(report or "", 100, 14)), anchor="nw", fill=Palette.INK, font=("Segoe UI", 10))
    y = (c.bbox(rid) or (0, 0, 0, y + 16))[3] + 14
    affected_text = ", ".join(affected) if affected else "(none)"
    aid = c.create_text(body_x0, y, text="\n".join(_fit_lines(f"Affected districts: {affected_text}", 100, 3)), anchor="nw", fill=Palette.BLUE, font=("Segoe UI", 9, "bold"))
    y = (c.bbox(aid) or (0, 0, 0, y + 14))[3] + 6
    metric_y = height - margin - 58
    c.create_line(body_x0, metric_y - 10, body_x1, metric_y - 10, fill="#c4b798")
    items = (("AP", f"{state.ap}/{state.max_ap}"), ("$", str(state.money)), ("PROS", str(state.prosperity)), ("UNREST", str(state.unrest)), ("CULT", str(state.culture)), ("RISK", str(state.risk)), ("HEAT", str(rules.heat_summary(state))))
    mw = (body_x1 - body_x0 - 140) // len(items)
    mx = body_x0
    for label, value in items:
        c.create_text(mx, metric_y, text=label, anchor="nw", fill=Palette.MUTED, font=("Segoe UI", 7, "bold"))
        c.create_text(mx, metric_y + 12, text=_clip(value, 8), anchor="nw", fill=Palette.INK, font=("Segoe UI", 10, "bold"))
        mx += mw


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
    bucket_h = 46
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
        c.create_text(bx0 + 11, by0 + 18, text=_clip(bucket.value, max(24, (bx1 - bx0 - 22) // 6)), anchor="nw", fill=Palette.INK, font=font_factory(8, "bold"), width=bx1 - bx0 - 18)
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
