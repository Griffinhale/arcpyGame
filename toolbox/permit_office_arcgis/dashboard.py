"""Tkinter dashboard controller for ArcGIS-hosted Permit Office sessions."""

from __future__ import annotations

import traceback

import arcpy

from ._perf import perf_block, perf_session
from .geometry import (
    add_outputs_to_map,
    activate_proposal,
    case_proposal_visible,
    ensure_case_proposal,
    hide_case_proposal,
    insert_or_replace_proposal,
    mark_proposals,
    proposal_spillover,
    refresh_all,
    remove_outputs_from_map,
    select_case_context,
    selected_cell_ids,
    seed_city_features,
)
from .messages import _log, _warn
from .rules_loader import rules
from .schema import DISTRICTS, LINES, POINTS, ZONES, clear_game_rows
from .store import (
    action_log,
    command_finish,
    command_insert,
    create_district_board,
    generate_docket_rows,
    read_active_features,
    read_districts,
    read_docket,
    read_projects,
    read_state,
    write_active_features,
    write_district_updates,
    write_docket_item,
    write_projects,
    write_state,
)
from .desk_view import DeskCallbacks, PermitDeskView, build_desk_model, open_filed_report


def open_effect_report(title, report, affected, state):
    """Show a filed-report receipt after a dashboard action resolves."""

    open_filed_report(title, report, affected, state)


def prepare_dashboard_session(paths, seed, messages):
    """Repair resumable saved-game presentation before the GUI opens."""

    if has_saved_game(paths):
        add_outputs_to_map(paths, messages)
        if _row_count(paths["docket"]) == 0:
            generate_docket_rows(paths, seed, messages)
            refresh_all(paths, messages)
        _log(messages, "DASH", "resuming saved Permit Office game")
    else:
        _log(messages, "DASH", "no saved Permit Office game found; open dashboard start screen")
    return seed


def has_saved_game(paths):
    """Return whether the geodatabase contains enough rows to resume play."""

    return _row_count(paths["districts"]) > 0 and _row_count(paths["state"]) > 0


def _row_count(path):
    """Return an ArcGIS table row count, treating inaccessible paths as empty."""

    try:
        return int(arcpy.management.GetCount(path)[0])
    except Exception:
        return 0


class _StatusProxy:
    """Compatibility shim for the old StringVar-like controller calls."""

    def __init__(self, controller):
        """Attach the proxy to the dashboard controller's status field."""

        self.controller = controller

    def set(self, value):
        """Store status text in the controller for the next render."""

        self.controller.status_text = str(value or "")

    def get(self):
        """Return the controller's current status text."""

        return self.controller.status_text


class DashboardController:
    """Coordinate dashboard UI actions with ArcGIS persistence helpers."""

    def __init__(self, paths, district_layer, seed, messages):
        """Store ArcGIS handles used by dashboard callbacks."""

        self.paths = paths
        self.district_layer = district_layer
        self.seed = seed
        self.messages = messages

    def open(self):
        """Create the Tkinter window, wire callbacks, and enter the UI loop."""

        try:
            import tkinter as tk
        except Exception as exc:
            raise RuntimeError(f"tkinter is not available: {exc}")

        self.root = tk.Tk()
        self.root.title("Permit Office")
        self.root.geometry("1320x760")
        self.root.minsize(1180, 720)
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        self.selected_item_id = ""
        self.status_text = ""
        self.status_var = _StatusProxy(self)
        # The view owns drawing and hit targets; the controller owns actions
        # that mutate ArcGIS-backed game state.
        callbacks = DeskCallbacks(
            toggle_exhibit=self.toggle_exhibit,
            update_from_map=self.update_from_map,
            inspect=self.inspect,
            approve=lambda: self.apply_decision("approve", False),
            approve_mitigated=lambda: self.apply_decision("approve_mitigated", True),
            deny=self.deny,
            advance_turn=self.advance_turn,
            new_game=self.new_game,
            scorecard=self.show_scorecard,
            close=self.root.destroy,
        )
        self.view = PermitDeskView(self.root, callbacks, self.select_item)

        self.reload()
        self.root.mainloop()

    def select_item(self, item_id):
        """Select a docket item and redraw the dashboard model."""

        self.selected_item_id = item_id
        item = self.active_item()
        if item:
            try:
                select_case_context(self.paths, self.district_layer, item, self.seed, self.messages)
                self.status_text = f"Selected {item.title}; map context updated."
            except Exception as exc:
                self.status_text = f"Map selection failed: {exc}"
                _warn(self.messages, "DASH", traceback.format_exc().strip().splitlines()[-1])
        self.reload()

    def reload(self):
        """Read persisted game rows and render a fresh desk view model."""

        state = read_state(self.paths)
        districts = read_districts(self.paths)
        items = read_docket(self.paths)
        if not has_saved_game(self.paths) and not self.status_text:
            self.status_text = "No saved game found. Click New Game to create Permit Office layers and start play."
        proposal_visible_by_item = {}
        for item in items:
            try:
                proposal_visible_by_item[item.item_id] = case_proposal_visible(self.paths, item)
            except Exception:
                proposal_visible_by_item[item.item_id] = False
        model = build_desk_model(
            state,
            districts,
            items,
            self.selected_item_id,
            self.status_text,
            proposal_visible_by_item,
        )
        self.selected_item_id = model.selected_item_id
        self.view.render(model)

    def new_game(self):
        """Start a fresh game from the dashboard after player confirmation."""

        try:
            from tkinter import messagebox, simpledialog
        except Exception as exc:
            self.status_var.set(f"New game failed: tkinter dialogs unavailable: {exc}")
            self.reload()
            return
        if has_saved_game(self.paths):
            ok = messagebox.askyesno(
                "Start New Game",
                "Replace the current Permit Office game rows and map layers?",
                parent=self.root,
            )
            if not ok:
                return
        seed = simpledialog.askinteger(
            "New Game Seed",
            "Random seed",
            initialvalue=self.seed,
            minvalue=0,
            parent=self.root,
        )
        if seed is None:
            return
        self.start_new_game(int(seed))

    def start_new_game(self, seed):
        """Replace persisted game rows and reload the dashboard."""

        with perf_session("new_game", self.messages):
            try:
                clear_game_rows(self.paths)
                create_district_board(self.paths, seed, self.messages)
                seed_city_features(self.paths, seed, self.messages)
                write_state(self.paths, rules.CityState())
                generate_docket_rows(self.paths, seed, self.messages)
                remove_outputs_from_map(self.messages)
                add_outputs_to_map(self.paths, self.messages)
                refresh_all(self.paths, self.messages)
                self.seed = seed
                self.district_layer = DISTRICTS
                self.selected_item_id = ""
                self.status_var.set(f"New game started with seed {seed}.")
            except Exception as exc:
                self.status_var.set(f"New game failed: {exc}")
                _warn(self.messages, "NEW", traceback.format_exc().strip().splitlines()[-1])
            finally:
                self.reload()

    def show_scorecard(self):
        """Display the current audit scorecard from persisted game rows."""

        try:
            from tkinter import messagebox
        except Exception as exc:
            self.status_var.set(f"Scorecard failed: tkinter dialogs unavailable: {exc}")
            self.reload()
            return
        if not has_saved_game(self.paths):
            messagebox.showinfo("Scorecard", "No saved Permit Office game found.", parent=self.root)
            return
        try:
            state = read_state(self.paths)
            districts = read_districts(self.paths)
            active_features = read_active_features(self.paths)
            items = read_docket(self.paths)
            _grade, report = rules.scorecard(state, districts, active_features, items)
            summary = f"{report}\n\n{rules.population_city_summary(districts)}; incidents={rules.incident_summary(districts)}."
            messagebox.showinfo("Scorecard", summary, parent=self.root)
            self.status_var.set(report)
        except Exception as exc:
            self.status_var.set(f"Scorecard failed: {exc}")
        self.reload()

    def item_label(self, item):
        """Return a compact debugging label for a docket item."""

        return f"{item.item_id} | {item.geometry_type} | {item.status} | {item.title}"

    def active_item(self):
        """Return the selected docket item or first actionable fallback."""

        item_id = self.selected_item_id
        if not item_id and getattr(self, "view", None):
            item_id = self.view.selected_item_id()
        for item in read_docket(self.paths):
            if item.item_id == item_id:
                return item
        for item in read_docket(self.paths):
            if item.status in ("open", "inspected", "active", "carried"):
                return item
        return None

    def refresh_detail(self):
        """Refresh visible dashboard details from persisted state."""

        self.reload()

    def toggle_exhibit(self):
        """Hide or show the selected unresolved proposal exhibit."""

        item = self.active_item()
        if not item:
            return
        try:
            if case_proposal_visible(self.paths, item):
                changed = hide_case_proposal(self.paths, item.item_id)
                action = "Hid" if changed else "No exhibit found for"
                target_ids = item.target_cell_ids
            else:
                target_ids = ensure_case_proposal(self.paths, item, self.seed, self.messages)
                action = "Showed"
            refresh_all(self.paths, self.messages)
            suffix = f" for {', '.join(target_ids)}" if target_ids else ""
            self.status_var.set(f"{action} {item.title}{suffix}.")
            self.reload()
        except Exception as exc:
            self.status_var.set(f"Exhibit toggle failed: {exc}")
            _warn(self.messages, "DASH", traceback.format_exc().strip().splitlines()[-1])

    def update_from_map(self):
        """Replace the selected case's proposed exhibit from current map selection."""

        item = self.active_item()
        if not item:
            return
        try:
            selected = selected_cell_ids(self.district_layer)
            target_ids = insert_or_replace_proposal(self.paths, item, selected, self.messages)
            refresh_all(self.paths, self.messages)
            self.status_var.set(f"Updated {item.title} from map selection: {', '.join(target_ids)}.")
            self.reload()
        except Exception as exc:
            self.status_var.set(f"Update from map failed: {exc}")
            _warn(self.messages, "DASH", traceback.format_exc().strip().splitlines()[-1])

    def inspect(self):
        """Resolve an inspection command for the active docket item."""

        item = self.active_item()
        if not item:
            return
        command_id = command_insert(self.paths, "inspect", item.item_id, item.target_cell_ids)
        with perf_session("turn=inspect", self.messages):
            try:
                # Inspection reads the live state, lets pure rules attach evidence,
                # then persists both the changed docket item and the command log.
                state = read_state(self.paths)
                districts = read_districts(self.paths)
                active_features = read_active_features(self.paths)
                result = rules.resolve_decision(state, item, districts, "inspect", item.target_cell_ids, seed=self.seed, active_features=active_features)
                with perf_block("writes"):
                    write_state(self.paths, state)
                    write_docket_item(self.paths, item)
                    action_log(self.paths, state, result)
                    command_finish(self.paths, command_id, result.command_status, result.report)
                self.status_var.set(result.report)
                with perf_block("receipt"):
                    open_effect_report(item.title, result.report, result.affected_cell_ids, state)
            except Exception as exc:
                command_finish(self.paths, command_id, "error", error=str(exc))
                self.status_var.set(f"Inspect failed: {exc}")
        self.reload()

    def apply_decision(self, action, mitigated):
        """Approve or approve-with-mitigation for the active docket item."""

        item = self.active_item()
        if not item:
            return
        command_id = None
        with perf_session(f"turn={action}", self.messages):
            try:
                # Approvals need current map proposal context before pure rules can
                # resolve target effects, spillover, active features, and projects.
                target_ids = list(item.target_cell_ids or ())
                if not target_ids:
                    target_ids = selected_cell_ids(self.district_layer)
                with perf_block("ensure"):
                    target_ids = ensure_case_proposal(self.paths, item, self.seed, self.messages, target_ids or None)
                command_id = command_insert(self.paths, action, item.item_id, target_ids)
                with perf_block("spillover"):
                    spillover = [] if item.template_id == rules.MAINTENANCE_TEMPLATE_ID else proposal_spillover(self.paths, item)
                with perf_block("reads"):
                    state = read_state(self.paths)
                    districts = read_districts(self.paths)
                    active_features = read_active_features(self.paths)
                    projects = read_projects(self.paths)
                with perf_block("resolve"):
                    result = rules.resolve_decision(
                        state,
                        item,
                        districts,
                        action,
                        item.target_cell_ids,
                        spillover,
                        seed=self.seed,
                        mitigated=mitigated,
                        active_features=active_features,
                        projects=projects,
                    )
                if not result.ok:
                    command_finish(self.paths, command_id, "error", result.report, result.report)
                    self.status_var.set(result.report)
                    return
                if result.feature_updates:
                    with perf_block("write_features"):
                        write_active_features(self.paths, active_features)
                with perf_block("activate"):
                    activated = activate_proposal(self.paths, item, result.report)
                if not activated:
                    _warn(self.messages, "DASH", f"approved {item.item_id} but no proposed map feature was activated")
                self._finish_decision(command_id, item, state, districts, projects, result, _decision_layer_names(item))
            except Exception as exc:
                if command_id:
                    command_finish(self.paths, command_id, "error", error=str(exc))
                self.status_var.set(f"Approve failed: {exc}")
                _warn(self.messages, "DASH", traceback.format_exc().strip().splitlines()[-1])
            finally:
                with perf_block("reload"):
                    self.reload()

    def deny(self):
        """Deny the active docket item and persist resulting state changes."""

        item = self.active_item()
        if not item:
            return
        command_id = command_insert(self.paths, "deny", item.item_id, item.target_cell_ids)
        with perf_session("turn=deny", self.messages):
            try:
                # Denials use the same pure-rule resolver, but proposal features are
                # marked denied instead of activated on the map.
                with perf_block("reads"):
                    state = read_state(self.paths)
                    districts = read_districts(self.paths)
                    active_features = read_active_features(self.paths)
                    projects = read_projects(self.paths)
                with perf_block("resolve"):
                    result = rules.resolve_decision(state, item, districts, "deny", item.target_cell_ids, seed=self.seed, active_features=active_features, projects=projects)
                if not result.ok:
                    command_finish(self.paths, command_id, "error", result.report, result.report)
                    self.status_var.set(result.report)
                    return
                if result.feature_updates:
                    with perf_block("write_features"):
                        write_active_features(self.paths, active_features)
                proposal_status = item.status if item.status in ("denied", "deferred") else "denied"
                with perf_block("mark"):
                    mark_proposals(self.paths, item.item_id, proposal_status, result.report)
                self._finish_decision(command_id, item, state, districts, projects, result, _decision_layer_names(item))
            except Exception as exc:
                command_finish(self.paths, command_id, "error", error=str(exc))
                self.status_var.set(f"Deny failed: {exc}")
            finally:
                with perf_block("reload"):
                    self.reload()

    def _finish_decision(self, command_id, item, state, districts, projects, result, layer_names=None):
        """Persist a successful decision result and show its filed report."""

        filed_report = _filed_report_text(result)
        with perf_block("writes"):
            write_district_updates(self.paths, districts, result.report, result.affected_cell_ids)
            write_state(self.paths, state)
            write_projects(self.paths, projects)
            write_docket_item(self.paths, item)
            action_log(self.paths, state, result)
            command_finish(self.paths, command_id, result.command_status, filed_report)
        rebuild_output_layers(self.paths, self.messages, layer_names=layer_names)
        self.district_layer = DISTRICTS
        self.status_var.set(filed_report)
        with perf_block("receipt"):
            open_effect_report(item.title, filed_report, result.affected_cell_ids, state)

    def advance_turn(self):
        """Advance the saved game one turn and regenerate the docket."""

        command_id = command_insert(self.paths, "advance_turn", "", [])
        with perf_session("turn=advance", self.messages):
            try:
                # Turn advancement mutates open docket items, city systems, active
                # features, projects, and the next generated docket as one command.
                with perf_block("reads"):
                    state = read_state(self.paths)
                    items = read_docket(self.paths)
                    districts = read_districts(self.paths)
                    active_features = read_active_features(self.paths)
                    projects = read_projects(self.paths)
                with perf_block("resolve"):
                    turn_result = rules.advance_turn_result(state, items, districts, active_features, projects)
                report = turn_result.report
                with perf_block("writes"):
                    write_state(self.paths, state)
                    write_projects(self.paths, projects)
                    write_district_updates(self.paths, districts, report)
                    write_active_features(self.paths, active_features)
                    for item in items:
                        write_docket_item(self.paths, item)
                    generate_docket_rows(self.paths, self.seed, self.messages)
                    command_finish(self.paths, command_id, "applied", report)
                rebuild_output_layers(self.paths, self.messages)
                self.district_layer = DISTRICTS
                self.status_var.set(report)
            except Exception as exc:
                command_finish(self.paths, command_id, "error", error=str(exc))
                self.status_var.set(f"Advance failed: {exc}")
            finally:
                with perf_block("reload"):
                    self.reload()


def clear_output_selections(paths):
    """Clear lingering dashboard selections from output layers and feature classes."""

    with perf_block("sel"):
        for name, key in ((DISTRICTS, "districts"), (POINTS, "points"), (LINES, "lines"), (ZONES, "zones")):
            try:
                arcpy.management.SelectLayerByAttribute(name, "CLEAR_SELECTION")
            except Exception:
                try:
                    arcpy.management.SelectLayerByAttribute(paths[key], "CLEAR_SELECTION")
                except Exception:
                    pass


_GEOM_TYPE_TO_LAYER = {"POINT": POINTS, "LINE": LINES, "POLYGON": ZONES}


def _decision_layer_names(item):
    """Return the layer set a decision on this item actually changes, or None.

    None signals "rebuild all" so unknown geometry types fall back safely.
    """

    feature_layer = _GEOM_TYPE_TO_LAYER.get(getattr(item, "geometry_type", None))
    if feature_layer is None:
        return None
    return {DISTRICTS, feature_layer}


def rebuild_output_layers(paths, messages, layer_names=None):
    """Recreate map layers after GDB edits to avoid stale ArcGIS draw state.

    layer_names: optional iterable restricting remove/add/refresh to those names.
    None rebuilds all four (current behavior). Unknown values pass through.
    """

    with perf_block("rebuild"):
        clear_output_selections(paths)
        if layer_names is None:
            _log(messages, "REBUILD", "all")
        else:
            _log(messages, "REBUILD", f"targeted={sorted(layer_names)}")
        with perf_block("remove"):
            remove_outputs_from_map(messages, layer_names=layer_names)
        with perf_block("add"):
            add_outputs_to_map(paths, messages, layer_names=layer_names)
        with perf_block("refresh"):
            refresh_all(paths, messages, layer_names=layer_names)


def _filed_report_text(result):
    """Append compact non-money local changes to a decision report."""

    local = _local_changes_fragment(result)
    if not local:
        return result.report
    return f"{result.report} Local changes: {local}."


def _local_changes_fragment(result):
    """Summarize district deltas and feature updates for filed receipts."""

    parts = []
    for cell_id, delta in sorted((result.district_deltas or {}).items())[:3]:
        text = _compact_delta(delta)
        if text:
            parts.append(f"{cell_id} {text}")
    extra = max(0, len(result.district_deltas or {}) - 3)
    if extra:
        parts.append(f"+{extra} district(s)")
    for feature_id, update in sorted((result.feature_updates or {}).items())[:2]:
        status = update.get("status") or update.get("display_state") or "updated"
        condition = update.get("condition")
        due = update.get("maintenance_due_turn")
        feature_text = f"{feature_id} {status}"
        if condition not in (None, ""):
            feature_text += f" condition {condition}"
        if due not in (None, "", -1):
            feature_text += f" due {due}"
        parts.append(feature_text)
    return "; ".join(parts)


def _compact_delta(delta):
    """Format a district delta map without burying the receipt."""

    if not delta:
        return ""
    ordered = sorted(delta.items(), key=lambda row: (row[0] not in ("prosperity", "unrest", "culture", "risk", "services", "dissatisfaction"), row[0]))
    parts = []
    for metric, amount in ordered:
        if not amount:
            continue
        label = "dissat" if metric == "dissatisfaction" else metric[:4]
        parts.append(f"{label} {int(amount):+d}")
        if len(parts) == 4:
            break
    return ", ".join(parts)
