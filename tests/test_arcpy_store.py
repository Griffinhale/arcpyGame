"""Gate C: ArcPy Store/schema tests with a fake ArcPy surface.

These tests do not require ArcGIS Pro. They verify the ArcPyStore contract and
the ArcPy calls we depend on so the same module can run under Pro-Python.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re

import pytest

from toolbox import arcpy_game_rules as rules
from toolbox import arcpy_game_store as store_mod

FAKE_GDB = r"E:\GIS\arcpyGame\game.gdb"
STALE_GDB = r"E:\GIS\arcpyGame\old.gdb"


@dataclass
class FakeField:
    name: str


@dataclass
class FakeIndex:
    fields: list[FakeField]


@dataclass
class FakeDescribe:
    catalogPath: str
    OIDFieldName: str = "OBJECTID"
    FIDSet: object = ""


class FakeLayer:
    def __init__(self, source: str, selected_oids: object = "") -> None:
        self.dataSource = source
        self.selected_oids = selected_oids


class FakeManagement:
    def __init__(self, arcpy: FakeArcpy) -> None:
        self.arcpy = arcpy

    def CreateFileGDB(self, folder: str, name: str) -> None:
        self.arcpy.gdbs.add(os.path.join(folder, name))

    def CreateFeatureclass(self, out_path: str, out_name: str, geometry_type: str, **kwargs) -> None:
        path = os.path.join(out_path, out_name)
        self.arcpy.datasets[path] = {"fields": {"OBJECTID"}, "rows": [], "indexes": []}

    def CreateTable(self, out_path: str, out_name: str) -> None:
        path = os.path.join(out_path, out_name)
        self.arcpy.datasets[path] = {"fields": {"OBJECTID"}, "rows": [], "indexes": []}

    def AddField(self, path: str, name: str, field_type: str, **kwargs) -> None:
        self.arcpy.datasets[path]["fields"].add(name)
        self.arcpy.calls.append(("AddField", path, name))

    def AddIndex(self, path: str, fields, index_name: str, unique: str = "NON_UNIQUE") -> None:
        names = fields if isinstance(fields, list) else [fields]
        self.arcpy.datasets[path]["indexes"].append(FakeIndex([FakeField(name) for name in names]))
        self.arcpy.calls.append(("AddIndex", path, tuple(names), unique))

    def DeleteRows(self, path: str) -> None:
        self.arcpy.datasets[path]["rows"].clear()
        self.arcpy.calls.append(("DeleteRows", path))


class FakeDA:
    def __init__(self, arcpy: FakeArcpy) -> None:
        self.arcpy = arcpy

    def InsertCursor(self, path: str, fields: list[str]):
        return FakeInsertCursor(self.arcpy, path, fields)

    def SearchCursor(self, path_or_layer, fields: list[str], where_clause: str | None = None):
        path = path_or_layer.dataSource if isinstance(path_or_layer, FakeLayer) else path_or_layer
        return FakeSearchCursor(self.arcpy, path, fields, where_clause)

    def UpdateCursor(self, path: str, fields: list[str], where_clause: str | None = None):
        return FakeUpdateCursor(self.arcpy, path, fields, where_clause)


class FakeInsertCursor:
    def __init__(self, arcpy: FakeArcpy, path: str, fields: list[str]) -> None:
        self.arcpy = arcpy
        self.path = path
        self.fields = fields

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def insertRow(self, row) -> None:
        data = dict(zip(self.fields, row))
        if "OBJECTID" not in data:
            data["OBJECTID"] = self.arcpy.next_oid(self.path)
        self.arcpy.datasets[self.path]["rows"].append(data)


class FakeSearchCursor:
    def __init__(self, arcpy: FakeArcpy, path: str, fields: list[str], where_clause: str | None) -> None:
        rows = arcpy.datasets[path]["rows"]
        self.rows = [_project(row, fields) for row in _filter_rows(rows, where_clause)]
        self.index = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.rows):
            raise StopIteration
        row = self.rows[self.index]
        self.index += 1
        return row


class FakeUpdateCursor:
    def __init__(self, arcpy: FakeArcpy, path: str, fields: list[str], where_clause: str | None) -> None:
        self.rows = _filter_rows(arcpy.datasets[path]["rows"], where_clause)
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
        return _project(self.current, self.fields)

    def updateRow(self, values) -> None:
        for field, value in zip(self.fields, values):
            self.current[field] = value


class FakeArcpy:
    def __init__(self) -> None:
        self.gdbs = set()
        self.datasets = {}
        self.calls = []
        self.management = FakeManagement(self)
        self.da = FakeDA(self)

    def Exists(self, path: str) -> bool:
        return path in self.gdbs or path in self.datasets

    def ListFields(self, path: str) -> list[FakeField]:
        return [FakeField(name) for name in sorted(self.datasets[path]["fields"])]

    def ListIndexes(self, path: str) -> list[FakeIndex]:
        return list(self.datasets[path]["indexes"])

    def Describe(self, value) -> FakeDescribe:
        if isinstance(value, FakeLayer):
            return FakeDescribe(value.dataSource, FIDSet=value.selected_oids)
        return FakeDescribe(str(value))

    def AddFieldDelimiters(self, source: str, field: str) -> str:
        return field

    def SpatialReference(self, factory_code: int):
        return ("SR", factory_code)

    def next_oid(self, path: str) -> int:
        return len(self.datasets[path]["rows"]) + 1


def test_ensure_schema_is_idempotent_for_gdb_datasets_fields_and_indexes():
    arcpy = FakeArcpy()
    store = store_mod.ArcPyStore(FAKE_GDB, arcpy_module=arcpy)

    store.ensure_schema()
    first_counts = _schema_counts(arcpy)
    store.ensure_schema()

    assert _schema_counts(arcpy) == first_counts
    assert set(arcpy.datasets) == {
        store.board_fc,
        store.state_table,
        store.adjacency_table,
        store.log_table,
    }
    assert "cell_id" in arcpy.datasets[store.board_fc]["fields"]
    assert any(
        index.fields[0].name == "cell_id"
        for index in arcpy.datasets[store.board_fc]["indexes"]
    )


def test_delete_rows_reset_preserves_paths_and_roundtrip_works():
    arcpy = FakeArcpy()
    store = store_mod.ArcPyStore(FAKE_GDB, arcpy_module=arcpy)
    game = rules.new_game("Tiny Demo", seed=2026)

    store.ensure_schema()
    store.write_full_game(game)
    assert len(arcpy.datasets[store.board_fc]["rows"]) == 25
    assert len(arcpy.datasets[store.adjacency_table]["rows"]) == 144

    loaded = store.read_game()
    assert loaded.state == game.state
    assert loaded.cells["R00C03"].is_hazard is True
    assert len(loaded.adjacency["R02C02"]) == 8

    before_paths = set(arcpy.datasets)
    store.clear_all()

    assert set(arcpy.datasets) == before_paths
    assert all(len(arcpy.datasets[path]["rows"]) == 0 for path in before_paths)


def test_write_cells_updates_only_changed_rows():
    arcpy = FakeArcpy()
    store = store_mod.ArcPyStore(FAKE_GDB, arcpy_module=arcpy)
    game = rules.new_game("Tiny Demo", seed=2026)
    store.ensure_schema()
    store.write_full_game(game)

    rules.reveal_cells(game, ["R00C00"])
    store.write_cells(["R00C00"], game)
    loaded = store.read_game()

    assert loaded.cells["R00C00"].revealed is True
    assert loaded.cells["R00C01"].revealed is False


def test_selected_layer_cursor_returns_only_selected_cell_ids():
    arcpy = FakeArcpy()
    store = store_mod.ArcPyStore(FAKE_GDB, arcpy_module=arcpy)
    store.ensure_schema()
    store.write_full_game(rules.new_game("Tiny Demo", seed=2026))
    store.layer = FakeLayer(store.board_fc, selected_oids="1;3;3")

    assert store.read_selection() == ["R00C00", "R00C02"]


def test_wrong_or_stale_layer_fails_safely():
    arcpy = FakeArcpy()
    store = store_mod.ArcPyStore(FAKE_GDB, arcpy_module=arcpy)
    store.ensure_schema()
    store.write_full_game(rules.new_game("Tiny Demo", seed=2026))
    store.layer = FakeLayer(os.path.join(STALE_GDB, store_mod.BOARD_FC_NAME), "1")

    with pytest.raises(store_mod.StoreSchemaError, match="not the current"):
        store.read_selection()


def test_normalize_fidset_variants():
    assert store_mod.normalize_fidset(None) == []
    assert store_mod.normalize_fidset("") == []
    assert store_mod.normalize_fidset("3;1,3;bad") == [1, 3]
    assert store_mod.normalize_fidset([2, "4", "bad"]) == [2, 4]
    assert store_mod.normalize_fidset(9) == [9]


def _schema_counts(arcpy: FakeArcpy) -> tuple[int, int, int]:
    field_count = sum(len(dataset["fields"]) for dataset in arcpy.datasets.values())
    index_count = sum(len(dataset["indexes"]) for dataset in arcpy.datasets.values())
    return len(arcpy.gdbs), field_count, index_count


def _project(row: dict[str, object], fields: list[str]) -> list[object]:
    return [row.get(field) for field in fields]


def _filter_rows(rows: list[dict[str, object]], where_clause: str | None) -> list[dict[str, object]]:
    if not where_clause:
        return list(rows)
    match = re.search(r"(\w+)\s+IN\s+\((.*)\)", where_clause)
    if not match:
        return list(rows)
    field = match.group(1)
    raw_values = [value.strip().strip("'") for value in match.group(2).split(",")]
    values = set(raw_values)
    coerced = {int(value) for value in raw_values if value.isdigit()}
    return [row for row in rows if row.get(field) in values or row.get(field) in coerced]
