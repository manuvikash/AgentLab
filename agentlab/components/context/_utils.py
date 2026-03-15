"""Shared utilities for context manager implementations."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable

from agentlab.models.schemas import Message

if TYPE_CHECKING:
    pass

CHARS_PER_TOKEN = 4

# Type alias used by both Summarising and Hierarchical context managers.
Summariser = Callable[[list[Message]], str]


def estimate_tokens(msg: Message) -> int:
    """Rough character-based token estimate (4 chars ≈ 1 token)."""
    return max(1, len(msg.content or "") // CHARS_PER_TOKEN)


def extractive_summariser(messages: list[Message]) -> str:
    """Default summariser: join role + first 200 chars of each message.

    Requires no external dependencies. Useful as a drop-in fallback when
    no LLM is available for summarisation.
    """
    parts: list[str] = []
    for m in messages:
        snippet = (m.content or "").replace("\n", " ")[:200].rstrip()
        parts.append(f"[{m.role}] {snippet}")
    return "\n".join(parts)


def async_summariser_from_llm(
    llm_fn: Callable[[list[Message]], object],
    prompt_prefix: str = "Summarise the following conversation concisely:\n",
) -> Summariser:
    """Wrap an *async* LLM call into a synchronous Summariser.

    Args:
        llm_fn: ``async`` callable that accepts a list of Messages and returns
            an object with a ``.content`` attribute (e.g. ``LLMResponse``).
        prompt_prefix: text prepended to the extractive summary before sending
            to the LLM, so the model understands what to do.

    Example::

        async def my_llm(messages):
            return await llm_client.generate(messages)

        ctx = SumarisingContext(summariser=async_summariser_from_llm(my_llm))

    .. warning::
        This helper uses :func:`asyncio.get_event_loop` and ``.run_until_complete``.
        It **must not** be called from inside a running event loop (e.g. directly
        inside an ``async def``).  To perform summarisation from within an async
        context pass an already-compacted ``asyncio.Future`` or use a thread
        executor instead.
    """

    def _sync_summariser(messages: list[Message]) -> str:
        extractive = extractive_summariser(messages)
        prompt_msg = Message(role="user", content=prompt_prefix + extractive)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already inside an event loop we can't block it.
                # Fall back to the extractive summary so callers don't crash.
                return extractive
            result = loop.run_until_complete(llm_fn([prompt_msg]))
        except RuntimeError:
            return extractive
        return getattr(result, "content", None) or extractive

    return _sync_summariser
