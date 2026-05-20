"""Load the pure Permit Office rules facade from an ArcGIS toolbox context."""

from __future__ import annotations

import importlib.util
import os
import sys


def _clear_cached_rules_modules():
    """Drop cached pure-rule modules before loading the facade in ArcGIS Pro."""

    for name in list(sys.modules):
        if name == "permit_office" or name.startswith("permit_office."):
            sys.modules.pop(name, None)


def _load_rules():
    """Import the rules facade by file path so .pyt execution can find it."""

    toolbox_dir = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(toolbox_dir, "arcpy_permit_office_rules.py")
    _clear_cached_rules_modules()
    spec = importlib.util.spec_from_file_location("arcpy_permit_office_rules", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

rules = _load_rules()
