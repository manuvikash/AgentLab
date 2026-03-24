"""Tests for LLM request serialization used in playground tracing."""

from __future__ import annotations

from agentlab.components.llms.anthropic_llm import AnthropicLLM
from agentlab.components.llms.openai_llm import OpenAILLM
from agentlab.components.llms.serialize import (
    build_llm_request_trace,
    ensure_span_payload_fits,
    llm_response_to_trace_dict,
    truncate_for_storage,
)
from agentlab.models.schemas import LLMResponse, LLMToolCall, Message, TokenUsage, ToolSpec


def test_openai_request_trace_matches_adapter_shape():
    llm = OpenAILLM(model="gpt-4o-mini", temperature=0.1)
    messages = [
        Message(role="system", content="You are helpful."),
        Message(role="user", content="Hi"),
    ]
    tools = [
        ToolSpec(
            name="shell",
            description="Run shell",
            parameters={"type": "object", "properties": {}},
        )
    ]
    trace = build_llm_request_trace(llm, messages, tools)
    assert trace["provider"] == "openai"
    assert trace["model"] == "gpt-4o-mini"
    assert trace["temperature"] == 0.1
    assert len(trace["messages"]) == 2
    assert trace["messages"][0]["role"] == "system"
    assert trace["tools"][0]["type"] == "function"
    assert trace["tools"][0]["function"]["name"] == "shell"


def test_openai_request_includes_assistant_tool_calls():
    llm = OpenAILLM()
    messages = [
        Message(
            role="assistant",
            content="I'll call a tool",
            tool_calls=[
                LLMToolCall(id="call_1", name="shell", arguments={"command": "pwd"}),
            ],
        ),
        Message(role="tool", content="/tmp", tool_call_id="call_1", name="shell"),
    ]
    trace = build_llm_request_trace(llm, messages, None)
    assert trace["messages"][0]["role"] == "assistant"
    assert trace["messages"][0]["tool_calls"][0]["function"]["name"] == "shell"


def test_anthropic_request_trace():
    llm = AnthropicLLM(model="claude-3-5-sonnet-20241022", max_tokens=1024)
    messages = [
        Message(role="system", content="Sys"),
        Message(role="user", content="Hello"),
    ]
    trace = build_llm_request_trace(llm, messages, None)
    assert trace["provider"] == "anthropic"
    assert trace["system"] == "Sys"
    assert trace["messages"] == [{"role": "user", "content": "Hello"}]


def test_llm_response_to_trace_dict():
    r = LLMResponse(
        content="ok",
        tool_calls=[],
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )
    d = llm_response_to_trace_dict(r)
    assert d["content"] == "ok"
    assert d["usage"]["input_tokens"] == 10


def test_truncate_for_storage_long_string():
    long = "x" * 300_000
    out = truncate_for_storage({"msg": long}, max_field_chars=1000)
    assert len(out["msg"]) < len(long)
    assert "truncated" in out["msg"]


def test_ensure_span_payload_fits():
    req = {"a": "b"}
    resp = {"content": "x"}
    r1, r2 = ensure_span_payload_fits(req, resp)
    assert r1["a"] == "b"
    assert r2 is not None and r2["content"] == "x"
