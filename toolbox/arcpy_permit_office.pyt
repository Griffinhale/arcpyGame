"""Permit Office prototype toolbox.

This ArcGIS Python toolbox entrypoint delegates schema, persistence, geometry,
and dashboard behavior to ``permit_office_arcgis`` helper modules. The gameplay
rules remain pure Python in ``permit_office`` and are exposed through the
``arcpy_permit_office_rules`` compatibility facade.
"""

from __future__ import annotations

import os
import sys

import arcpy

_HERE = os.path.dirname(__file__)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from permit_office_arcgis.dashboard import DashboardController
from permit_office_arcgis.geometry import add_outputs_to_map, refresh_all
from permit_office_arcgis.messages import _err, _log
from permit_office_arcgis.rules_loader import rules
from permit_office_arcgis.schema import (
    ACTIONS,
    P_ACTION,
    P_DISTRICTS,
    P_OUTPUT,
    P_SEED,
    P_WORKSPACE,
    TOOLBOX_ALIAS,
    TOOLBOX_LABEL,
    clear_game_rows,
    ensure_schema,
    resolve_workspace,
)
from permit_office_arcgis.store import (
    create_district_board,
    generate_docket_rows,
    read_active_features,
    read_districts,
    read_docket,
    read_state,
    write_state,
)


class Toolbox(object):
    def __init__(self):
        self.label = TOOLBOX_LABEL
        self.alias = TOOLBOX_ALIAS
        self.tools = [PermitOfficePrototype]


class PermitOfficePrototype(object):
    def __init__(self):
        self.label = "Permit Office Prototype"
        self.description = "Generated-district permit office dashboard prototype."
        self.canRunInBackground = False

    def getParameterInfo(self):
        p_workspace = arcpy.Parameter("Game Workspace (optional)", "game_workspace", "DEWorkspace", "Optional", "Input")
        p_districts = arcpy.Parameter("District Layer", "district_layer", "GPFeatureLayer", "Optional", "Input")
        p_action = arcpy.Parameter("Action", "action", "GPString", "Required", "Input")
        p_action.filter.type = "ValueList"
        p_action.filter.list = list(ACTIONS)
        p_action.value = "Ping Environment"
        p_seed = arcpy.Parameter("Random Seed", "random_seed", "GPLong", "Optional", "Input")
        p_seed.value = 2026
        p_output = arcpy.Parameter("Output District Layer", "output_district_layer", "GPFeatureLayer", "Derived", "Output")
        return [p_workspace, p_districts, p_action, p_seed, p_output]

    def updateParameters(self, parameters):
        action = parameters[P_ACTION].valueAsText
        parameters[P_DISTRICTS].enabled = action == "Open Dashboard"

    def execute(self, parameters, messages):
        action = parameters[P_ACTION].valueAsText or "Ping Environment"
        seed = int(parameters[P_SEED].value or 2026)
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        paths = ensure_schema(gdb_path, messages)

        if action == "Ping Environment":
            _log(messages, "PING", f"workspace = {gdb_path}")
            _log(messages, "PING", f"templates = {', '.join(sorted(rules.TEMPLATES))}")
            return
        if action == "New Game":
            clear_game_rows(paths)
            create_district_board(paths, seed, messages)
            write_state(paths, rules.CityState())
            generate_docket_rows(paths, seed, messages)
            add_outputs_to_map(paths, messages)
            refresh_all(paths, messages)
            arcpy.SetParameterAsText(P_OUTPUT, paths["districts"])
            return
        if action == "Generate Docket":
            generate_docket_rows(paths, seed, messages)
            refresh_all(paths, messages)
            return
        if action == "Show Scorecard":
            state = read_state(paths)
            districts = read_districts(paths)
            active_features = read_active_features(paths)
            items = read_docket(paths)
            grade, report = rules.scorecard(state, districts, active_features, items)
            _log(messages, "AUDIT", f"{report} {rules.population_city_summary(districts)}; incidents={rules.incident_summary(districts)}.")
            return
        if action == "Open Dashboard":
            district_layer = parameters[P_DISTRICTS].value or paths["districts"]
            add_outputs_to_map(paths, messages)
            if int(arcpy.management.GetCount(paths["districts"])[0]) == 0:
                _err(messages, "DASH", "Run New Game before opening the dashboard.")
                return
            if int(arcpy.management.GetCount(paths["docket"])[0]) == 0:
                generate_docket_rows(paths, seed, messages)
            DashboardController(paths, district_layer, seed, messages).open()
            arcpy.SetParameterAsText(P_OUTPUT, paths["districts"])
            return
        _err(messages, "DISPATCH", f"unknown action: {action}")
