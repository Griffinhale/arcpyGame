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
    "permit_office_arcgis._perf",
    "permit_office_arcgis.store",
    "permit_office_arcgis.symbology_config",
    "permit_office_arcgis.geometry",
    "permit_office_arcgis.desk_model",
    "permit_office_arcgis.desk_view",
    "permit_office_arcgis.dashboard",
):
    _module = sys.modules.get(_module_name)
    if _module is not None:
        importlib.reload(_module)

from permit_office_arcgis import _perf
from permit_office_arcgis.dashboard import DashboardController, REDRAW_EXPERIMENT_ENV, has_saved_game, prepare_dashboard_session, run_redraw_benchmark
from permit_office_arcgis.geometry import output_layers_present
from permit_office_arcgis.schema import (
    P_OUTPUT,
    P_PERF,
    P_REDRAW_BENCHMARK_RUNS,
    P_REDRAW_EXPERIMENT,
    P_WORKSPACE,
    DISTRICTS,
    TOOLBOX_ALIAS,
    TOOLBOX_LABEL,
    ensure_schema,
    resolve_workspace,
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
        """Declare ArcGIS tool parameters for launching the dashboard."""

        p_workspace = arcpy.Parameter(
            displayName="Game Workspace (optional)",
            name="game_workspace",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input",
        )
        p_output = arcpy.Parameter(
            displayName="Output District Layer",
            name="output_district_layer",
            datatype="GPFeatureLayer",
            parameterType="Derived",
            direction="Output",
        )
        p_perf = arcpy.Parameter(
            displayName="Log Refresh Timings",
            name="enable_perf",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_perf.value = False
        p_redraw = arcpy.Parameter(
            displayName="Redraw Experiment",
            name="redraw_experiment",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        p_redraw.filter.type = "ValueList"
        p_redraw.filter.list = [
            "None",
            "volatile-overlay",
            "predrawn-swap",
            "predrawn-swap-refresh",
            "predrawn-rehydrate",
            "predrawn-rehydrate-smart-features",
            "predrawn-rehydrate-style-cache",
            "predrawn-rehydrate-template-style",
            "predrawn-rehydrate-refresh-hidden-first",
            "predrawn-rehydrate-refresh-visible-first",
            "hybrid-rehydrate-districts-swap-points",
            "alt-refresh",
            "alt-definition-query",
            "alt-visibility",
            "alt-cim",
            "alt-symbology",
            "alt-make-feature-layer",
        ]
        p_redraw.value = "None"
        p_benchmark = arcpy.Parameter(
            displayName="Redraw Benchmark Runs",
            name="redraw_benchmark_runs",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input",
        )
        p_benchmark.value = 0
        return [p_workspace, p_output, p_perf, p_redraw, p_benchmark]

    def execute(self, parameters, messages):
        """Open the dashboard against the resolved saved-game geodatabase."""

        _perf.set_enabled(bool(parameters[P_PERF].value))
        redraw_experiment = str(parameters[P_REDRAW_EXPERIMENT].value or "").strip()
        benchmark_runs = int(parameters[P_REDRAW_BENCHMARK_RUNS].value or 0)
        if redraw_experiment and redraw_experiment != "None":
            os.environ[REDRAW_EXPERIMENT_ENV] = redraw_experiment
            messages.addMessage(f"[EXPERIMENT] selected {redraw_experiment}")
        else:
            os.environ.pop(REDRAW_EXPERIMENT_ENV, None)
        gdb_path = resolve_workspace(parameters[P_WORKSPACE].value, messages)
        paths = ensure_schema(gdb_path, messages)
        # Detect an empty map BEFORE adding any layers: a save in this workspace
        # with no Permit Office layers on the map opens to a fresh-start prompt
        # instead of silently resuming the old board.
        offer_fresh_start = has_saved_game(paths) and not output_layers_present()
        seed = prepare_dashboard_session(paths, 2026, messages, resume=not offer_fresh_start)
        run_redraw_benchmark(paths, messages, benchmark_runs)
        DashboardController(paths, DISTRICTS, seed, messages, offer_fresh_start=offer_fresh_start).open()
        arcpy.SetParameterAsText(P_OUTPUT, paths["districts"])
