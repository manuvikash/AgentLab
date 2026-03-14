"""Sliding window context manager that keeps recent messages within a token budget."""

from __future__ import annotations

from agentlab.core.component import BaseContextManager
from agentlab.core.registry import register
from agentlab.models.schemas import Message

CHARS_PER_TOKEN_ESTIMATE = 4


@register("context", "sliding")
class SlidingWindowContext(BaseContextManager):
    """Keeps the system message plus the most recent messages that fit within a token budget.

    Uses a rough character-based estimate for token counting (4 chars ≈ 1 token).
    """

    def __init__(self, window_tokens: int = 8000, **kwargs: object) -> None:
        self._messages: list[Message] = []
        self._window_tokens = window_tokens

    def add(self, message: Message) -> None:
        self._messages.append(message)

    def get_messages(self, max_tokens: int | None = None) -> list[Message]:
        budget = max_tokens or self._window_tokens

        system_msgs = [m for m in self._messages if m.role == "system"]
        non_system = [m for m in self._messages if m.role != "system"]

        used = sum(self._estimate_tokens(m) for m in system_msgs)
        result: list[Message] = []

        for msg in reversed(non_system):
            cost = self._estimate_tokens(msg)
            if used + cost > budget:
                break
            result.insert(0, msg)
            used += cost

        return system_msgs + result

    def reset(self) -> None:
        self._messages.clear()

    @staticmethod
    def _estimate_tokens(msg: Message) -> int:
        return max(1, len(msg.content) // CHARS_PER_TOKEN_ESTIMATE)
