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

def open_effect_report(title, report, affected, state):
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return
    root = tk.Toplevel()
    root.title("Permit Effect Report")
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(frame, text=title, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
    ttk.Label(frame, text=report, wraplength=560).grid(row=1, column=0, sticky="w", pady=4)
    ttk.Label(frame, text=f"Affected districts: {', '.join(affected) if affected else '(none)'}", wraplength=560).grid(row=2, column=0, sticky="w", pady=4)
    metrics = f"AP {state.ap}/{state.max_ap} | ${state.money} | Prosperity {state.prosperity} | Unrest {state.unrest} | Culture {state.culture} | Risk {state.risk} | Heat {rules.heat_summary(state)}"
    ttk.Label(frame, text=metrics, wraplength=560).grid(row=3, column=0, sticky="w", pady=4)
    ttk.Button(frame, text="Close", command=root.destroy).grid(row=4, column=0, sticky="e", pady=(10, 0))
    root.grab_set()
    root.wait_window()


class DashboardController:
    def __init__(self, paths, district_layer, seed, messages):
        self.paths = paths
        self.district_layer = district_layer
        self.seed = seed
        self.messages = messages

    def open(self):
        try:
            import tkinter as tk
            from tkinter import ttk
        except Exception as exc:
            raise RuntimeError(f"tkinter is not available: {exc}")

        self.root = tk.Tk()
        self.root.title("Permit Office")
        self.root.geometry("760x520")
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        self.item_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.metrics_var = tk.StringVar()
        self.detail_var = tk.StringVar()

        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Permit Office", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.metrics_var).grid(row=0, column=1, sticky="e")

        ttk.Label(frame, text="Active docket item").grid(row=1, column=0, sticky="w", pady=(12, 2))
        self.combo = ttk.Combobox(frame, textvariable=self.item_var, state="readonly", width=54)
        self.combo.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.combo.bind("<<ComboboxSelected>>", lambda _evt: self.refresh_detail())

        ttk.Label(frame, textvariable=self.detail_var, wraplength=720, justify="left").grid(row=3, column=0, columnspan=2, sticky="w", pady=10)

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)
        for text, command in (
            ("Preview From Selection", self.preview_selected),
            ("Inspect", self.inspect),
            ("Approve", lambda: self.apply_decision("approve", False)),
            ("Approve + Mitigate", lambda: self.apply_decision("approve_mitigated", True)),
            ("Deny", self.deny),
            ("Advance Turn", self.advance_turn),
        ):
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 6), pady=3)

        ttk.Label(frame, textvariable=self.status_var, wraplength=720).grid(row=5, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(frame, text="Close", command=self.root.destroy).grid(row=6, column=1, sticky="e", pady=(18, 0))

        self.reload()
        self.root.mainloop()

    def reload(self):
        state = read_state(self.paths)
        districts = read_districts(self.paths)
        items = read_docket(self.paths)
        labels = [self.item_label(item) for item in items if item.status in ("open", "inspected", "active", "carried")]
        self.combo["values"] = labels
        if labels and self.item_var.get() not in labels:
            self.item_var.set(labels[0])
        heat = rules.heat_summary(state)
        population = rules.population_city_summary(districts)
        incidents = rules.incident_summary(districts)
        self.metrics_var.set(
            f"Turn {state.turn}/6 | AP {state.ap}/{state.max_ap} | ${state.money} | P {state.prosperity} U {state.unrest} C {state.culture} R {state.risk} | {population} | Heat {heat} | Incidents {incidents}"
        )
        self.refresh_detail()

    def item_label(self, item):
        return f"{item.item_id} | {item.geometry_type} | {item.status} | {item.title}"

    def active_item(self):
        selected = self.item_var.get()
        if not selected:
            return None
        item_id = selected.split(" | ", 1)[0]
        for item in read_docket(self.paths):
            if item.item_id == item_id:
                return item
        return None

    def refresh_detail(self):
        item = self.active_item()
        if not item:
            self.detail_var.set("No active docket item.")
            return
        state = read_state(self.paths)
        template = rules.TEMPLATES[item.template_id]
        archetype = rules.feature_archetype_for_template(template)
        stakeholder = item.stakeholder or template.stakeholder
        target_rule = item.target_rule or template.target_rule
        heat = state.stakeholder_heat.get(stakeholder, 0)
        districts = read_districts(self.paths)
        target_profiles = [districts[cid] for cid in item.target_cell_ids if cid in districts]
        population_hint = rules.target_population_hint(item, target_profiles)
        population_line = f"\n{population_hint}" if population_hint else ""
        action_note = "Approve=enforce; Approve + Mitigate=settle/retro-permit; Deny=defer." if template.is_enforcement else "Approve=issue permit; Approve + Mitigate=issue with conditions; Deny=reject."
        if template.is_incident:
            action_note = "Approve=formal response; Approve + Mitigate=settle/service response; Deny=defer incident."
        text = (
            f"{item.title}\n"
            f"Type: {template.category}; geometry: {item.geometry_type}; stakeholder: {stakeholder.replace('_', ' ')}; heat: {heat}\n"
            f"Feature: {archetype.label}; family: {archetype.family}; service: {archetype.service_type or 'none'}; land use: {archetype.land_use or 'none'}\n"
            f"Cost: {template.ap_cost} AP / ${template.money_cost}; mitigation +${template.mitigation_cost}\n"
            f"Target rule: {target_rule}\n"
            f"Failure mode: {template.failure_mode or 'none filed'}\n"
            f"Contact: {template.contact_name or 'not assigned'}\n"
            f"Actions: {action_note}\n"
            f"Targets: {', '.join(item.target_cell_ids) if item.target_cell_ids else '(select on map, then preview)'}\n"
            f"{item.preview_text}{population_line}"
        )
        self.detail_var.set(text)

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
            write_district_updates(self.paths, districts, result.report, result.affected_cell_ids)
            write_state(self.paths, state)
            write_projects(self.paths, projects)
            write_docket_item(self.paths, item)
            action_log(self.paths, state, result)
            command_finish(self.paths, command_id, result.command_status, result.report)
            refresh_all(self.paths, self.messages)
            self.status_var.set(result.report)
            open_effect_report(item.title, result.report, result.affected_cell_ids, state)
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
            write_district_updates(self.paths, districts, result.report, result.affected_cell_ids)
            write_state(self.paths, state)
            write_projects(self.paths, projects)
            write_docket_item(self.paths, item)
            action_log(self.paths, state, result)
            command_finish(self.paths, command_id, result.command_status, result.report)
            refresh_all(self.paths, self.messages)
            self.status_var.set(result.report)
            open_effect_report(item.title, result.report, result.affected_cell_ids, state)
        except Exception as exc:
            command_finish(self.paths, command_id, "error", error=str(exc))
            self.status_var.set(f"Deny failed: {exc}")
        self.reload()

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


