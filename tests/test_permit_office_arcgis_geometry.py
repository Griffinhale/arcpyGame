"""Fake-ArcPy coverage for Permit Office map-selection helpers."""

from __future__ import annotations

from dataclasses import dataclass
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

from toolbox import arcpy_permit_office_rules as rules
from toolbox.permit_office_arcgis import geometry


@dataclass
class FakeField:
    name: str


class FakeMessages:
    def __init__(self):
        self.warnings = []

    def addWarningMessage(self, text):
        self.warnings.append(text)


class FakeManagement:
    def __init__(self):
        self.selections = []

    def SelectLayerByAttribute(self, layer, selection_type, where_clause=None):
        self.selections.append((layer, selection_type, where_clause))


class FakeDA:
    def __init__(self, rows):
        self.rows = rows

    def SearchCursor(self, path, fields):
        return FakeSearchCursor(self.rows[path], fields)

    def UpdateCursor(self, path, fields):
        return FakeUpdateCursor(self.rows[path], fields)


class FakeArcpy:
    def __init__(self, rows):
        self.rows = rows
        self.da = FakeDA(rows)
        self.management = FakeManagement()

    def ListFields(self, path):
        names = set()
        for row in self.rows.get(path, []):
            names.update(row)
        return [FakeField(name) for name in sorted(names)]


class FakeSearchCursor:
    def __init__(self, rows, fields):
        self.projected = [[row.get(field) for field in fields] for row in rows]
        self.index = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.projected):
            raise StopIteration
        row = self.projected[self.index]
        self.index += 1
        return row


class FakeUpdateCursor:
    def __init__(self, rows, fields):
        self.rows = rows
        self.fields = fields
        self.index = 0
        self.current = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.rows):
            raise StopIteration
        self.current = self.rows[self.index]
        self.index += 1
        return [self.current.get(field) for field in self.fields]

    def updateRow(self, values):
        for field, value in zip(self.fields, values):
            self.current[field] = value

    def deleteRow(self):
        if self.current in self.rows:
            self.rows.remove(self.current)
            self.index -= 1


def _paths():
    return {"districts": "districts", "points": "points", "lines": "lines", "zones": "zones"}


def _rows():
    return {"districts": [], "points": [], "lines": [], "zones": []}


def test_select_case_context_creates_proposal_and_selects_support_feature(monkeypatch):
    rows = _rows()
    fake = FakeArcpy(rows)
    monkeypatch.setattr(geometry, "arcpy", fake)
    item = rules.DocketItem(
        "CASE-1",
        "street_vendor_compact",
        "Street Vendor Compact",
        "POINT",
        1,
        target_cell_ids=["D0000"],
    )

    def insert(paths, docket_item, target_ids, messages):
        rows["points"].append(
            {
                "item_id": docket_item.item_id,
                "status": "proposed",
                "target_cell_ids": ",".join(target_ids),
                "feature_id": "P-1",
            }
        )
        return list(target_ids)

    monkeypatch.setattr(geometry, "insert_or_replace_proposal", insert)

    geometry.select_case_context(_paths(), "district_layer", item, 2026, FakeMessages())

    assert rows["points"][0]["item_id"] == "CASE-1"
    assert ("district_layer", "NEW_SELECTION", "cell_id = 'D0000'") in fake.management.selections
    assert ("PermitPoints", "NEW_SELECTION", "item_id = 'CASE-1'") in fake.management.selections


def test_maintenance_selection_includes_referenced_active_feature(monkeypatch):
    rows = _rows()
    rows["points"].append({"item_id": "CASE-2", "status": "proposed", "target_cell_ids": "D0000", "feature_id": "P-2"})
    fake = FakeArcpy(rows)
    monkeypatch.setattr(geometry, "arcpy", fake)
    item = rules.DocketItem(
        "CASE-2",
        rules.MAINTENANCE_TEMPLATE_ID,
        "Maintenance Order",
        "POINT",
        1,
        target_cell_ids=["D0000"],
        subject_feature_id="FEATURE-77",
    )

    geometry.select_case_context(_paths(), "district_layer", item, 2026, FakeMessages())

    support_wheres = [where for layer, _mode, where in fake.management.selections if layer == "PermitPoints"]
    assert support_wheres == ["item_id = 'CASE-2' OR feature_id = 'FEATURE-77'"]


def test_hide_show_affects_only_selected_proposed_feature(monkeypatch):
    rows = _rows()
    rows["points"].extend(
        [
            {"item_id": "CASE-3", "status": "proposed", "target_cell_ids": "D0000", "feature_id": "P-3"},
            {"item_id": "CASE-3", "status": "active", "target_cell_ids": "D0000", "feature_id": "A-3"},
            {"item_id": "", "status": "context", "target_cell_ids": "D0001", "feature_id": "CITY-1"},
        ]
    )
    fake = FakeArcpy(rows)
    monkeypatch.setattr(geometry, "arcpy", fake)
    item = rules.DocketItem(
        "CASE-3",
        "street_vendor_compact",
        "Street Vendor Compact",
        "POINT",
        1,
        target_cell_ids=["D0000"],
    )

    assert geometry.case_proposal_visible(_paths(), item) is True
    assert geometry.hide_case_proposal(_paths(), item.item_id) is True

    assert geometry.case_proposal_visible(_paths(), item) is False
    assert [(row["feature_id"], row["status"]) for row in rows["points"]] == [
        ("A-3", "active"),
        ("CITY-1", "context"),
    ]
