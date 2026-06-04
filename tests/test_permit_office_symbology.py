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
    """Capture ArcPy-style info and warning messages."""

    def __init__(self) -> None:
        """Initialize captured message buffers."""

        self.messages: list[str] = []
        self.warnings: list[str] = []

    def addMessage(self, text: str) -> None:
        """Record an informational ArcPy message."""

        self.messages.append(text)

    def addWarningMessage(self, text: str) -> None:
        """Record a warning ArcPy message."""

        self.warnings.append(text)


class FakeSymbology:
    """Minimal symbology object exposing renderer update state."""

    def __init__(self, renderer) -> None:
        """Store the renderer under test."""

        self.renderer = renderer
        self.updated_renderer: str | None = None

    def updateRenderer(self, renderer_name: str) -> None:
        """Record the requested ArcGIS renderer type."""

        self.updated_renderer = renderer_name


class FakeLayer:
    """Minimal ArcGIS layer double with symbology and label APIs."""

    def __init__(self, renderer, supports_symbology: bool = True) -> None:
        """Initialize fake layer state around one renderer."""

        self.name = "Fake Layer"
        self._supports_symbology = supports_symbology
        self._symbology = FakeSymbology(renderer)
        self.assigned_symbology = None
        self.symbology_assignment_count = 0
        self.transparency = None
        self.showLabels = False
        self.label_classes = [SimpleNamespace(expression="", visible=False)]

    def supports(self, capability: str) -> bool:
        """Return whether the fake layer claims a capability."""

        return capability == "SYMBOLOGY" and self._supports_symbology

    @property
    def symbology(self):
        """Return the fake symbology object."""

        return self._symbology

    @symbology.setter
    def symbology(self, value) -> None:
        """Record symbology assignments made by the helper."""

        self.assigned_symbology = value
        self.symbology_assignment_count += 1

    def listLabelClasses(self):
        """Return mutable fake label classes."""

        return self.label_classes


class FakeMap:
    """Minimal active-map double supporting layer removal and ordering."""

    def __init__(self, layers) -> None:
        """Store a mutable list of fake layers."""

        self.layers = list(layers)
        self.removed = []

    def listLayers(self):
        """Return the current fake layer list."""

        return list(self.layers)

    def removeLayer(self, layer) -> None:
        """Remove a layer and record its name."""

        self.removed.append(layer.name)
        self.layers.remove(layer)

    def moveLayer(self, reference_layer, move_layer, insert_position) -> None:
        """Move one fake layer before or after another."""

        self.layers.remove(move_layer)
        reference_index = self.layers.index(reference_layer)
        insert_index = reference_index if insert_position == "BEFORE" else reference_index + 1
        self.layers.insert(insert_index, move_layer)


class FakeCimLayer(FakeLayer):
    """Layer double exposing ArcGIS CIM definition methods."""

    def __init__(self, renderer) -> None:
        """Initialize CIM renderer state used by fallback tests."""

        super().__init__(renderer)
        self.cim_renderer = SimpleNamespace(fields=None, useDefaultSymbol=False, isDefaultSymbolVisible=False)
        self.cim_definition = SimpleNamespace(renderer=self.cim_renderer)
        self.requested_cim_versions: list[str] = []
        self.assigned_definition = None

    def getDefinition(self, cim_version: str):
        """Return the fake CIM definition and record requested version."""

        self.requested_cim_versions.append(cim_version)
        return self.cim_definition

    def setDefinition(self, definition) -> None:
        """Record the CIM definition assigned by the helper."""

        self.assigned_definition = definition


class FieldsListRenderer:
    """Renderer variant accepting list-valued fields."""

    def __init__(self) -> None:
        """Initialize renderer field and default-symbol state."""

        self.fields = None
        self.useDefaultSymbol = False


class FakeSymbol:
    """Mutable symbol object used for style assertions."""

    def __init__(self) -> None:
        """Initialize symbol color state."""

        self.color = None


class FakeItem:
    """Unique-value item double with value, label, and symbol."""

    def __init__(self, value: str) -> None:
        """Create one fake unique-value item."""

        self.values = [[value]]
        self.label = value
        self.symbol = FakeSymbol()


class FakeGroup:
    """Unique-value renderer group double."""

    def __init__(self, heading: str = "display_state") -> None:
        """Initialize a group heading and empty item list."""

        self.heading = heading
        self.items: list[FakeItem] = []


class StyledRenderer(FieldsListRenderer):
    """Renderer variant that supports value seeding and styling."""

    def __init__(self) -> None:
        """Initialize renderer groups, added-value capture, and default symbol."""

        super().__init__()
        self.groups = [FakeGroup()]
        self.added_values = None
        self.defaultSymbol = FakeSymbol()

    def addValues(self, values_or_items) -> None:
        """Add unique-value items to the first fake group."""

        self.added_values = values_or_items
        existing = {item.values[0][0] for item in self.groups[0].items}
        for value in values_or_items.get(self.groups[0].heading, []):
            if value not in existing:
                self.groups[0].items.append(FakeItem(value))


class FieldRenderer:
    """Renderer variant accepting only singular field assignment."""

    def __init__(self) -> None:
        """Initialize the singular field backing value."""

        self._field = None
        self.useDefaultSymbol = False

    @property
    def fields(self):
        """Return unsupported list-field state."""

        return None

    @fields.setter
    def fields(self, value) -> None:
        """Reject list-field assignment."""

        raise RuntimeError("fields is not supported")

    @property
    def field(self):
        """Return the singular renderer field."""

        return self._field

    @field.setter
    def field(self, value) -> None:
        """Accept singular field assignment."""

        self._field = value


class FieldsTupleRenderer:
    """Renderer variant accepting tuple-valued fields only."""

    def __init__(self) -> None:
        """Initialize tuple field state."""

        self._fields = None
        self.useDefaultSymbol = False

    @property
    def fields(self):
        """Return assigned tuple fields."""

        return self._fields

    @fields.setter
    def fields(self, value) -> None:
        """Reject list fields but accept tuple fields."""

        if isinstance(value, list):
            raise RuntimeError("list fields are not supported")
        self._fields = value


class RejectingRenderer:
    """Renderer variant that rejects all direct field setters."""

    @property
    def fields(self):
        """Expose unsupported fields property."""

        return None

    @fields.setter
    def fields(self, value) -> None:
        """Reject fields assignment."""

        raise RuntimeError("fields is not supported")

    @property
    def field(self):
        """Expose unsupported field property."""

        return None

    @field.setter
    def field(self, value) -> None:
        """Reject field assignment."""

        raise RuntimeError("field is not supported")


def test_district_layers_render_by_district_type_by_default():
    """Verify district layers default to identity-first district-type rendering."""

    from toolbox.permit_office_arcgis.symbology_config import RENDER_FIELD_BY_LAYER_KEY

    assert RENDER_FIELD_BY_LAYER_KEY["districts"] == "district_type"


def test_identity_transition_symbol_values_are_configured():
    """Verify identity transition render values are available."""

    from toolbox.permit_office_arcgis.symbology_config import SYMBOLS_BY_FIELD

    identity_symbols = SYMBOLS_BY_FIELD["identity_state"]
    assert {"stable", "vulnerable", "contested", "converted", "overextended"} <= set(identity_symbols)
    assert "district_type" in SYMBOLS_BY_FIELD


def test_identity_transition_symbol_style_gets_strong_outline():
    """Verify identity transition values get high-contrast outlines."""

    from toolbox.permit_office_arcgis.symbology_config import symbol_style_for

    style = symbol_style_for("districts", "contested")

    assert style["outline_color"] == [93, 48, 48, 100]
    assert style["outline_width"] == 3.2


def test_apply_simple_symbology_uses_district_type_for_districts():
    """Verify district layers render by district_type."""

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
    """Verify support layers render by display_state."""

    renderer = FieldsListRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "points", messages)

    assert renderer.fields == ["display_state"]
    assert layer.assigned_symbology is layer.symbology
    assert messages.warnings == []


def test_apply_simple_symbology_seeds_and_styles_district_type_classes():
    """Verify known district types receive labels and symbols."""

    renderer = StyledRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    items = {item.values[0][0]: item for item in renderer.groups[0].items}
    assert "residential" in items
    assert "mercantile" in items
    assert "industrial" in items
    assert "civic" in items
    assert "academic" in items
    assert "natural" in items
    assert items["residential"].label == "Residential"
    assert items["mercantile"].label == "Mercantile"
    assert items["industrial"].symbol.color == {"RGB": [174, 166, 154, 100]}
    assert items["residential"].symbol.outlineColor == {"RGB": [242, 238, 226, 100]}
    assert items["residential"].symbol.outlineWidth == 3.0
    assert renderer.defaultSymbol.color == {"RGB": [220, 220, 208, 100]}
    assert renderer.defaultSymbol.outlineColor == {"RGB": [242, 238, 226, 100]}
    assert renderer.defaultSymbol.outlineWidth == 3.0
    assert renderer.useDefaultSymbol is True
    assert layer.assigned_symbology is layer.symbology
    assert messages.warnings == []


def test_apply_simple_symbology_falls_back_to_field_attribute():
    """Verify symbology uses singular field when fields is unavailable."""

    renderer = FieldRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "points", messages)

    assert renderer.field == "display_state"
    assert layer.assigned_symbology is layer.symbology
    assert layer.symbology_assignment_count == 1
    assert messages.warnings == []


def test_apply_simple_symbology_falls_back_to_fields_tuple():
    """Verify symbology uses tuple fields when list fields fail."""

    renderer = FieldsTupleRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "points", messages)

    assert renderer.fields == ("display_state",)
    assert layer.assigned_symbology is layer.symbology
    assert layer.symbology_assignment_count == 1
    assert messages.warnings == []


def test_apply_simple_symbology_warns_once_when_no_field_api_works():
    """Verify direct renderer failures produce one useful warning."""

    layer = FakeLayer(RejectingRenderer())
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert layer.assigned_symbology is None
    assert len(messages.warnings) == 1
    assert "[SYM] WARN: unique-value symbology skipped for Fake Layer" in messages.warnings[0]
    assert "fields is not supported" in messages.warnings[0]


def test_apply_simple_symbology_falls_back_to_cim_field_setter():
    """Verify CIM fallback configures renderer fields."""

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
    """Verify layers without symbology support are skipped quietly."""

    layer = FakeLayer(FieldsListRenderer(), supports_symbology=False)
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert layer.assigned_symbology is None
    assert messages.warnings == []


def test_tune_layer_visibility_makes_zones_transparent():
    """Verify configured layer transparency is applied."""

    layer = FakeLayer(FieldsListRenderer())

    _tune_layer_visibility(layer, "zones")

    assert layer.transparency == 35


def test_configure_labels_turns_on_district_name_labels():
    """Verify district label classes display district names."""

    layer = FakeLayer(FieldsListRenderer())

    _configure_labels(layer, "districts")

    assert layer.showLabels is True
    assert layer.label_classes[0].expression == "$feature.district_name"
    assert layer.label_classes[0].visible is True


def test_remove_outputs_from_map_removes_stale_permit_layers(monkeypatch):
    """Verify stale Permit Office layers are removed from the active map."""

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
    """Verify map layer ordering keeps districts as the base layer."""

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
