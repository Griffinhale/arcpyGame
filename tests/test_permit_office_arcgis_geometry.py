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
from toolbox.permit_office_arcgis.schema import DISTRICT_FIELDS


@dataclass
class FakeField:
    """Minimal ArcPy field object exposing only a name."""

    name: str


class FakeMessages:
    """Capture warning messages emitted by geometry helpers."""

    def __init__(self):
        """Initialize captured warning storage."""

        self.warnings = []

    def addWarningMessage(self, text):
        """Record an ArcPy-style warning message."""

        self.warnings.append(text)


class FakeManagement:
    """Record ArcPy management selection calls."""

    def __init__(self):
        """Initialize captured selections."""

        self.selections = []

    def SelectLayerByAttribute(self, layer, selection_type, where_clause=None):
        """Capture a layer selection operation."""

        self.selections.append((layer, selection_type, where_clause))


class FakeDA:
    """Provide fake ArcPy data-access cursor factories."""

    def __init__(self, rows):
        """Store shared fake table rows."""

        self.rows = rows

    def SearchCursor(self, path, fields, where_clause=None):
        """Return a read cursor over one fake table.

        where_clause is accepted to match real arcpy; the production code keeps
        an equivalent Python guard, so the fake can leave filtering to it.
        """

        return FakeSearchCursor(self.rows[path], fields)

    def UpdateCursor(self, path, fields, where_clause=None):
        """Return a mutable cursor over one fake table (where_clause ignored)."""

        return FakeUpdateCursor(self.rows[path], fields)


class FakeArcpy:
    """Small ArcPy module stand-in for geometry tests."""

    def __init__(self, rows):
        """Wire fake rows into management and data-access namespaces."""

        self.rows = rows
        self.da = FakeDA(rows)
        self.management = FakeManagement()

    def ListFields(self, path):
        """Return field names discovered from fake row dictionaries."""

        names = set()
        for row in self.rows.get(path, []):
            names.update(row)
        return [FakeField(name) for name in sorted(names)]


class FakeSearchCursor:
    """Context-manager search cursor for fake row dictionaries."""

    def __init__(self, rows, fields):
        """Project fake rows to the requested field order."""

        self.projected = [[row.get(field) for field in fields] for row in rows]
        self.index = 0

    def __enter__(self):
        """Enter the cursor context."""

        return self

    def __exit__(self, *exc):
        """Leave the cursor context without suppressing errors."""

        return False

    def __iter__(self):
        """Return this cursor as its own iterator."""

        return self

    def __next__(self):
        """Return the next projected row."""

        if self.index >= len(self.projected):
            raise StopIteration
        row = self.projected[self.index]
        self.index += 1
        return row


class FakeUpdateCursor:
    """Mutable fake cursor that supports update and delete calls."""

    def __init__(self, rows, fields):
        """Store rows and the ArcPy cursor field order."""

        self.rows = rows
        self.fields = fields
        self.index = 0
        self.current = None

    def __enter__(self):
        """Enter the cursor context."""

        return self

    def __exit__(self, *exc):
        """Leave the cursor context without suppressing errors."""

        return False

    def __iter__(self):
        """Return this cursor as its own iterator."""

        return self

    def __next__(self):
        """Return the next row values in cursor field order."""

        if self.index >= len(self.rows):
            raise StopIteration
        self.current = self.rows[self.index]
        self.index += 1
        return [self.current.get(field) for field in self.fields]

    def updateRow(self, values):
        """Write values back to the current fake row."""

        for field, value in zip(self.fields, values):
            self.current[field] = value

    def deleteRow(self):
        """Delete the current fake row."""

        if self.current in self.rows:
            self.rows.remove(self.current)
            self.index -= 1


def _paths():
    """Return canonical fake geodatabase paths."""

    return {"districts": "districts", "points": "points", "lines": "lines", "zones": "zones"}


def _rows():
    """Return empty fake feature-class row containers."""

    return {"districts": [], "points": [], "lines": [], "zones": []}


def test_district_identity_persistence_field_aliases_are_configured():
    """Verify district identity persistence fields use Task 7 aliases."""

    fields = {name: (field_type, alias, length) for name, field_type, alias, length in DISTRICT_FIELDS}

    assert fields["prior_district_type"] == ("TEXT", "Prior District Type", 32)
    assert fields["identity_state"] == ("TEXT", "Identity State", 32)
    assert fields["contesting_cell_id"] == ("TEXT", "Contesting District ID", 32)
    assert fields["contesting_type"] == ("TEXT", "Contesting Type", 32)
    assert fields["transition_due_turn"] == ("LONG", "Transition Due Week", None)
    assert fields["buyout_pressure"] == ("LONG", "Buyout Pressure", None)
    assert fields["last_buyout_report"] == ("TEXT", "Last Buyout Report", 512)


def test_select_case_context_creates_proposal_and_selects_support_feature(monkeypatch):
    """Verify selecting a case creates and selects its proposal context."""

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
        """Fake proposal insertion used by the selection flow."""

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
    """Verify maintenance cases select both proposal and subject feature."""

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
    """Verify hiding a proposal leaves active and context features intact."""

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
