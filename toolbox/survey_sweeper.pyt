"""Survey Sweeper ArcGIS Pro toolbox.

This is the playable Gate D controller. The rules and action orchestration live
in importable modules so they can be tested outside ArcGIS Pro; this file only
handles ArcPy parameters, map/layer plumbing, messages, and refresh hints.
"""

from __future__ import annotations

import os
import sys
import traceback

import arcpy


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from toolbox import arcpy_game_actions as actions
from toolbox import arcpy_game_store as store_mod


TOOLBOX_LABEL = "Survey Sweeper"
TOOLBOX_ALIAS = "survey_sweeper"
DEFAULT_GDB_NAME = "survey_sweeper.gdb"
LYRX_NAME = "GameBoard_SurveySweeper.lyrx"

P_WORKSPACE = 0
P_LAYER = 1
P_ACTION = 2
P_PRESET = 3
P_SEED = 4
P_OUTPUT = 5

ACTIONS = [
    "New Game",
    "Reveal / Scout",
    "Flag / Mark",
    "Show Score",
    "Reset",
]

SETUP_ACTIONS = {"New Game", "Reset"}
SELECTION_ACTIONS = {"Reveal / Scout", "Flag / Mark"}


class Toolbox(object):
    def __init__(self):
        self.label = TOOLBOX_LABEL
        self.alias = TOOLBOX_ALIAS
        self.tools = [SurveySweeperController]


class SurveySweeperController(object):
    def __init__(self):
        self.label = "Survey Sweeper Controller"
        self.description = "Play Survey Sweeper using feature selection as input."
        self.canRunInBackground = False

    def getParameterInfo(self):
        p_workspace = arcpy.Parameter(
            displayName="Game Workspace (optional)",
            name="game_workspace",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input",
        )

        p_layer = arcpy.Parameter(
            displayName="Game Layer",
            name="game_layer",
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
        p_action.value = "New Game"

        p_preset = arcpy.Parameter(
            displayName="Board Preset",
            name="board_preset",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        p_preset.filter.type = "ValueList"
        p_preset.filter.list = ["Tiny Demo", "Small"]
        p_preset.value = "Tiny Demo"

        p_seed = arcpy.Parameter(
            displayName="Random Seed",
            name="random_seed",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input",
        )
        p_seed.value = 2026

        p_output = arcpy.Parameter(
            displayName="Output Game Layer",
            name="output_game_layer",
            datatype="GPFeatureLayer",
            parameterType="Derived",
            direction="Output",
        )
        lyrx = _lyrx_path()
        if os.path.exists(lyrx):
            p_output.symbology = lyrx

        return [p_workspace, p_layer, p_action, p_preset, p_seed, p_output]

    def updateParameters(self, parameters):
        action = parameters[P_ACTION].valueAsText or "New Game"
        parameters[P_LAYER].enabled = action not in {"New Game"}
        parameters[P_LAYER].parameterType = "Required" if action in SELECTION_ACTIONS else "Optional"
        parameters[P_PRESET].enabled = action in SETUP_ACTIONS
        parameters[P_SEED].enabled = action in SETUP_ACTIONS
        return

    def updateMessages(self, parameters):
        action = parameters[P_ACTION].valueAsText or "New Game"
        layer = parameters[P_LAYER]
        if action in SELECTION_ACTIONS and not layer.value:
            layer.setErrorMessage("Choose the current Survey Sweeper board layer.")
        else:
            layer.clearMessage()
        return

    def execute(self, parameters, messages):
        action = parameters[P_ACTION].valueAsText or "New Game"
        workspace = _resolve_workspace(parameters[P_WORKSPACE].value)
        layer = parameters[P_LAYER].value
        preset = parameters[P_PRESET].valueAsText or "Tiny Demo"
        seed = int(parameters[P_SEED].value or 2026)

        _message(messages, "Survey Sweeper action: {0}".format(action))
        store = store_mod.ArcPyStore(
            workspace,
            layer=layer,
            spatial_reference=_active_spatial_reference(messages),
        )

        try:
            result = _run_action(action, store, preset, seed)
        except Exception as exc:
            _error(messages, "{0}: {1}".format(type(exc).__name__, exc))
            _warning(messages, traceback.format_exc().strip().splitlines()[-1])
            raise

        if result.ok:
            _message(messages, result.message)
        else:
            _warning(messages, result.message)

        output_layer = _ensure_board_layer(store.board_fc, messages)
        if action in SETUP_ACTIONS:
            _clear_selection(output_layer, messages)
            _message(messages, "Selection cleared; choose a parcel.")
        _apply_symbology(output_layer, messages)
        _set_output(output_layer or store.board_fc, messages)
        _refresh(output_layer or store.board_fc, messages)
        return


def _run_action(action, store, preset, seed):
    handlers = {
        "New Game": lambda: actions.new_game_action(store, preset_name=preset, seed=seed),
        "Reveal / Scout": lambda: actions.reveal_action(store),
        "Flag / Mark": lambda: actions.flag_action(store),
        "Show Score": lambda: actions.show_score_action(store),
        "Reset": lambda: actions.reset_action(store, preset_name=preset, seed=seed),
    }
    try:
        return handlers[action]()
    except KeyError as exc:
        raise ValueError("Unknown Survey Sweeper action: {0!r}".format(action)) from exc


def _resolve_workspace(workspace_param_value):
    if workspace_param_value:
        return str(workspace_param_value)
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        if aprx.homeFolder:
            return os.path.join(aprx.homeFolder, "data", DEFAULT_GDB_NAME)
    except Exception:
        pass
    scratch = arcpy.env.scratchWorkspace or arcpy.env.scratchFolder
    if scratch:
        return os.path.join(scratch, DEFAULT_GDB_NAME)
    return os.path.join(os.path.expanduser("~"), DEFAULT_GDB_NAME)


def _active_spatial_reference(messages):
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        if aprx.activeMap and aprx.activeMap.spatialReference:
            return aprx.activeMap.spatialReference
    except Exception as exc:
        _warning(messages, "Using fallback spatial reference; active map unavailable: {0}".format(exc))
    return arcpy.SpatialReference(3857)


def _ensure_board_layer(board_fc, messages):
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap
        if active_map is None:
            _warning(messages, "No active map; output is the board feature class path.")
            return board_fc
        wanted = os.path.normcase(os.path.normpath(board_fc))
        for layer in active_map.listLayers():
            if not layer.supports("DATASOURCE"):
                continue
            source = os.path.normcase(os.path.normpath(str(layer.dataSource)))
            if source == wanted:
                return layer
        layer = active_map.addDataFromPath(board_fc)
        _message(messages, "Added board layer to active map.")
        return layer
    except Exception as exc:
        _warning(messages, "Could not add/find board layer: {0}".format(exc))
        return board_fc


def _clear_selection(layer_or_path, messages):
    try:
        arcpy.management.SelectLayerByAttribute(layer_or_path, "CLEAR_SELECTION")
    except Exception as exc:
        _warning(messages, "Could not clear selection: {0}".format(exc))


def _apply_symbology(layer_or_path, messages):
    lyrx = _lyrx_path()
    if not os.path.exists(lyrx):
        _warning(messages, "Symbology layer not found yet: {0}".format(lyrx))
        return
    try:
        arcpy.management.ApplySymbologyFromLayer(layer_or_path, lyrx)
    except Exception as exc:
        _warning(messages, "Could not apply symbology: {0}".format(exc))


def _set_output(layer_or_path, messages):
    try:
        value = layer_or_path
        if not isinstance(layer_or_path, str):
            value = getattr(layer_or_path, "name", None) or str(layer_or_path)
        arcpy.SetParameterAsText(P_OUTPUT, value)
    except Exception as exc:
        _warning(messages, "Could not set derived output: {0}".format(exc))


def _refresh(layer_or_path, messages):
    try:
        name = layer_or_path
        if not isinstance(layer_or_path, str):
            name = getattr(layer_or_path, "name", None) or str(layer_or_path)
        arcpy.RefreshLayer(name)
    except AttributeError:
        return
    except Exception as exc:
        _warning(messages, "RefreshLayer failed: {0}".format(exc))


def _lyrx_path():
    return os.path.join(ROOT, "symbology", LYRX_NAME)


def _message(messages, text):
    try:
        messages.addMessage(text)
    except Exception:
        arcpy.AddMessage(text)


def _warning(messages, text):
    try:
        messages.addWarningMessage(text)
    except Exception:
        arcpy.AddWarning(text)


def _error(messages, text):
    try:
        messages.addErrorMessage(text)
    except Exception:
        arcpy.AddError(text)
