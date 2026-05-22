"""Pure tests for ArcGIS Pro symbology API compatibility shims."""

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

from toolbox.permit_office_arcgis.geometry import apply_simple_symbology, remove_outputs_from_map, _configure_labels, _order_output_layers, _tune_layer_visibility


class FakeMessages:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.warnings: list[str] = []

    def addMessage(self, text: str) -> None:
        self.messages.append(text)

    def addWarningMessage(self, text: str) -> None:
        self.warnings.append(text)


class FakeSymbology:
    def __init__(self, renderer) -> None:
        self.renderer = renderer
        self.updated_renderer: str | None = None

    def updateRenderer(self, renderer_name: str) -> None:
        self.updated_renderer = renderer_name


class FakeLayer:
    def __init__(self, renderer, supports_symbology: bool = True) -> None:
        self.name = "Fake Layer"
        self._supports_symbology = supports_symbology
        self._symbology = FakeSymbology(renderer)
        self.assigned_symbology = None
        self.symbology_assignment_count = 0
        self.transparency = None
        self.showLabels = False
        self.label_classes = [SimpleNamespace(expression="", visible=False)]

    def supports(self, capability: str) -> bool:
        return capability == "SYMBOLOGY" and self._supports_symbology

    @property
    def symbology(self):
        return self._symbology

    @symbology.setter
    def symbology(self, value) -> None:
        self.assigned_symbology = value
        self.symbology_assignment_count += 1

    def listLabelClasses(self):
        return self.label_classes


class FakeMap:
    def __init__(self, layers) -> None:
        self.layers = list(layers)
        self.removed = []

    def listLayers(self):
        return list(self.layers)

    def removeLayer(self, layer) -> None:
        self.removed.append(layer.name)
        self.layers.remove(layer)

    def moveLayer(self, reference_layer, move_layer, insert_position) -> None:
        self.layers.remove(move_layer)
        reference_index = self.layers.index(reference_layer)
        insert_index = reference_index if insert_position == "BEFORE" else reference_index + 1
        self.layers.insert(insert_index, move_layer)


class FakeCimLayer(FakeLayer):
    def __init__(self, renderer) -> None:
        super().__init__(renderer)
        self.cim_renderer = SimpleNamespace(fields=None, useDefaultSymbol=False, isDefaultSymbolVisible=False)
        self.cim_definition = SimpleNamespace(renderer=self.cim_renderer)
        self.requested_cim_versions: list[str] = []
        self.assigned_definition = None

    def getDefinition(self, cim_version: str):
        self.requested_cim_versions.append(cim_version)
        return self.cim_definition

    def setDefinition(self, definition) -> None:
        self.assigned_definition = definition


class FieldsListRenderer:
    def __init__(self) -> None:
        self.fields = None
        self.useDefaultSymbol = False


class FakeSymbol:
    def __init__(self) -> None:
        self.color = None


class FakeItem:
    def __init__(self, value: str) -> None:
        self.values = [[value]]
        self.label = value
        self.symbol = FakeSymbol()


class FakeGroup:
    def __init__(self, heading: str = "display_state") -> None:
        self.heading = heading
        self.items: list[FakeItem] = []


class StyledRenderer(FieldsListRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.groups = [FakeGroup()]
        self.added_values = None

    def addValues(self, values_or_items) -> None:
        self.added_values = values_or_items
        existing = {item.values[0][0] for item in self.groups[0].items}
        for value in values_or_items.get(self.groups[0].heading, []):
            if value not in existing:
                self.groups[0].items.append(FakeItem(value))


class FieldRenderer:
    def __init__(self) -> None:
        self._field = None
        self.useDefaultSymbol = False

    @property
    def fields(self):
        return None

    @fields.setter
    def fields(self, value) -> None:
        raise RuntimeError("fields is not supported")

    @property
    def field(self):
        return self._field

    @field.setter
    def field(self, value) -> None:
        self._field = value


class FieldsTupleRenderer:
    def __init__(self) -> None:
        self._fields = None
        self.useDefaultSymbol = False

    @property
    def fields(self):
        return self._fields

    @fields.setter
    def fields(self, value) -> None:
        if isinstance(value, list):
            raise RuntimeError("list fields are not supported")
        self._fields = value


class RejectingRenderer:
    @property
    def fields(self):
        return None

    @fields.setter
    def fields(self, value) -> None:
        raise RuntimeError("fields is not supported")

    @property
    def field(self):
        return None

    @field.setter
    def field(self, value) -> None:
        raise RuntimeError("field is not supported")


def test_apply_simple_symbology_uses_district_type_for_districts():
    renderer = FieldsListRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert layer.symbology.updated_renderer == "UniqueValueRenderer"
    assert renderer.fields == ["district_type"]
    assert renderer.useDefaultSymbol is True
    assert layer.assigned_symbology is layer.symbology
    assert layer.symbology_assignment_count == 1
    assert messages.warnings == []


def test_apply_simple_symbology_uses_display_state_for_support_layers():
    renderer = FieldsListRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "points", messages)

    assert renderer.fields == ["display_state"]
    assert layer.assigned_symbology is layer.symbology
    assert messages.warnings == []


def test_apply_simple_symbology_seeds_and_styles_display_state_classes():
    renderer = StyledRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    items = {item.values[0][0]: item for item in renderer.groups[0].items}
    assert "residential" in items
    assert "academic" in items
    assert "natural" in items
    assert items["residential"].label == "Residential"
    assert items["academic"].symbol.color == {"RGB": [176, 160, 211, 100]}
    assert items["residential"].symbol.outlineColor == {"RGB": [242, 238, 226, 100]}
    assert items["residential"].symbol.outlineWidth == 3.0
    assert renderer.useDefaultSymbol is True
    assert layer.assigned_symbology is layer.symbology
    assert messages.warnings == []


def test_apply_simple_symbology_falls_back_to_field_attribute():
    renderer = FieldRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "points", messages)

    assert renderer.field == "display_state"
    assert layer.assigned_symbology is layer.symbology
    assert layer.symbology_assignment_count == 1
    assert messages.warnings == []


def test_apply_simple_symbology_falls_back_to_fields_tuple():
    renderer = FieldsTupleRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "points", messages)

    assert renderer.fields == ("display_state",)
    assert layer.assigned_symbology is layer.symbology
    assert layer.symbology_assignment_count == 1
    assert messages.warnings == []


def test_apply_simple_symbology_warns_once_when_no_field_api_works():
    layer = FakeLayer(RejectingRenderer())
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert layer.assigned_symbology is None
    assert len(messages.warnings) == 1
    assert "[SYM] WARN: unique-value symbology skipped for Fake Layer" in messages.warnings[0]
    assert "fields is not supported" in messages.warnings[0]


def test_apply_simple_symbology_falls_back_to_cim_field_setter():
    layer = FakeCimLayer(RejectingRenderer())
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert layer.assigned_symbology is layer.symbology
    assert layer.symbology_assignment_count == 1
    assert layer.requested_cim_versions == ["V3"]
    assert layer.cim_renderer.fields == ["district_type"]
    assert layer.cim_renderer.useDefaultSymbol is True
    assert layer.cim_renderer.isDefaultSymbolVisible is True
    assert layer.assigned_definition is layer.cim_definition
    assert messages.warnings == []


def test_apply_simple_symbology_returns_quietly_without_symbology_support():
    layer = FakeLayer(FieldsListRenderer(), supports_symbology=False)
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert layer.assigned_symbology is None
    assert messages.warnings == []


def test_tune_layer_visibility_makes_zones_transparent():
    layer = FakeLayer(FieldsListRenderer())

    _tune_layer_visibility(layer, "zones")

    assert layer.transparency == 35


def test_configure_labels_turns_on_district_cell_labels():
    layer = FakeLayer(FieldsListRenderer())

    _configure_labels(layer, "districts")

    assert layer.showLabels is True
    assert layer.label_classes[0].expression == "$feature.cell_id"
    assert layer.label_classes[0].visible is True


def test_remove_outputs_from_map_removes_stale_permit_layers(monkeypatch):
    stale = [FakeLayer(FieldsListRenderer()) for _ in range(5)]
    stale[0].name = "PermitDistricts"
    stale[1].name = "PermitPoints"
    stale[2].name = "PermitLines"
    stale[3].name = "PermitZones"
    stale[4].name = "OtherLayer"
    fake_map = FakeMap(stale)
    fake_arcpy = SimpleNamespace(
        mp=SimpleNamespace(ArcGISProject=lambda current: SimpleNamespace(activeMap=fake_map)),
        AddMessage=lambda text: None,
        AddWarning=lambda text: None,
    )
    monkeypatch.setattr("toolbox.permit_office_arcgis.geometry.arcpy", fake_arcpy)
    messages = FakeMessages()

    remove_outputs_from_map(messages)

    assert fake_map.removed == ["PermitDistricts", "PermitPoints", "PermitLines", "PermitZones"]
    assert [layer.name for layer in fake_map.layers] == ["OtherLayer"]
    assert messages.messages == ["[MAP] removed 4 stale Permit Office layer(s)"]


def test_order_output_layers_keeps_lines_on_top_and_districts_on_bottom():
    layers = [FakeLayer(FieldsListRenderer()) for _ in range(4)]
    for layer, name in zip(layers, ["PermitDistricts", "PermitZones", "PermitPoints", "PermitLines"]):
        layer.name = name
    existing = {layer.name: layer for layer in layers}
    fake_map = FakeMap(layers)

    _order_output_layers(fake_map, existing)

    assert [layer.name for layer in fake_map.layers] == [
        "PermitLines",
        "PermitPoints",
        "PermitZones",
        "PermitDistricts",
    ]
