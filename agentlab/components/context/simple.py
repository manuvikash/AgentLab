"""Simple context manager that keeps the full message history."""

from __future__ import annotations

from agentlab.core.component import BaseContextManager
from agentlab.core.registry import register
from agentlab.models.schemas import Message


@register("context", "simple")
class SimpleContext(BaseContextManager):
    """Stores all messages without truncation."""

    def __init__(self, **kwargs: object) -> None:
        self._messages: list[Message] = []

    def add(self, message: Message) -> None:
        self._messages.append(message)

    def get_messages(self, max_tokens: int | None = None) -> list[Message]:
        return list(self._messages)

    def reset(self) -> None:
        self._messages.clear()
