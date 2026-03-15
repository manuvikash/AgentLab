"""Sliding-window memory: keep only the N most recently written entries.

When the window is full, the oldest entry is evicted automatically.
Useful for agents where only recent context matters and old data can be forgotten
without a summary step.

Registration name: ``"sliding_window"``
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from agentlab.core.component import BaseMemory
from agentlab.core.registry import register


@register("memory", "sliding_window")
class SlidingWindowMemory(BaseMemory):
    """Bounded key-value memory that evicts oldest entries when full.

    Parameters:
        window: maximum number of entries to retain (default 100).
    """

    def __init__(self, window: int = 100, **_: Any) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        self._window = window
        # OrderedDict so we can efficiently pop from the front (oldest first)
        self._store: OrderedDict[str, Any] = OrderedDict()

    # ------------------------------------------------------------------
    # BaseMemory interface
    # ------------------------------------------------------------------

    def store(self, key: str, value: Any) -> None:
        """Insert or update a key. On update the entry moves to the most-recent end.
        If at capacity after insertion, the oldest entry is evicted.
        """
        # Remove if already present so it gets re-inserted at the "recent" end
        self._store.pop(key, None)
        self._store[key] = value
        # Evict oldest entries until within budget
        while len(self._store) > self._window:
            self._store.popitem(last=False)

    def retrieve(self, key: str) -> Any | None:
        return self._store.get(key)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, Any]]:
        """Substring search restricted to the current window (newest → oldest order)."""
        query_lower = query.lower()
        matches: list[tuple[str, Any]] = []
        # Iterate newest first
        for k, v in reversed(self._store.items()):
            if query_lower in k.lower() or query_lower in str(v).lower():
                matches.append((k, v))
            if len(matches) >= top_k:
                break
        return matches

    def clear(self) -> None:
        self._store.clear()

    # ------------------------------------------------------------------
    # Extras
    # ------------------------------------------------------------------

    @property
    def window(self) -> int:
        """Maximum entries retained."""
        return self._window

    @property
    def size(self) -> int:
        """Current number of stored entries."""
        return len(self._store)

    def keys(self) -> list[str]:
        """Return stored keys from oldest to newest."""
        return list(self._store.keys())
