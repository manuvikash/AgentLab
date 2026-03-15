"""Hierarchical context manager.

Maintains two tiers of non-system context:

* **Long-term summary** – a compressed representation of all messages
  that have been evicted from the tail.  Produced lazily in
  ``get_messages()`` by calling ``summariser`` on the accumulated evicted
  messages.  Re-computed only when new evictions have occurred since the
  last call.

* **Verbatim tail** – the most-recent ``tail_size`` non-system messages,
  kept word-for-word.

The layout returned by ``get_messages()`` is always::

    [system messages ...] [summary (if any)] [verbatim tail ...]

This mirrors how humans remember long conversations: a fuzzy high-level
memory of what happened earlier plus crisp recall of recent turns.

Usage::

    ctx = HierarchicalContext(tail_size=8)
    # With a custom LLM-based summariser:
    ctx = HierarchicalContext(
        tail_size=8,
        summariser=async_summariser_from_llm(my_llm_fn),
    )
"""

from __future__ import annotations

from agentlab.components.context._utils import (
    Summariser,
    estimate_tokens,
    extractive_summariser,
)
from agentlab.core.component import BaseContextManager
from agentlab.core.registry import register
from agentlab.models.schemas import Message

_SUMMARY_HEADER = "--- Long-term summary (earlier context) ---"


@register("context", "hierarchical")
class HierarchicalContext(BaseContextManager):
    """Two-tier context: compressed long-term summary + verbatim recent tail.

    Args:
        tail_size: maximum number of non-system messages kept verbatim
            (default 10).  When the tail exceeds this, the oldest entry is
            evicted to the long-term store.
        summariser: callable ``(list[Message]) -> str`` used to produce the
            long-term summary from all evicted messages.  Defaults to
            :func:`extractive_summariser`.
    """

    def __init__(
        self,
        tail_size: int = 10,
        summariser: Summariser | None = None,
        **kwargs: object,
    ) -> None:
        self._system: list[Message] = []
        self._tail: list[Message] = []
        # All messages that have been evicted from the tail, oldest first.
        self._evicted: list[Message] = []

        self._tail_size = max(1, tail_size)
        self._summariser: Summariser = summariser or extractive_summariser

        # Lazy cache: only regenerate when new evictions have occurred.
        self._summary_cache: str | None = None
        self._evicted_dirty: bool = False

    # ------------------------------------------------------------------
    # BaseContextManager interface
    # ------------------------------------------------------------------

    def add(self, message: Message) -> None:
        if message.role == "system":
            self._system.append(message)
            return

        self._tail.append(message)

        # Evict oldest tail entries until within the size limit.
        while len(self._tail) > self._tail_size:
            self._evicted.append(self._tail.pop(0))
            self._evicted_dirty = True

    def get_messages(self, max_tokens: int | None = None) -> list[Message]:
        # Recompute the long-term summary only when something new was evicted.
        if self._evicted_dirty:
            self._summary_cache = self._summariser(self._evicted)
            self._evicted_dirty = False

        result: list[Message] = list(self._system)

        if self._summary_cache:
            result.append(
                Message(
                    role="user",
                    content=f"{_SUMMARY_HEADER}\n{self._summary_cache}",
                )
            )

        # Honor max_tokens by trimming the tail if it alone would overflow.
        tail = list(self._tail)
        if max_tokens is not None:
            system_cost = sum(estimate_tokens(m) for m in self._system)
            summary_cost = (
                estimate_tokens(result[-1]) if self._summary_cache else 0
            )
            tail_budget = max_tokens - system_cost - summary_cost
            trimmed: list[Message] = []
            used = 0
            for msg in reversed(tail):
                cost = estimate_tokens(msg)
                if used + cost > tail_budget:
                    break
                trimmed.insert(0, msg)
                used += cost
            tail = trimmed

        result.extend(tail)
        return result

    def reset(self) -> None:
        self._system.clear()
        self._tail.clear()
        self._evicted.clear()
        self._summary_cache = None
        self._evicted_dirty = False
