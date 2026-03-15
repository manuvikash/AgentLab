"""Summarising context manager.

Keeps all messages in memory and, when the token budget is exceeded,
compresses the *oldest* non-system messages into a single summary message
while keeping the most-recent ``tail_ratio`` fraction verbatim.

The summary is **cached**: it is only recomputed when the split-point
between "old" and "recent" messages changes (i.e. when new messages arrive
and the tail advances forward).  This makes repeated ``get_messages()`` calls
cheap in the common case.

Usage::

    ctx = SumarisingContext(window_tokens=4096, tail_ratio=0.7)
    # With a custom LLM-based summariser:
    ctx = SumarisingContext(
        summariser=async_summariser_from_llm(my_llm_fn)
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

_SUMMARY_HEADER = "--- Summary of prior context ---"


@register("context", "summarising")
class SumarisingContext(BaseContextManager):
    """Compress old messages into a summary when the token budget is exceeded.

    Args:
        window_tokens: default token budget used when ``get_messages`` is
            called without an explicit ``max_tokens`` argument.
        tail_ratio: fraction of the *non-system* budget reserved for the
            verbatim recent tail (0 < tail_ratio < 1, default 0.7).
        summariser: callable ``(list[Message]) -> str`` that produces the
            compressed text.  Defaults to :func:`extractive_summariser`.
    """

    def __init__(
        self,
        window_tokens: int = 8000,
        tail_ratio: float = 0.7,
        summariser: Summariser | None = None,
        **kwargs: object,
    ) -> None:
        self._messages: list[Message] = []
        self._window_tokens = window_tokens
        self._tail_ratio = max(0.05, min(0.95, tail_ratio))
        self._summariser: Summariser = summariser or extractive_summariser

        # Cache state: recompute only when the split-point changes.
        self._cached_summary: str | None = None
        # We use the CPython id() of the first verbatim-tail message as a
        # lightweight fingerprint.  It changes whenever the tail advances.
        self._cache_key: int = -1

    # ------------------------------------------------------------------
    # BaseContextManager interface
    # ------------------------------------------------------------------

    def add(self, message: Message) -> None:
        self._messages.append(message)

    def get_messages(self, max_tokens: int | None = None) -> list[Message]:
        budget = max_tokens or self._window_tokens

        system_msgs = [m for m in self._messages if m.role == "system"]
        non_system = [m for m in self._messages if m.role != "system"]

        system_cost = sum(estimate_tokens(m) for m in system_msgs)
        remaining = budget - system_cost

        if remaining <= 0:
            return system_msgs

        # Fast path: everything fits without compression.
        if sum(estimate_tokens(m) for m in non_system) <= remaining:
            return system_msgs + non_system

        # Greedy tail fill: walk newest → oldest, fill tail_ratio of budget.
        tail_budget = max(1, int(remaining * self._tail_ratio))
        tail: list[Message] = []
        tail_cost = 0
        for msg in reversed(non_system):
            cost = estimate_tokens(msg)
            if tail_cost + cost > tail_budget:
                break
            tail.insert(0, msg)
            tail_cost += cost

        # Messages not included in the tail are candidates for summarisation.
        tail_ids = {id(m) for m in tail}
        old = [m for m in non_system if id(m) not in tail_ids]

        if not old:
            return system_msgs + tail

        # Recompute summary only when the split-point advances.
        cache_key = id(tail[0]) if tail else 0
        if self._cached_summary is None or self._cache_key != cache_key:
            self._cached_summary = self._summariser(old)
            self._cache_key = cache_key

        summary_msg = Message(
            role="user",
            content=f"{_SUMMARY_HEADER}\n{self._cached_summary}",
        )
        return system_msgs + [summary_msg] + tail

    def reset(self) -> None:
        self._messages.clear()
        self._cached_summary = None
        self._cache_key = -1
