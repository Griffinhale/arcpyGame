from __future__ import annotations

import importlib.util
import os
import sys

def _load_rules():
    toolbox_dir = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(toolbox_dir, "arcpy_permit_office_rules.py")
    spec = importlib.util.spec_from_file_location("arcpy_permit_office_rules", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

rules = _load_rules()
