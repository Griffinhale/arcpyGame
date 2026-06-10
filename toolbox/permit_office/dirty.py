"""Dirty-scope bitsets for Permit Office cache and redraw planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


DISTRICTS = 1
POINTS = 2
LINES = 4
ZONES = 8
DOCKET = 16
STATE = 32
PROJECTS = 64

_LAYER_BITS = {
    "districts": DISTRICTS,
    "points": POINTS,
    "lines": LINES,
    "zones": ZONES,
    "docket": DOCKET,
    "state": STATE,
    "projects": PROJECTS,
}
_BIT_LAYERS = {value: key for key, value in _LAYER_BITS.items()}


@dataclass(frozen=True)
class DistrictBitIndex:
    """Stable mapping between persisted cell ids and compact integer bits."""

    cell_to_bit: dict[str, int]

    @classmethod
    def from_cell_ids(cls, cell_ids: Iterable[str]) -> "DistrictBitIndex":
        ordered = sorted({str(cell_id) for cell_id in cell_ids})
        return cls({cell_id: 1 << index for index, cell_id in enumerate(ordered)})

    def to_bits(self, cell_ids: Iterable[str]) -> int:
        bits = 0
        for cell_id in cell_ids or ():
            bits |= self.cell_to_bit.get(str(cell_id), 0)
        return bits

    def from_bits(self, bits: int) -> tuple[str, ...]:
        return tuple(cell_id for cell_id, bit in sorted(self.cell_to_bit.items()) if bits & bit)


def layer_bits_from_names(names: Iterable[str]) -> int:
    """Return layer dirty bits for canonical lower-case names."""

    bits = 0
    for name in names or ():
        bits |= _LAYER_BITS.get(str(name).lower(), 0)
    return bits


def layer_names_from_bits(bits: int) -> tuple[str, ...]:
    """Return canonical layer names in stable bit order."""

    return tuple(_BIT_LAYERS[bit] for bit in sorted(_BIT_LAYERS) if bits & bit)
