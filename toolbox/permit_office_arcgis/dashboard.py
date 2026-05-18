"""Tkinter dashboard controller for ArcGIS-hosted Permit Office sessions."""

from __future__ import annotations

import traceback

from .geometry import (
    activate_proposal,
    insert_or_replace_proposal,
    mark_proposals,
    proposal_spillover,
    refresh_all,
    selected_cell_ids,
)
from .messages import _warn
from .rules_loader import rules
from .store import (
    action_log,
    command_finish,
    command_insert,
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


class _StatusProxy:
    """Compatibility shim for the old StringVar-like controller calls."""

    def __init__(self, controller):
        self.controller = controller

    def set(self, value):
        self.controller.status_text = str(value or "")

    def get(self):
        return self.controller.status_text


class DashboardController:
    """Coordinate dashboard UI actions with ArcGIS persistence helpers."""

    def __init__(self, paths, district_layer, seed, messages):
        self.paths = paths
        self.district_layer = district_layer
        self.seed = seed
        self.messages = messages

    def open(self):
        try:
            import tkinter as tk
        except Exception as exc:
            raise RuntimeError(f"tkinter is not available: {exc}")

        self.root = tk.Tk()
        self.root.title("Permit Office")
        self.root.geometry("980x680")
        self.root.minsize(900, 680)
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        self.selected_item_id = ""
        self.status_text = ""
        self.status_var = _StatusProxy(self)
        callbacks = DeskCallbacks(
            preview=self.preview_selected,
            inspect=self.inspect,
            approve=lambda: self.apply_decision("approve", False),
            approve_mitigated=lambda: self.apply_decision("approve_mitigated", True),
            deny=self.deny,
            advance_turn=self.advance_turn,
            close=self.root.destroy,
        )
        self.view = PermitDeskView(self.root, callbacks, self.select_item)

        self.reload()
        self.root.mainloop()

    def select_item(self, item_id):
        self.selected_item_id = item_id
        self.reload()

    def reload(self):
        state = read_state(self.paths)
        districts = read_districts(self.paths)
        items = read_docket(self.paths)
        model = build_desk_model(state, districts, items, self.selected_item_id, self.status_text)
        self.selected_item_id = model.selected_item_id
        self.view.render(model)

    def item_label(self, item):
        return f"{item.item_id} | {item.geometry_type} | {item.status} | {item.title}"

    def active_item(self):
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
        self.reload()

    def preview_selected(self):
        item = self.active_item()
        if not item:
            return
        try:
            selected = selected_cell_ids(self.district_layer)
            target_ids = insert_or_replace_proposal(self.paths, item, selected, self.messages)
            refresh_all(self.paths, self.messages)
            self.status_var.set(f"Previewed {item.title} for {', '.join(target_ids)}.")
            self.reload()
        except Exception as exc:
            self.status_var.set(f"Preview failed: {exc}")
            _warn(self.messages, "DASH", traceback.format_exc().strip().splitlines()[-1])

    def inspect(self):
        item = self.active_item()
        if not item:
            return
        command_id = command_insert(self.paths, "inspect", item.item_id, item.target_cell_ids)
        try:
            state = read_state(self.paths)
            districts = read_districts(self.paths)
            active_features = read_active_features(self.paths)
            result = rules.resolve_decision(state, item, districts, "inspect", item.target_cell_ids, seed=self.seed, active_features=active_features)
            write_state(self.paths, state)
            write_docket_item(self.paths, item)
            action_log(self.paths, state, result)
            command_finish(self.paths, command_id, result.command_status, result.report)
            self.status_var.set(result.report)
            open_effect_report(item.title, result.report, result.affected_cell_ids, state)
        except Exception as exc:
            command_finish(self.paths, command_id, "error", error=str(exc))
            self.status_var.set(f"Inspect failed: {exc}")
        self.reload()

    def apply_decision(self, action, mitigated):
        item = self.active_item()
        if not item:
            return
        command_id = command_insert(self.paths, action, item.item_id, item.target_cell_ids)
        try:
            if not item.target_cell_ids:
                selected = selected_cell_ids(self.district_layer)
                insert_or_replace_proposal(self.paths, item, selected, self.messages)
            spillover = [] if item.template_id == rules.MAINTENANCE_TEMPLATE_ID else proposal_spillover(self.paths, item)
            state = read_state(self.paths)
            districts = read_districts(self.paths)
            active_features = read_active_features(self.paths)
            projects = read_projects(self.paths)
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
                self.reload()
                return
            if result.feature_updates:
                write_active_features(self.paths, active_features)
            activate_proposal(self.paths, item, result.report)
            self._finish_decision(command_id, item, state, districts, projects, result)
        except Exception as exc:
            command_finish(self.paths, command_id, "error", error=str(exc))
            self.status_var.set(f"Approve failed: {exc}")
            _warn(self.messages, "DASH", traceback.format_exc().strip().splitlines()[-1])
        self.reload()

    def deny(self):
        item = self.active_item()
        if not item:
            return
        command_id = command_insert(self.paths, "deny", item.item_id, item.target_cell_ids)
        try:
            state = read_state(self.paths)
            districts = read_districts(self.paths)
            active_features = read_active_features(self.paths)
            projects = read_projects(self.paths)
            result = rules.resolve_decision(state, item, districts, "deny", item.target_cell_ids, seed=self.seed, active_features=active_features, projects=projects)
            if not result.ok:
                command_finish(self.paths, command_id, "error", result.report, result.report)
                self.status_var.set(result.report)
                self.reload()
                return
            if result.feature_updates:
                write_active_features(self.paths, active_features)
            proposal_status = item.status if item.status in ("denied", "deferred") else "denied"
            mark_proposals(self.paths, item.item_id, proposal_status, result.report)
            self._finish_decision(command_id, item, state, districts, projects, result)
        except Exception as exc:
            command_finish(self.paths, command_id, "error", error=str(exc))
            self.status_var.set(f"Deny failed: {exc}")
        self.reload()

    def _finish_decision(self, command_id, item, state, districts, projects, result):
        write_district_updates(self.paths, districts, result.report, result.affected_cell_ids)
        write_state(self.paths, state)
        write_projects(self.paths, projects)
        write_docket_item(self.paths, item)
        action_log(self.paths, state, result)
        command_finish(self.paths, command_id, result.command_status, result.report)
        refresh_all(self.paths, self.messages)
        self.status_var.set(result.report)
        open_effect_report(item.title, result.report, result.affected_cell_ids, state)

    def advance_turn(self):
        command_id = command_insert(self.paths, "advance_turn", "", [])
        try:
            state = read_state(self.paths)
            items = read_docket(self.paths)
            districts = read_districts(self.paths)
            active_features = read_active_features(self.paths)
            projects = read_projects(self.paths)
            turn_result = rules.advance_turn_result(state, items, districts, active_features, projects)
            report = turn_result.report
            write_state(self.paths, state)
            write_projects(self.paths, projects)
            write_district_updates(self.paths, districts, report)
            write_active_features(self.paths, active_features)
            for item in items:
                write_docket_item(self.paths, item)
            generate_docket_rows(self.paths, self.seed, self.messages)
            command_finish(self.paths, command_id, "applied", report)
            refresh_all(self.paths, self.messages)
            self.status_var.set(report)
        except Exception as exc:
            command_finish(self.paths, command_id, "error", error=str(exc))
            self.status_var.set(f"Advance failed: {exc}")
        self.reload()
