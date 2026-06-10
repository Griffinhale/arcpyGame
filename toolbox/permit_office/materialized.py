"""Dependency-keyed materialized view cache primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cache_keys import CacheLifetime, GenerationToken


@dataclass(frozen=True)
class MaterializedView:
    """A derived value tied to a dependency hash and generation."""

    name: str
    dependency_hash: str
    generation: GenerationToken
    value: Any


class MaterializedViewCache:
    """Small in-memory cache for derived dashboard/rules views."""

    def __init__(self):
        self._views: dict[str, MaterializedView] = {}

    def put(self, name: str, dependency_hash: str, generation: GenerationToken, value: Any) -> MaterializedView:
        view = MaterializedView(name, dependency_hash, generation, value)
        self._views[name] = view
        return view

    def get(
        self,
        name: str,
        dependency_hash: str,
        generation: GenerationToken,
        lifetime: CacheLifetime = CacheLifetime.DOCKET,
    ) -> Any | None:
        view = self._views.get(name)
        if view is None:
            return None
        if view.dependency_hash != dependency_hash:
            return None
        if not view.generation.matches(generation, lifetime):
            return None
        return view.value

    def invalidate(self, *names: str) -> None:
        if not names:
            self._views.clear()
            return
        for name in names:
            self._views.pop(name, None)
