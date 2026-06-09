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


class CapturingMessages(FakeMessages):
    """Capture informational and warning messages emitted by geometry helpers."""

    def __init__(self):
        """Initialize captured message storage."""

        super().__init__()
        self.messages = []

    def addMessage(self, text):
        """Record an ArcPy-style informational message."""

        self.messages.append(text)


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


class _SelectionArcpy:
    """Tailored ArcPy stub for selected_cell_ids fast-path tests."""

    def __init__(self, fidset, cursor_rows, legacy_field=None, fail_cell_id=False):
        """Configure selection state, cursor rows, and an optional legacy field name."""

        self.da = self
        self._fidset = fidset
        self._cursor_rows = cursor_rows
        self._legacy_field = legacy_field
        self._fail_cell_id = fail_cell_id
        self.listfields_calls = 0

    def Describe(self, _layer):
        """Report the configured FIDSet so has_selection is True."""

        return {"FIDSet": self._fidset}

    def SearchCursor(self, _layer, fields):
        """Return rows for the resolved field, or fail the direct cell_id read."""

        if fields == ["cell_id"] and self._fail_cell_id:
            raise RuntimeError("Field cell_id does not exist")
        return iter([[value] for value in self._cursor_rows])

    def ListFields(self, _layer):
        """Count field scans and expose the legacy field name on fallback."""

        self.listfields_calls += 1
        return [FakeField(self._legacy_field)] if self._legacy_field else []


def test_selected_cell_ids_reads_cell_id_directly_without_field_scan(monkeypatch):
    """Verify the common path reads the known cell_id column and skips ListFields."""

    fake = _SelectionArcpy(fidset="0;1", cursor_rows=["D0000", "D0001"])
    monkeypatch.setattr(geometry, "arcpy", fake)

    result = geometry.selected_cell_ids("districts_layer")

    assert result == ["D0000", "D0001"]
    assert fake.listfields_calls == 0  # fast path avoided the metadata round-trip


def test_selected_cell_ids_falls_back_to_field_scan_on_cursor_error(monkeypatch):
    """Verify a legacy/renamed column still resolves via the ListFields fallback."""

    fake = _SelectionArcpy(
        fidset="0", cursor_rows=["D0000"], legacy_field="CELL_ID", fail_cell_id=True
    )
    monkeypatch.setattr(geometry, "arcpy", fake)

    result = geometry.selected_cell_ids("districts_layer")

    assert result == ["D0000"]
    assert fake.listfields_calls == 1  # fell back exactly once


def _map_arcpy(layer_names, active=True, raise_err=False):
    """Return an ArcPy stub whose active map carries the given layer names."""

    def _project(_name):
        if raise_err:
            raise RuntimeError("no CURRENT project")
        if not active:
            return SimpleNamespace(activeMap=None)
        layers = [SimpleNamespace(name=name) for name in layer_names]
        return SimpleNamespace(activeMap=SimpleNamespace(listLayers=lambda: layers))

    return SimpleNamespace(mp=SimpleNamespace(ArcGISProject=_project))


def test_output_layers_present_true_when_an_output_layer_is_on_map(monkeypatch):
    """Verify a map carrying a Permit Office layer reports present (resume)."""

    monkeypatch.setattr(geometry, "arcpy", _map_arcpy([geometry.DISTRICTS, "Topographic"]))

    assert geometry.output_layers_present() is True


def test_output_layers_present_false_when_map_has_no_output_layers(monkeypatch):
    """Verify a map with only basemaps reports absent (offer fresh start)."""

    monkeypatch.setattr(geometry, "arcpy", _map_arcpy(["Topographic", "World Imagery"]))

    assert geometry.output_layers_present() is False


def test_output_layers_present_true_when_probe_unavailable(monkeypatch):
    """Verify a probe failure is conservative and never suppresses a resume."""

    monkeypatch.setattr(geometry, "arcpy", _map_arcpy([], raise_err=True))

    assert geometry.output_layers_present() is True


def test_redraw_experiment_volatile_overlay_adds_symbolized_map_layer(monkeypatch):
    """Verify the volatile overlay probe uses a valid display-state map layer."""

    calls = []
    layer = SimpleNamespace(name=geometry.VOLATILE_OVERLAY_LAYER, visible=True, definitionQuery="", transparency=None)
    fake_map = SimpleNamespace(listLayers=lambda: [], addDataFromPath=lambda source: calls.append(("add", source)) or layer)
    fake = SimpleNamespace(
        mp=SimpleNamespace(ArcGISProject=lambda current: SimpleNamespace(activeMap=fake_map)),
        RefreshLayer=lambda name: calls.append(("refresh", name)),
    )
    monkeypatch.setattr(geometry, "arcpy", fake)
    monkeypatch.setattr(geometry, "apply_simple_symbology", lambda target, key, messages: calls.append(("sym", target.name, key)))
    messages = CapturingMessages()

    geometry.run_redraw_experiment(_paths(), messages, "volatile-overlay", layer_names={geometry.DISTRICTS}, dirty_scope="districts", mode="district-readd")

    assert ("add", "districts") in calls
    assert layer.definitionQuery == "display_state = 'daily_pressure'"
    assert ("sym", "Permit Office Volatile Overlay", "district_display") in calls
    assert ("refresh", "Permit Office Volatile Overlay") in calls
    assert any("name=volatile-overlay path=volatile-overlay status=ok" in line for line in messages.messages)


def test_redraw_experiment_volatile_overlay_reuses_existing_symbology(monkeypatch):
    """Verify hot volatile overlay refresh avoids reapplying symbology."""

    calls = []
    layer = SimpleNamespace(name=geometry.VOLATILE_OVERLAY_LAYER, visible=True, definitionQuery="", transparency=None)
    fake_map = SimpleNamespace(listLayers=lambda: [layer], addDataFromPath=lambda source: calls.append(("add", source)))
    fake = SimpleNamespace(
        mp=SimpleNamespace(ArcGISProject=lambda current: SimpleNamespace(activeMap=fake_map)),
        RefreshLayer=lambda name: calls.append(("refresh", name)),
    )
    monkeypatch.setattr(geometry, "arcpy", fake)
    monkeypatch.setattr(geometry, "apply_simple_symbology", lambda target, key, messages: calls.append(("sym", target.name, key)))
    messages = CapturingMessages()

    geometry.run_redraw_experiment(_paths(), messages, "volatile-overlay", layer_names={geometry.DISTRICTS}, dirty_scope="districts", mode="district-readd")

    assert ("add", "districts") not in calls
    assert layer.definitionQuery == "display_state = 'daily_pressure'"
    assert not any(call[0] == "sym" for call in calls)
    assert ("refresh", "Permit Office Volatile Overlay") in calls


def test_redraw_experiment_predrawn_swap_toggles_snapshot_visibility(monkeypatch):
    """Verify the pre-drawn swap probe toggles candidate snapshot layers."""

    active = SimpleNamespace(name="Permit Office Predrawn Active", visible=True)
    idle = SimpleNamespace(name="Permit Office Predrawn Idle", visible=True)
    other = SimpleNamespace(name=geometry.DISTRICTS, visible=True)
    calls = []
    fake_map = SimpleNamespace(listLayers=lambda: [active, idle, other])
    fake = SimpleNamespace(
        management=SimpleNamespace(MakeFeatureLayer=lambda source, name, where: calls.append(("make", source, name, where))),
        mp=SimpleNamespace(ArcGISProject=lambda current: SimpleNamespace(activeMap=fake_map)),
        RefreshLayer=lambda name: calls.append(("refresh", name)),
    )
    monkeypatch.setattr(geometry, "arcpy", fake)
    messages = CapturingMessages()

    geometry.run_redraw_experiment(_paths(), messages, "predrawn-swap", layer_names={geometry.DISTRICTS}, dirty_scope="districts", mode="district-readd")

    assert active.visible is True
    assert idle.visible is False
    assert ("refresh", "Permit Office Predrawn Active") in calls
    assert any("path=predrawn-swap status=ok" in line for line in messages.messages)


def test_redraw_experiment_predrawn_swap_seeds_symbolized_snapshot_layers(monkeypatch):
    """Verify pre-drawn seed creates durable map layers with display-state symbology."""

    calls = []
    layers = []

    def add_data(source):
        layer = SimpleNamespace(name=f"raw-{len(layers)}", visible=True, definitionQuery="", transparency=None)
        layers.append(layer)
        calls.append(("add", source))
        return layer

    fake_map = SimpleNamespace(listLayers=lambda: [], addDataFromPath=add_data)
    fake = SimpleNamespace(
        mp=SimpleNamespace(ArcGISProject=lambda current: SimpleNamespace(activeMap=fake_map)),
        RefreshLayer=lambda name: calls.append(("refresh", name)),
    )
    monkeypatch.setattr(geometry, "arcpy", fake)
    monkeypatch.setattr(geometry, "apply_simple_symbology", lambda target, key, messages: calls.append(("sym", target.name, key)))
    messages = CapturingMessages()

    geometry.run_redraw_experiment(_paths(), messages, "predrawn-swap", layer_names={geometry.DISTRICTS}, dirty_scope="districts", mode="district-readd")

    assert [layer.name for layer in layers] == ["Permit Office Predrawn Active", "Permit Office Predrawn Idle"]
    assert [layer.visible for layer in layers] == [True, False]
    assert all(layer.definitionQuery == "1=1" for layer in layers)
    assert ("sym", "Permit Office Predrawn Active", "district_display") in calls
    assert ("sym", "Permit Office Predrawn Idle", "district_display") in calls
    assert ("refresh", "Permit Office Predrawn Active") in calls
    assert any("path=predrawn-swap status=seeded" in line for line in messages.messages)


def test_redraw_experiment_alt_refresh_tries_non_readd_paths(monkeypatch):
    """Verify the alt-refresh probe tries query, visibility, CIM, and temp-layer paths."""

    calls = []

    class Layer:
        def __init__(self, name):
            self.name = name
            self.visible = True
            self.definitionQuery = ""

        def getDefinition(self, version):
            calls.append(("getDefinition", self.name, version))
            return SimpleNamespace()

        def setDefinition(self, definition):
            calls.append(("setDefinition", self.name, definition))

    layer = Layer(geometry.DISTRICTS)
    fake_map = SimpleNamespace(listLayers=lambda: [layer])
    fake = SimpleNamespace(
        management=SimpleNamespace(
            MakeFeatureLayer=lambda source, name, where: calls.append(("make", source, name, where)),
            ApplySymbologyFromLayer=lambda target, source: calls.append(("symbology", getattr(target, "name", target), getattr(source, "name", source))),
        ),
        mp=SimpleNamespace(ArcGISProject=lambda current: SimpleNamespace(activeMap=fake_map)),
        RefreshLayer=lambda name: calls.append(("refresh", name)),
    )
    monkeypatch.setattr(geometry, "arcpy", fake)
    messages = CapturingMessages()

    geometry.run_redraw_experiment(_paths(), messages, "alt-refresh", layer_names={geometry.DISTRICTS}, dirty_scope="districts", mode="district-readd")

    assert layer.definitionQuery == ""
    assert layer.visible is True
    assert ("getDefinition", geometry.DISTRICTS, "V3") in calls
    assert any(call[0] == "setDefinition" and call[1] == geometry.DISTRICTS for call in calls)
    assert ("make", "districts", "Permit Office Alt Refresh View", "1=1") in calls
    assert ("symbology", geometry.DISTRICTS, geometry.DISTRICTS) in calls
    assert any("path=alt-refresh status=ok" in line for line in messages.messages)


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
