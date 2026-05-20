"""Compatibility facade for the Permit Office pure rules package.

ArcGIS Pro loads this file directly from the Python toolbox, while local tests
import it as ``toolbox.arcpy_permit_office_rules``. Keep both import paths
working and expose the same rule API from ``toolbox/permit_office``.
"""

from __future__ import annotations


try:
    from .permit_office import *  # noqa: F401,F403
    from .permit_office import __all__  # noqa: F401
except ImportError:
    import importlib
    import os
    import sys

    _HERE = os.path.dirname(__file__)
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    _rules = importlib.import_module("permit_office")
    globals().update({name: getattr(_rules, name) for name in _rules.__all__})
    __all__ = _rules.__all__
