"""Tests for context manager components."""

from __future__ import annotations

from agentlab.components.context.simple import SimpleContext
from agentlab.components.context.sliding import SlidingWindowContext
from agentlab.models.schemas import Message


def test_simple_context():
    ctx = SimpleContext()
    ctx.add(Message(role="system", content="Be helpful"))
    ctx.add(Message(role="user", content="Hello"))
    ctx.add(Message(role="assistant", content="Hi there"))

    msgs = ctx.get_messages()
    assert len(msgs) == 3
    assert msgs[0].role == "system"


def test_simple_context_reset():
    ctx = SimpleContext()
    ctx.add(Message(role="user", content="hi"))
    ctx.reset()
    assert ctx.get_messages() == []


def test_sliding_window_keeps_system():
    ctx = SlidingWindowContext(window_tokens=10)
    ctx.add(Message(role="system", content="sys"))
    ctx.add(Message(role="user", content="a" * 100))
    ctx.add(Message(role="user", content="recent"))

    msgs = ctx.get_messages()
    assert msgs[0].role == "system"
    assert msgs[0].content == "sys"
    assert any(m.content == "recent" for m in msgs)


def test_sliding_window_truncates():
    ctx = SlidingWindowContext(window_tokens=5)
    ctx.add(Message(role="system", content="s"))
    for i in range(20):
        ctx.add(Message(role="user", content=f"message {i} " * 10))

    msgs = ctx.get_messages()
    assert len(msgs) < 22  # should have dropped old messages


def test_sliding_window_respects_max_tokens():
    ctx = SlidingWindowContext(window_tokens=100)
    ctx.add(Message(role="system", content="sys"))
    ctx.add(Message(role="user", content="short"))

    msgs = ctx.get_messages(max_tokens=100)
    assert len(msgs) == 2
