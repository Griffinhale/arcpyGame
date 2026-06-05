"""Coverage for store write helpers, focused on render-dirty detection."""

from __future__ import annotations

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

from toolbox import arcpy_permit_office_rules as rules
from toolbox.permit_office_arcgis import store


class _FakeUpdateCursor:
    """Minimal arcpy.da.UpdateCursor stand-in over a fixed list of rows."""

    def __init__(self, rows):
        self._rows = rows
        self.updated = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def __iter__(self):
        return iter(self._rows)

    def updateRow(self, row):
        self.updated.append(list(row))


# Rendered district fields and their column positions in write_district_updates.
_RENDER_COL = {"district_type": 7, "identity_state": 9, "prosperity_band": 32}


def _district_row(profile, **rendered_overrides):
    """Build a 33-column district row matching the profile's rendered values.

    rendered_overrides lets a test seed the *old* stored value for a rendered
    field so the write detects (or doesn't detect) a change.
    """

    row = [0] * 33
    row[0] = profile.cell_id
    row[7] = profile.district_type
    row[9] = profile.identity_state
    row[32] = profile.prosperity_band
    for field, value in rendered_overrides.items():
        row[_RENDER_COL[field]] = value
    return row


def _patch_cursor(monkeypatch, rows):
    cursor = _FakeUpdateCursor(rows)
    monkeypatch.setattr(
        store.arcpy, "da", SimpleNamespace(UpdateCursor=lambda path, fields: cursor), raising=False
    )
    return cursor


def _profile():
    profile = rules.DistrictProfile("D0000", "Harbor Flats", 1000, 50, 20, 35, 25, 50, "mercantile")
    rules.normalize_profile(profile)
    return profile


def test_write_district_updates_reports_no_rendered_change(monkeypatch):
    """Verify an unchanged rendered state returns False (refresh-only is safe)."""
    profile = _profile()
    _patch_cursor(monkeypatch, [_district_row(profile)])

    dirty = store.write_district_updates({"districts": "fc"}, {profile.cell_id: profile}, "report")

    assert dirty is False


def test_write_district_updates_reports_rendered_change(monkeypatch):
    """Verify a changed rendered field returns True so the district family re-adds."""
    profile = _profile()
    # The stored prosperity band differs from what the profile now normalizes to.
    _patch_cursor(monkeypatch, [_district_row(profile, prosperity_band="__stale__")])

    dirty = store.write_district_updates({"districts": "fc"}, {profile.cell_id: profile}, "report")

    assert dirty is True
