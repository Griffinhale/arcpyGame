"""Permit Office prototype toolbox.

This ArcGIS Python toolbox entrypoint delegates schema, persistence, geometry,
and dashboard behavior to ``permit_office_arcgis`` helper modules. The gameplay
rules remain pure Python in ``permit_office`` and are exposed through the
``arcpy_permit_office_rules`` compatibility facade.
"""

from __future__ import annotations

import os
import sys
import importlib

import arcpy

_HERE = os.path.dirname(__file__)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

for _module_name in (
    "permit_office_arcgis.rules_loader",
    "permit_office_arcgis.schema",
    "permit_office_arcgis.messages",
    "permit_office_arcgis.store",
    "permit_office_arcgis.symbology_config",
    "permit_office_arcgis.geometry",
    "permit_office_arcgis.desk_view",
    "permit_office_arcgis.dashboard",
):
    _module = sys.modules.get(_module_name)
    if _module is not None:
        importlib.reload(_module)

from permit_office_arcgis.dashboard import DashboardController
from permit_office_arcgis.geometry import add_outputs_to_map, refresh_all, remove_outputs_from_map, seed_city_features
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
    """ArcGIS toolbox declaration for the Permit Office prototype."""

    def __init__(self):
        """Register the playable geoprocessing tool with ArcGIS Pro."""

        self.label = TOOLBOX_LABEL
        self.alias = TOOLBOX_ALIAS
        self.tools = [PermitOfficePrototype]


class PermitOfficePrototype(object):
    """ArcGIS geoprocessing tool that hosts the playable permit workflow."""

    def __init__(self):
        """Configure static tool metadata displayed in ArcGIS Pro."""

        self.label = "Permit Office Prototype"
        self.description = "Generated-district permit office dashboard prototype."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Declare ArcGIS tool parameters and their value-list constraints."""

        p_workspace = arcpy.Parameter(
            displayName="Game Workspace (optional)",
            name="game_workspace",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input",
        )
        p_districts = arcpy.Parameter(
            displayName="District Layer",
            name="district_layer",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
        )
        p_action = arcpy.Parameter(
            displayName="Action",
            name="action",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p_action.filter.type = "ValueList"
        p_action.filter.list = list(ACTIONS)
        p_action.value = "Ping Environment"
        p_seed = arcpy.Parameter(
            displayName="Random Seed",
            name="random_seed",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input",
        )
        p_seed.value = 2026
        p_output = arcpy.Parameter(
            displayName="Output District Layer",
            name="output_district_layer",
            datatype="GPFeatureLayer",
            parameterType="Derived",
            direction="Output",
        )
        return [p_workspace, p_districts, p_action, p_seed, p_output]

    def updateParameters(self, parameters):
        """Enable map-layer input only for dashboard actions."""

        action = parameters[P_ACTION].valueAsText
        parameters[P_DISTRICTS].enabled = action == "Open Dashboard"

    def execute(self, parameters, messages):
        """Dispatch the selected ArcGIS tool action against game state."""

        action = parameters[P_ACTION].valueAsText or "Ping Environment"
        seed = int(parameters[P_SEED].value or 2026)
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        paths = ensure_schema(gdb_path, messages)

        # Lightweight actions either report environment state or populate the
        # geodatabase without opening the dashboard event loop.
        if action == "Ping Environment":
            _log(messages, "PING", f"workspace = {gdb_path}")
            _log(messages, "PING", f"templates = {', '.join(sorted(rules.TEMPLATES))}")
            return
        if action == "New Game":
            clear_game_rows(paths)
            create_district_board(paths, seed, messages)
            seed_city_features(paths, seed, messages)
            write_state(paths, rules.CityState())
            generate_docket_rows(paths, seed, messages)
            remove_outputs_from_map(messages)
            add_outputs_to_map(paths, messages)
            refresh_all(paths, messages)
            arcpy.SetParameterAsText(P_OUTPUT, paths["districts"])
            return
        if action == "Generate Docket":
            generate_docket_rows(paths, seed, messages)
            add_outputs_to_map(paths, messages)
            refresh_all(paths, messages)
            return
        if action == "Show Scorecard":
            # Scorecards read persisted rows and pure rules data without
            # mutating the game so they are safe as a quick audit check.
            state = read_state(paths)
            districts = read_districts(paths)
            active_features = read_active_features(paths)
            items = read_docket(paths)
            grade, report = rules.scorecard(state, districts, active_features, items)
            _log(messages, "AUDIT", f"{report} {rules.population_city_summary(districts)}; incidents={rules.incident_summary(districts)}.")
            return
        if action == "Open Dashboard":
            # Dashboard startup requires map outputs and seeded rows because
            # Tkinter callbacks rely on persisted ArcGIS feature classes.
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
