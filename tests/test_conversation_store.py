"""Tests for playground conversation SQLite store."""

from __future__ import annotations

from agentlab.models.schemas import (
    ConversationMessage,
    ConversationRecord,
    LlmCallSpan,
)
from agentlab.storage.conversation_store import ConversationStore


def test_llm_spans_roundtrip(tmp_path):
    db = tmp_path / "c.db"
    store = ConversationStore(db)
    conv = ConversationRecord(agent_name="a1")
    store.create_conversation(conv)

    span = LlmCallSpan(
        call_index=1,
        model="gpt-4o",
        request={"provider": "openai", "messages": []},
        response={"content": "hi", "tool_calls": [], "usage": {}},
    )
    msg = ConversationMessage(
        conversation_id=conv.id,
        seq=1,
        role="assistant",
        content="hi",
        trace=[],
        llm_spans=[span],
    )
    store.add_message(msg)

    loaded = store.get_messages(conv.id)
    assert len(loaded) == 1
    assert len(loaded[0].llm_spans) == 1
    assert loaded[0].llm_spans[0].call_index == 1
    assert loaded[0].llm_spans[0].model == "gpt-4o"
