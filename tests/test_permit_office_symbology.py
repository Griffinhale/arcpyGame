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

from toolbox.permit_office_arcgis.geometry import apply_simple_symbology


class FakeMessages:
    def __init__(self) -> None:
        self.warnings: list[str] = []

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

    def supports(self, capability: str) -> bool:
        return capability == "SYMBOLOGY" and self._supports_symbology

    @property
    def symbology(self):
        return self._symbology

    @symbology.setter
    def symbology(self, value) -> None:
        self.assigned_symbology = value


class FieldsListRenderer:
    def __init__(self) -> None:
        self.fields = None
        self.useDefaultSymbol = False


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


def test_apply_simple_symbology_uses_fields_list_when_supported():
    renderer = FieldsListRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert layer.symbology.updated_renderer == "UniqueValueRenderer"
    assert renderer.fields == ["display_state"]
    assert renderer.useDefaultSymbol is True
    assert layer.assigned_symbology is layer.symbology
    assert messages.warnings == []


def test_apply_simple_symbology_falls_back_to_field_attribute():
    renderer = FieldRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert renderer.field == "display_state"
    assert layer.assigned_symbology is layer.symbology
    assert messages.warnings == []


def test_apply_simple_symbology_falls_back_to_fields_tuple():
    renderer = FieldsTupleRenderer()
    layer = FakeLayer(renderer)
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert renderer.fields == ("display_state",)
    assert layer.assigned_symbology is layer.symbology
    assert messages.warnings == []


def test_apply_simple_symbology_warns_once_when_no_field_api_works():
    layer = FakeLayer(RejectingRenderer())
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert layer.assigned_symbology is None
    assert len(messages.warnings) == 1
    assert "[SYM] WARN: unique-value symbology skipped for Fake Layer" in messages.warnings[0]
    assert "fields is not supported" in messages.warnings[0]


def test_apply_simple_symbology_returns_quietly_without_symbology_support():
    layer = FakeLayer(FieldsListRenderer(), supports_symbology=False)
    messages = FakeMessages()

    apply_simple_symbology(layer, "districts", messages)

    assert layer.assigned_symbology is None
    assert messages.warnings == []
