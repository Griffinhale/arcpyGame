"""Workspace-resolution coverage for the Permit Office toolbox schema layer."""

from __future__ import annotations

import os
from types import SimpleNamespace
import sys


sys.modules.setdefault(
    "arcpy",
    SimpleNamespace(
        AddMessage=lambda text: None,
        AddWarning=lambda text: None,
        AddError=lambda text: None,
    ),
)

import arcpy

from toolbox.permit_office_arcgis import schema


def _raise(*_args, **_kwargs):
    """Stand-in that fails if the default-resolution path is ever consulted."""

    raise AssertionError("default workspace resolution should not be consulted")


def test_resolve_workspace_uses_provided_gdb_verbatim_without_default():
    """A provided .gdb is honored exactly; the default chain is never consulted.

    arcpy.mp / arcpy.env are absent on the test stub, so touching the project-home
    or scratch fallback would raise -- proving the provided workspace wins.
    """

    path = schema.resolve_workspace("C:/games/save.gdb", None)

    assert path == "C:/games/save.gdb"


def test_resolve_workspace_provided_folder_appends_default_gdb_name():
    """A provided folder resolves to <folder>/permit_office.gdb, not the default."""

    path = schema.resolve_workspace("C:/games/board", None)

    assert path == os.path.join("C:/games/board", schema.DEFAULT_GDB_NAME)


def test_resolve_workspace_honors_provided_workspace_with_empty_contents():
    """A provided workspace is used even when it has no game rows yet.

    This is the regression the live run flagged: an empty/new target workspace
    must not fall back to the default project geodatabase.
    """

    path = schema.resolve_workspace("D:/fresh/new_game.gdb", None)

    assert path == "D:/fresh/new_game.gdb"


def test_resolve_workspace_blank_value_falls_back_to_default(monkeypatch):
    """A blank/whitespace value is treated as 'not provided' and falls back."""

    monkeypatch.setattr(arcpy, "mp", SimpleNamespace(ArcGISProject=_raise), raising=False)
    monkeypatch.setattr(
        arcpy, "env", SimpleNamespace(scratchWorkspace="C:/scratch.gdb", scratchFolder=None), raising=False
    )

    path = schema.resolve_workspace("   ", None)

    assert path == "C:/scratch.gdb"


def test_resolve_workspace_hash_sentinel_falls_back_to_default(monkeypatch):
    """The ArcGIS '#' unspecified sentinel is treated as 'not provided'."""

    monkeypatch.setattr(arcpy, "mp", SimpleNamespace(ArcGISProject=_raise), raising=False)
    monkeypatch.setattr(
        arcpy, "env", SimpleNamespace(scratchWorkspace="C:/scratch.gdb", scratchFolder=None), raising=False
    )

    path = schema.resolve_workspace("#", None)

    assert path == "C:/scratch.gdb"


def test_resolve_workspace_none_falls_back_to_project_home(monkeypatch):
    """With no value, the project home data folder is used when available."""

    monkeypatch.setattr(
        arcpy, "mp", SimpleNamespace(ArcGISProject=lambda _name: SimpleNamespace(homeFolder="C:/proj")), raising=False
    )
    monkeypatch.setattr(arcpy, "env", SimpleNamespace(scratchWorkspace=None, scratchFolder=None), raising=False)

    path = schema.resolve_workspace(None, None)

    assert path == os.path.join("C:/proj", "data", schema.DEFAULT_GDB_NAME)
