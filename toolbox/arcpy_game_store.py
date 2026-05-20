"""ArcPy-backed persistence store for Survey Sweeper.

The module is importable without ArcPy. ``ArcPyStore`` imports ArcPy lazily so
the pure rules/action tests still run in ordinary Python, while ArcGIS Pro can
use the same Store-shaped seam exercised by Gate B.
"""

from __future__ import annotations

from dataclasses import fields
import os
import re
from typing import Any, Iterable

from toolbox import arcpy_game_rules as rules


BOARD_FC_NAME = "SurveySweeper_Board"
STATE_TABLE_NAME = "SurveySweeper_State"
ADJACENCY_TABLE_NAME = "SurveySweeper_Adjacency"
LOG_TABLE_NAME = "SurveySweeper_Log"

BOARD_FIELDS = [
    ("cell_id", "TEXT", 16),
    ("row_idx", "LONG", None),
    ("col_idx", "LONG", None),
    ("is_hazard", "SHORT", None),
    ("revealed", "SHORT", None),
    ("flagged", "SHORT", None),
    ("neighbor_count", "LONG", None),
    ("turn_revealed", "LONG", None),
    ("display_state", "TEXT", 32),
    ("notes", "TEXT", 255),
    ("hazard_hit", "SHORT", None),
]

STATE_FIELDS = [
    ("mode", "TEXT", 32),
    ("status", "TEXT", 32),
    ("seed", "LONG", None),
    ("board_rows", "LONG", None),
    ("board_cols", "LONG", None),
    ("hazard_count", "LONG", None),
    ("safe_revealed_count", "LONG", None),
    ("flags_count", "LONG", None),
    ("action_count", "LONG", None),
    ("last_message", "TEXT", 1024),
]

ADJACENCY_FIELDS = [
    ("cell_id", "TEXT", 16),
    ("neighbor_id", "TEXT", 16),
    ("touch_type", "TEXT", 16),
    ("weight", "DOUBLE", None),
]

LOG_FIELDS = [
    ("action", "TEXT", 64),
    ("target_cell_ids", "TEXT", 512),
    ("result", "TEXT", 2048),
    ("gp_operation", "TEXT", 512),
    ("status", "TEXT", 32),
    ("action_count", "LONG", None),
    ("ok", "SHORT", None),
]

REQUIRED_DATASETS = {
    BOARD_FC_NAME,
    STATE_TABLE_NAME,
    ADJACENCY_TABLE_NAME,
    LOG_TABLE_NAME,
}


class StoreSchemaError(RuntimeError):
    """Raised when the persisted game schema is absent, stale, or wrong."""


class ArcPyStore:
    """ArcPy implementation of the Store contract consumed by actions."""

    def __init__(
        self,
        gdb_path: str,
        *,
        layer: Any | None = None,
        arcpy_module: Any | None = None,
        spatial_reference: Any | None = None,
        cell_size: float = 100.0,
    ) -> None:
        self.gdb_path = gdb_path
        self.layer = layer
        self._arcpy = arcpy_module
        self.spatial_reference = spatial_reference
        self.cell_size = cell_size

    @property
    def board_fc(self) -> str:
        return os.path.join(self.gdb_path, BOARD_FC_NAME)

    @property
    def state_table(self) -> str:
        return os.path.join(self.gdb_path, STATE_TABLE_NAME)

    @property
    def adjacency_table(self) -> str:
        return os.path.join(self.gdb_path, ADJACENCY_TABLE_NAME)

    @property
    def log_table(self) -> str:
        return os.path.join(self.gdb_path, LOG_TABLE_NAME)

    @property
    def arcpy(self) -> Any:
        if self._arcpy is None:
            import arcpy  # type: ignore[import-not-found]

            self._arcpy = arcpy
        return self._arcpy

    def ensure_schema(self) -> None:
        """Create the gdb, datasets, fields, and indexes idempotently."""
        arcpy = self.arcpy
        folder = os.path.dirname(self.gdb_path)
        name = os.path.basename(self.gdb_path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        if not arcpy.Exists(self.gdb_path):
            arcpy.management.CreateFileGDB(folder, name)

        if not arcpy.Exists(self.board_fc):
            sr = self.spatial_reference
            if sr is None and hasattr(arcpy, "SpatialReference"):
                sr = arcpy.SpatialReference(3857)
            arcpy.management.CreateFeatureclass(
                self.gdb_path,
                BOARD_FC_NAME,
                "POLYGON",
                spatial_reference=sr,
            )
        for table_name in (STATE_TABLE_NAME, ADJACENCY_TABLE_NAME, LOG_TABLE_NAME):
            table_path = os.path.join(self.gdb_path, table_name)
            if not arcpy.Exists(table_path):
                arcpy.management.CreateTable(self.gdb_path, table_name)

        self._ensure_fields(self.board_fc, BOARD_FIELDS)
        self._ensure_fields(self.state_table, STATE_FIELDS)
        self._ensure_fields(self.adjacency_table, ADJACENCY_FIELDS)
        self._ensure_fields(self.log_table, LOG_FIELDS)
        self._ensure_index(self.board_fc, ["cell_id"], "idx_ss_board_cell_id", unique=True)
        self._ensure_index(self.adjacency_table, ["cell_id"], "idx_ss_adj_cell_id")
        self._ensure_index(self.adjacency_table, ["neighbor_id"], "idx_ss_adj_neighbor_id")
        self._ensure_index(self.state_table, ["status"], "idx_ss_state_status")

    def assert_schema(self) -> None:
        """Validate that required datasets and fields are present."""
        arcpy = self.arcpy
        for path in (self.board_fc, self.state_table, self.adjacency_table, self.log_table):
            if not arcpy.Exists(path):
                raise StoreSchemaError(f"Missing Survey Sweeper dataset: {path}")
        for path, spec in (
            (self.board_fc, BOARD_FIELDS),
            (self.state_table, STATE_FIELDS),
            (self.adjacency_table, ADJACENCY_FIELDS),
            (self.log_table, LOG_FIELDS),
        ):
            existing = {field.name.lower() for field in arcpy.ListFields(path)}
            missing = [name for name, _ftype, _length in spec if name.lower() not in existing]
            if missing:
                raise StoreSchemaError(f"{path} is missing fields: {', '.join(missing)}")

    def clear_all(self) -> None:
        """Delete all rows while preserving dataset paths and schema."""
        self.assert_schema()
        arcpy = self.arcpy
        for path in (self.board_fc, self.state_table, self.adjacency_table, self.log_table):
            arcpy.management.DeleteRows(path)

    def read_selection(self) -> list[str]:
        """Return selected board cell IDs, rejecting absent or stale layers."""
        self.assert_schema()
        layer = self.layer
        if layer is None:
            raise StoreSchemaError("A current Survey Sweeper board layer is required.")
        source = self._layer_source(layer)
        if self._norm_path(source) != self._norm_path(self.board_fc):
            raise StoreSchemaError(
                f"Selected layer is not the current Survey Sweeper board: {source}"
            )

        desc = self.arcpy.Describe(layer)
        oid_field = getattr(desc, "OIDFieldName", None)
        selected_oids = normalize_fidset(getattr(desc, "FIDSet", None))
        if not oid_field or not selected_oids:
            return []

        where = "{field} IN ({oids})".format(
            field=self.arcpy.AddFieldDelimiters(source, oid_field),
            oids=",".join(str(oid) for oid in selected_oids),
        )
        with self.arcpy.da.SearchCursor(source, ["cell_id"], where_clause=where) as cursor:
            return [row[0] for row in cursor]

    def read_game(self) -> rules.SurveySweeperGame:
        self.assert_schema()
        cells: dict[str, rules.CellState] = {}
        with self.arcpy.da.SearchCursor(self.board_fc, _cell_field_names()) as cursor:
            for row in cursor:
                cell = _row_to_cell(row)
                cells[cell.cell_id] = cell

        state_rows = []
        with self.arcpy.da.SearchCursor(self.state_table, _state_field_names()) as cursor:
            for row in cursor:
                state_rows.append(row)
        if len(state_rows) != 1:
            raise StoreSchemaError(f"Expected exactly one game state row; found {len(state_rows)}.")
        state = _row_to_state(state_rows[0])

        adjacency = {cid: [] for cid in cells}
        with self.arcpy.da.SearchCursor(self.adjacency_table, _adjacency_field_names()) as cursor:
            for cell_id, neighbor_id, touch_type, weight in cursor:
                if cell_id in adjacency:
                    adjacency[cell_id].append(
                        rules.AdjacencyLink(
                            neighbor_id=neighbor_id,
                            touch_type=touch_type,
                            weight=float(weight),
                        )
                    )
        return rules.SurveySweeperGame(cells=cells, adjacency=adjacency, state=state)

    def write_full_game(self, game: rules.SurveySweeperGame) -> None:
        self.clear_all()
        self._insert_cells(game.cells.values())
        self.write_state(game.state)
        self._insert_adjacency(game.adjacency)

    def write_cells(self, changed_ids: list[str], game: rules.SurveySweeperGame) -> None:
        if not changed_ids:
            return
        self.assert_schema()
        where = "cell_id IN ({ids})".format(ids=",".join(_sql_text(cid) for cid in changed_ids))
        changed = set(changed_ids)
        updated: set[str] = set()
        with self.arcpy.da.UpdateCursor(
            self.board_fc,
            _cell_field_names(),
            where_clause=where,
        ) as cursor:
            for row in cursor:
                cid = row[0]
                if cid not in changed:
                    continue
                cursor.updateRow(_cell_to_row(game.cells[cid]))
                updated.add(cid)
        missing = sorted(changed - updated)
        if missing:
            raise StoreSchemaError(f"Could not update missing board cells: {', '.join(missing)}")

    def write_state(self, state: rules.GameState) -> None:
        self.assert_schema()
        arcpy = self.arcpy
        arcpy.management.DeleteRows(self.state_table)
        with arcpy.da.InsertCursor(self.state_table, _state_field_names()) as cursor:
            cursor.insertRow(_state_to_row(state))

    def append_log(self, payload: dict[str, object]) -> None:
        self.assert_schema()
        fields_ = [name for name, _ftype, _length in LOG_FIELDS]
        row = [
            payload.get("action", ""),
            payload.get("target_cell_ids", ""),
            payload.get("result", ""),
            payload.get("gp_operation", ""),
            payload.get("status", ""),
            payload.get("action_count", 0),
            _bool_to_short(payload.get("ok", True)),
        ]
        with self.arcpy.da.InsertCursor(self.log_table, fields_) as cursor:
            cursor.insertRow(row)

    def _ensure_fields(self, path: str, spec: list[tuple[str, str, int | None]]) -> None:
        existing = {field.name.lower() for field in self.arcpy.ListFields(path)}
        for name, field_type, length in spec:
            if name.lower() in existing:
                continue
            kwargs = {}
            if length is not None and field_type.upper() == "TEXT":
                kwargs["field_length"] = length
            self.arcpy.management.AddField(path, name, field_type, **kwargs)

    def _ensure_index(
        self,
        path: str,
        field_names: list[str],
        index_name: str,
        *,
        unique: bool = False,
    ) -> None:
        wanted = {name.lower() for name in field_names}
        for index in self.arcpy.ListIndexes(path) or []:
            indexed = {field.name.lower() for field in index.fields}
            if indexed == wanted:
                return
        unique_flag = "UNIQUE" if unique else "NON_UNIQUE"
        self.arcpy.management.AddIndex(path, field_names, index_name, unique_flag)

    def _insert_cells(self, cells: Iterable[rules.CellState]) -> None:
        with self.arcpy.da.InsertCursor(self.board_fc, ["SHAPE@", *_cell_field_names()]) as cursor:
            for cell in cells:
                cursor.insertRow([self._cell_geometry(cell), *_cell_to_row(cell)])

    def _insert_adjacency(self, adjacency: dict[str, list[rules.AdjacencyLink]]) -> None:
        with self.arcpy.da.InsertCursor(self.adjacency_table, _adjacency_field_names()) as cursor:
            for cell_id, links in adjacency.items():
                for link in links:
                    cursor.insertRow([cell_id, link.neighbor_id, link.touch_type, link.weight])

    def _cell_geometry(self, cell: rules.CellState) -> Any:
        arcpy = self.arcpy
        if not all(hasattr(arcpy, name) for name in ("Array", "Point", "Polygon")):
            return None
        sr = self.spatial_reference
        if sr is None and hasattr(arcpy, "SpatialReference"):
            sr = arcpy.SpatialReference(3857)
        x0 = cell.col_idx * self.cell_size
        y0 = cell.row_idx * self.cell_size
        pts = [
            arcpy.Point(x0, y0),
            arcpy.Point(x0 + self.cell_size, y0),
            arcpy.Point(x0 + self.cell_size, y0 + self.cell_size),
            arcpy.Point(x0, y0 + self.cell_size),
            arcpy.Point(x0, y0),
        ]
        return arcpy.Polygon(arcpy.Array(pts), sr)

    def _layer_source(self, layer: Any) -> str:
        desc = self.arcpy.Describe(layer)
        return str(getattr(desc, "catalogPath", None) or getattr(layer, "dataSource", None) or layer)

    @staticmethod
    def _norm_path(path: str) -> str:
        return os.path.normcase(os.path.normpath(str(path)))


def normalize_fidset(fidset: Any) -> list[int]:
    """Normalize ArcPy FIDSet variants into sorted unique object IDs."""
    if fidset is None:
        return []
    if isinstance(fidset, str):
        if not fidset.strip():
            return []
        parts = re.split(r"[;,]", fidset)
        out = []
        for part in parts:
            try:
                out.append(int(part.strip()))
            except ValueError:
                continue
        return sorted(set(out))
    if isinstance(fidset, (list, tuple, set, frozenset)):
        out = []
        for value in fidset:
            try:
                out.append(int(value))
            except (TypeError, ValueError):
                continue
        return sorted(set(out))
    try:
        return [int(fidset)]
    except (TypeError, ValueError):
        return []


def _cell_field_names() -> list[str]:
    return [field.name for field in fields(rules.CellState)]


def _state_field_names() -> list[str]:
    return [field.name for field in fields(rules.GameState)]


def _adjacency_field_names() -> list[str]:
    return ["cell_id", *[field.name for field in fields(rules.AdjacencyLink)]]


def _cell_to_row(cell: rules.CellState) -> list[Any]:
    return [
        cell.cell_id,
        cell.row_idx,
        cell.col_idx,
        _bool_to_short(cell.is_hazard),
        _bool_to_short(cell.revealed),
        _bool_to_short(cell.flagged),
        cell.neighbor_count,
        cell.turn_revealed,
        cell.display_state,
        cell.notes,
        _bool_to_short(cell.hazard_hit),
    ]


def _row_to_cell(row: Iterable[Any]) -> rules.CellState:
    values = list(row)
    return rules.CellState(
        cell_id=values[0],
        row_idx=int(values[1]),
        col_idx=int(values[2]),
        is_hazard=bool(values[3]),
        revealed=bool(values[4]),
        flagged=bool(values[5]),
        neighbor_count=int(values[6]),
        turn_revealed=int(values[7]),
        display_state=values[8],
        notes=values[9] or "",
        hazard_hit=bool(values[10]),
    )


def _state_to_row(state: rules.GameState) -> list[Any]:
    return [
        state.mode,
        state.status,
        state.seed,
        state.board_rows,
        state.board_cols,
        state.hazard_count,
        state.safe_revealed_count,
        state.flags_count,
        state.action_count,
        state.last_message,
    ]


def _row_to_state(row: Iterable[Any]) -> rules.GameState:
    values = list(row)
    return rules.GameState(
        mode=values[0],
        status=values[1],
        seed=int(values[2]),
        board_rows=int(values[3]),
        board_cols=int(values[4]),
        hazard_count=int(values[5]),
        safe_revealed_count=int(values[6]),
        flags_count=int(values[7]),
        action_count=int(values[8]),
        last_message=values[9] or "",
    )


def _bool_to_short(value: object) -> int:
    return 1 if bool(value) else 0


def _sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
