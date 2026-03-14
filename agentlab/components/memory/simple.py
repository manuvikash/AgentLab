"""Simple in-memory key-value store."""

from __future__ import annotations

from typing import Any

from agentlab.core.component import BaseMemory
from agentlab.core.registry import register


@register("memory", "simple")
class SimpleMemory(BaseMemory):
    """Dictionary-backed memory with basic substring search."""

    def __init__(self, **kwargs: object) -> None:
        self._store: dict[str, Any] = {}

    def store(self, key: str, value: Any) -> None:
        self._store[key] = value

    def retrieve(self, key: str) -> Any | None:
        return self._store.get(key)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, Any]]:
        query_lower = query.lower()
        matches = [
            (k, v)
            for k, v in self._store.items()
            if query_lower in k.lower() or query_lower in str(v).lower()
        ]
        return matches[:top_k]

    def clear(self) -> None:
        self._store.clear()
