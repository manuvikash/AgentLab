"""Compaction memory: automatically summarise old entries when the store grows too large.

When the number of entries exceeds ``threshold``, the oldest ``compact_ratio``
fraction of entries are passed to a *compactor* function that produces a single
summary string. That summary is stored as a special ``__compacted_N__`` entry
and the compacted entries are removed.

Two built-in compactors are provided:
- ``extractive_compactor`` (default): joins all key-value pairs into a concise text.
- ``truncating_compactor``: keeps only the tail of each value up to a char limit.

LLM-based async compaction is supported via an async wrapper — see
``async_compactor_from_llm()`` for an example of how to bridge async LLM calls.

Registration name: ``"compaction"``
"""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import Any, Callable

from agentlab.core.component import BaseMemory
from agentlab.core.registry import register

# Type alias for a sync compactor function
Compactor = Callable[[dict[str, Any]], str]


# ---------------------------------------------------------------------------
# Built-in compactors
# ---------------------------------------------------------------------------


def extractive_compactor(entries: dict[str, Any]) -> str:
    """Join all entries into a readable summary (default compactor)."""
    parts = [f"{k}: {v!s}" for k, v in entries.items()]
    return "Summary of prior context — " + " | ".join(parts)


def truncating_compactor(max_chars_per_entry: int = 120) -> Compactor:
    """Return a compactor that truncates each value to ``max_chars_per_entry`` chars."""

    def _compact(entries: dict[str, Any]) -> str:
        parts = []
        for k, v in entries.items():
            snippet = str(v)[:max_chars_per_entry]
            parts.append(f"{k}: {snippet}")
        return "Compacted — " + " | ".join(parts)

    return _compact


def async_compactor_from_llm(llm_fn: Any) -> Compactor:
    """
    Bridge an *async* LLM summarizer into a sync compactor.

    Usage::

        async def my_summarizer(text: str) -> str:
            response = await openai_client.chat(...)
            return response

        mem = CompactionMemory(
            compactor=async_compactor_from_llm(my_summarizer)
        )

    ``llm_fn`` must accept a single string (the concatenated entries text) and
    return an awaitable that resolves to a string summary.
    """
    import asyncio

    def _compact(entries: dict[str, Any]) -> str:
        text = "\n".join(f"{k}: {v}" for k, v in entries.items())
        prompt = f"Summarize these agent memory entries concisely:\n\n{text}"
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already inside an async context — use a new thread loop
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(asyncio.run, llm_fn(prompt))
                    return fut.result(timeout=60)
            return loop.run_until_complete(llm_fn(prompt))
        except Exception as exc:
            # Fall back to extractive summary on LLM failure
            return extractive_compactor(entries) + f" [LLM compaction failed: {exc}]"

    return _compact


# ---------------------------------------------------------------------------
# CompactionMemory
# ---------------------------------------------------------------------------


@register("memory", "compaction")
class CompactionMemory(BaseMemory):
    """Auto-compacting key-value memory.

    When ``len(store) > threshold``, the oldest ``ceil(threshold * compact_ratio)``
    entries are summarised into a single ``__compacted_N__`` entry and removed.

    Parameters:
        threshold: entry count that triggers compaction (default 50).
        compact_ratio: fraction of entries to compact on each trigger (default 0.5).
        compactor: callable ``(dict) -> str`` that summarises old entries.
                   Defaults to :func:`extractive_compactor`.
    """

    def __init__(
        self,
        threshold: int = 50,
        compact_ratio: float = 0.5,
        compactor: Compactor | None = None,
        **_: Any,
    ) -> None:
        if threshold < 2:
            raise ValueError("threshold must be >= 2")
        if not (0 < compact_ratio < 1):
            raise ValueError("compact_ratio must be in (0, 1)")
        self._threshold = threshold
        self._compact_ratio = compact_ratio
        self._compactor: Compactor = compactor or extractive_compactor
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._compaction_count = 0

    # ------------------------------------------------------------------
    # BaseMemory interface
    # ------------------------------------------------------------------

    def store(self, key: str, value: Any) -> None:
        """Store a value; triggers compaction if the store is over threshold."""
        self._store.pop(key, None)  # move to the recent end on update
        self._store[key] = value
        if len(self._store) > self._threshold:
            self._compact()

    def retrieve(self, key: str) -> Any | None:
        return self._store.get(key)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, Any]]:
        """Substring search across all entries (including compacted summaries)."""
        query_lower = query.lower()
        matches = [
            (k, v)
            for k, v in self._store.items()
            if query_lower in k.lower() or query_lower in str(v).lower()
        ]
        return matches[:top_k]

    def clear(self) -> None:
        self._store.clear()
        self._compaction_count = 0

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def compact(self) -> str:
        """Manually trigger one compaction pass. Returns the summary string."""
        return self._compact()

    def _compact(self) -> str:
        n_to_compact = max(1, math.ceil(len(self._store) * self._compact_ratio))
        # Extract oldest n_to_compact entries (front of OrderedDict)
        old_items: dict[str, Any] = {}
        keys = list(self._store.keys())
        for k in keys[:n_to_compact]:
            old_items[k] = self._store.pop(k)

        self._compaction_count += 1
        summary = self._compactor(old_items)
        summary_key = f"__compacted_{self._compaction_count}__"
        # Insert summary at the front (it represents older context)
        new_store: OrderedDict[str, Any] = OrderedDict({summary_key: summary})
        new_store.update(self._store)
        self._store = new_store
        return summary

    # ------------------------------------------------------------------
    # Extras
    # ------------------------------------------------------------------

    @property
    def compaction_count(self) -> int:
        """Number of compaction passes performed so far."""
        return self._compaction_count

    @property
    def size(self) -> int:
        return len(self._store)
