"""Tests for SumarisingContext and HierarchicalContext."""

from __future__ import annotations

import pytest

from agentlab.components.context._utils import (
    async_summariser_from_llm,
    extractive_summariser,
)
from agentlab.components.context.hierarchical import HierarchicalContext
from agentlab.components.context.summarising import SumarisingContext
from agentlab.models.schemas import Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg(role: str, content: str) -> Message:
    return Message(role=role, content=content)


def _long(n: int = 200) -> str:
    """Return a string of *n* characters."""
    return "x" * n


# ---------------------------------------------------------------------------
# extractive_summariser
# ---------------------------------------------------------------------------

class TestExtractiveSummariser:
    def test_basic(self):
        msgs = [_msg("user", "hello"), _msg("assistant", "hi")]
        result = extractive_summariser(msgs)
        assert "[user]" in result
        assert "[assistant]" in result
        assert "hello" in result
        assert "hi" in result

    def test_truncates_long_content(self):
        msgs = [_msg("user", "a" * 500)]
        result = extractive_summariser(msgs)
        # Only first 200 chars should appear in the snippet
        assert len(result) < 400

    def test_handles_none_content(self):
        # Message with no content should not raise
        msg = Message(role="user", content=None)
        result = extractive_summariser([msg])
        assert "[user]" in result

    def test_empty_list(self):
        assert extractive_summariser([]) == ""


# ---------------------------------------------------------------------------
# SumarisingContext
# ---------------------------------------------------------------------------

class TestSumarisingContext:
    def test_all_messages_returned_when_within_budget(self):
        ctx = SumarisingContext(window_tokens=10_000)
        ctx.add(_msg("system", "Be helpful"))
        ctx.add(_msg("user", "Hi"))
        ctx.add(_msg("assistant", "Hello"))

        msgs = ctx.get_messages()
        assert len(msgs) == 3
        assert msgs[0].role == "system"

    def test_system_message_always_present(self):
        ctx = SumarisingContext(window_tokens=5)
        ctx.add(_msg("system", "sys"))
        for i in range(10):
            ctx.add(_msg("user", _long(200)))

        msgs = ctx.get_messages()
        assert msgs[0].role == "system"
        assert msgs[0].content == "sys"

    def test_summary_injected_when_over_budget(self):
        ctx = SumarisingContext(window_tokens=100, tail_ratio=0.7)
        ctx.add(_msg("system", "sys"))
        # Add many long messages to force compression
        for i in range(20):
            ctx.add(_msg("user", _long(100)))

        msgs = ctx.get_messages()
        summary_msgs = [m for m in msgs if m.role == "user" and "Summary" in (m.content or "")]
        assert len(summary_msgs) == 1, "Expected exactly one summary message"

    def test_recent_messages_are_verbatim(self):
        ctx = SumarisingContext(window_tokens=50, tail_ratio=0.7)
        ctx.add(_msg("system", "s"))
        for i in range(5):
            ctx.add(_msg("user", _long(100)))
        ctx.add(_msg("user", "LAST MESSAGE"))

        msgs = ctx.get_messages()
        contents = [m.content for m in msgs]
        assert any("LAST MESSAGE" in (c or "") for c in contents), (
            "Most recent message should be in the verbatim tail"
        )

    def test_summary_cache_is_reused(self):
        calls: list[int] = []

        def counting_summariser(messages):
            calls.append(len(messages))
            return extractive_summariser(messages)

        ctx = SumarisingContext(window_tokens=20, summariser=counting_summariser)
        ctx.add(_msg("system", "sys"))
        for i in range(10):
            ctx.add(_msg("user", _long(50)))

        ctx.get_messages()  # first call computes summary
        ctx.get_messages()  # second call should reuse cache
        ctx.get_messages()  # third call should reuse cache

        assert len(calls) == 1, f"Summariser called {len(calls)} times; expected 1 (cache reuse)"

    def test_summary_cache_invalidated_on_new_message(self):
        calls: list[int] = []

        def counting_summariser(messages):
            calls.append(1)
            return extractive_summariser(messages)

        ctx = SumarisingContext(window_tokens=20, summariser=counting_summariser)
        ctx.add(_msg("system", "s"))
        for i in range(10):
            ctx.add(_msg("user", _long(50)))

        ctx.get_messages()        # triggers compaction
        ctx.add(_msg("user", _long(50)))  # tail advances → split-point changes
        ctx.get_messages()        # should recompute

        assert len(calls) >= 2

    def test_reset_clears_state(self):
        ctx = SumarisingContext(window_tokens=10_000)
        ctx.add(_msg("user", "hi"))
        ctx.reset()
        assert ctx.get_messages() == []

    def test_custom_summariser_used(self):
        sentinel = "CUSTOM_SUMMARY_SENTINEL"

        ctx = SumarisingContext(window_tokens=20, summariser=lambda _: sentinel)
        ctx.add(_msg("system", "s"))
        for i in range(10):
            ctx.add(_msg("user", _long(50)))

        msgs = ctx.get_messages()
        combined = " ".join(m.content or "" for m in msgs)
        assert sentinel in combined

    def test_max_tokens_override(self):
        ctx = SumarisingContext(window_tokens=10_000)
        ctx.add(_msg("system", "sys"))
        for i in range(10):
            ctx.add(_msg("user", _long(100)))

        # Very tight budget passed inline
        msgs = ctx.get_messages(max_tokens=10)
        # Must not crash and system should still be present
        assert msgs[0].role == "system"

    def test_no_summary_when_nothing_to_summarise(self):
        """If tail fills the entire budget, no summary message is added."""
        ctx = SumarisingContext(window_tokens=1000, tail_ratio=0.99)
        ctx.add(_msg("system", "s"))
        ctx.add(_msg("user", "short"))
        ctx.add(_msg("assistant", "reply"))

        msgs = ctx.get_messages(max_tokens=1000)
        summary_msgs = [m for m in msgs if "Summary" in (m.content or "")]
        assert len(summary_msgs) == 0


# ---------------------------------------------------------------------------
# HierarchicalContext
# ---------------------------------------------------------------------------

class TestHierarchicalContext:
    def test_messages_within_tail_returned_verbatim(self):
        ctx = HierarchicalContext(tail_size=5)
        ctx.add(_msg("system", "sys"))
        for i in range(3):
            ctx.add(_msg("user", f"msg-{i}"))

        msgs = ctx.get_messages()
        assert msgs[0].content == "sys"
        assert len(msgs) == 4  # system + 3 tail

    def test_tail_limit_triggers_eviction(self):
        ctx = HierarchicalContext(tail_size=3)
        ctx.add(_msg("system", "sys"))
        for i in range(6):
            ctx.add(_msg("user", f"msg-{i}"))

        msgs = ctx.get_messages()
        # tail should contain exactly 3 messages
        non_system_non_summary = [
            m for m in msgs
            if m.role != "system" and "Long-term summary" not in (m.content or "")
        ]
        assert len(non_system_non_summary) == 3

    def test_long_term_summary_injected_after_eviction(self):
        ctx = HierarchicalContext(tail_size=2)
        ctx.add(_msg("system", "sys"))
        for i in range(5):
            ctx.add(_msg("user", f"msg-{i}"))

        msgs = ctx.get_messages()
        summary_msgs = [m for m in msgs if "Long-term summary" in (m.content or "")]
        assert len(summary_msgs) == 1

    def test_long_term_summary_contains_evicted_content(self):
        ctx = HierarchicalContext(tail_size=2)
        ctx.add(_msg("system", "sys"))
        ctx.add(_msg("user", "EVICTED_MESSAGE"))  # will be evicted
        ctx.add(_msg("user", "recent-1"))
        ctx.add(_msg("user", "recent-2"))

        msgs = ctx.get_messages()
        full_text = " ".join(m.content or "" for m in msgs)
        assert "EVICTED_MESSAGE" in full_text

    def test_verbatim_tail_contains_newest_messages(self):
        ctx = HierarchicalContext(tail_size=2)
        ctx.add(_msg("system", "sys"))
        for i in range(5):
            ctx.add(_msg("user", f"msg-{i}"))

        msgs = ctx.get_messages()
        # Last two messages should be in the tail verbatim
        contents = [m.content for m in msgs]
        assert "msg-3" in contents
        assert "msg-4" in contents

    def test_system_messages_always_present(self):
        ctx = HierarchicalContext(tail_size=2)
        ctx.add(_msg("system", "sys-A"))
        ctx.add(_msg("system", "sys-B"))
        for i in range(10):
            ctx.add(_msg("user", f"m{i}"))

        msgs = ctx.get_messages()
        system_contents = [m.content for m in msgs if m.role == "system"]
        assert "sys-A" in system_contents
        assert "sys-B" in system_contents

    def test_layout_order(self):
        """[system ...] [summary] [tail ...] ordering must be respected."""
        ctx = HierarchicalContext(tail_size=2)
        ctx.add(_msg("system", "sys"))
        for i in range(4):
            ctx.add(_msg("user", f"m{i}"))

        msgs = ctx.get_messages()
        roles = [m.role for m in msgs]
        # First is system
        assert roles[0] == "system"
        # Summary (user role with header) comes before tail user messages
        summary_idx = next(
            (i for i, m in enumerate(msgs) if "Long-term summary" in (m.content or "")),
            None,
        )
        assert summary_idx is not None
        assert summary_idx == 1  # right after system

    def test_no_summary_when_tail_not_exceeded(self):
        ctx = HierarchicalContext(tail_size=10)
        ctx.add(_msg("system", "sys"))
        ctx.add(_msg("user", "only a few messages"))

        msgs = ctx.get_messages()
        summary_msgs = [m for m in msgs if "Long-term summary" in (m.content or "")]
        assert len(summary_msgs) == 0

    def test_summary_cache_not_recomputed_without_new_evictions(self):
        calls: list[int] = []

        def counting_summariser(messages):
            calls.append(1)
            return extractive_summariser(messages)

        ctx = HierarchicalContext(tail_size=2, summariser=counting_summariser)
        ctx.add(_msg("system", "s"))
        for i in range(4):
            ctx.add(_msg("user", f"m{i}"))

        ctx.get_messages()  # triggers compaction
        ctx.get_messages()  # should use cache
        ctx.get_messages()  # should use cache

        assert len(calls) == 1, f"Expected 1 summariser call, got {len(calls)}"

    def test_new_eviction_invalidates_cache(self):
        calls: list[int] = []

        def counting_summariser(messages):
            calls.append(1)
            return extractive_summariser(messages)

        ctx = HierarchicalContext(tail_size=2, summariser=counting_summariser)
        ctx.add(_msg("system", "s"))
        for i in range(4):
            ctx.add(_msg("user", f"m{i}"))

        ctx.get_messages()            # computes summary
        ctx.add(_msg("user", "new"))  # triggers another eviction
        ctx.get_messages()            # should recompute

        assert len(calls) == 2

    def test_reset_clears_all_state(self):
        ctx = HierarchicalContext(tail_size=2)
        ctx.add(_msg("system", "sys"))
        for i in range(5):
            ctx.add(_msg("user", f"m{i}"))

        ctx.reset()
        assert ctx.get_messages() == []

    def test_custom_summariser_used(self):
        sentinel = "HIERARCHICAL_SENTINEL"

        ctx = HierarchicalContext(tail_size=1, summariser=lambda _: sentinel)
        ctx.add(_msg("system", "s"))
        ctx.add(_msg("user", "msg-a"))
        ctx.add(_msg("user", "msg-b"))  # evicts msg-a

        msgs = ctx.get_messages()
        full_text = " ".join(m.content or "" for m in msgs)
        assert sentinel in full_text

    def test_max_tokens_trims_tail(self):
        ctx = HierarchicalContext(tail_size=20)
        ctx.add(_msg("system", "s"))
        for i in range(15):
            ctx.add(_msg("user", _long(100)))

        # Very tight budget
        msgs = ctx.get_messages(max_tokens=10)
        # Must not crash; system is always included
        assert msgs[0].role == "system"


# ---------------------------------------------------------------------------
# async_summariser_from_llm (sync fallback path)
# ---------------------------------------------------------------------------

class TestAsyncSummariserFromLLM:
    def test_extractive_fallback_inside_event_loop(self):
        """When called from a running event loop the helper must not crash."""
        import asyncio

        class FakeLLMResponse:
            content = "LLM summary"

        async def fake_llm(messages):
            return FakeLLMResponse()

        summariser = async_summariser_from_llm(fake_llm)
        msgs = [_msg("user", "hello"), _msg("assistant", "hi")]

        async def run():
            # Calling a sync summariser from async → falls back to extractive
            result = summariser(msgs)
            assert isinstance(result, str)
            assert len(result) > 0

        asyncio.run(run())
