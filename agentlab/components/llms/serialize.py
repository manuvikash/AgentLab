"""Serialize LLM adapter inputs for playground tracing (matches OpenAI / Anthropic adapters)."""

from __future__ import annotations

import json
from typing import Any

from agentlab.core.component import BaseLLM
from agentlab.models.schemas import LLMResponse, Message, ToolSpec


def llm_trace_provider(llm: BaseLLM) -> str:
    from agentlab.components.llms.anthropic_llm import AnthropicLLM
    from agentlab.components.llms.openai_llm import OpenAILLM

    if isinstance(llm, OpenAILLM):
        return "openai"
    if isinstance(llm, AnthropicLLM):
        return "anthropic"
    return "openai"


def build_llm_request_trace(
    llm: BaseLLM,
    messages: list[Message],
    tools: list[ToolSpec] | None,
) -> dict[str, Any]:
    """Return a JSON-serializable dict matching the kwargs passed to the provider SDK."""
    from agentlab.components.llms.anthropic_llm import AnthropicLLM
    from agentlab.components.llms.openai_llm import OpenAILLM

    if isinstance(llm, OpenAILLM):
        return _build_openai_request_trace(llm, messages, tools)
    if isinstance(llm, AnthropicLLM):
        return _build_anthropic_request_trace(llm, messages, tools)
    return _build_openai_request_trace_generic(llm, messages, tools)


def _build_openai_request_trace_generic(
    llm: BaseLLM,
    messages: list[Message],
    tools: list[ToolSpec] | None,
) -> dict[str, Any]:
    """Fallback: OpenAI-shaped messages when the concrete class is unknown."""
    from agentlab.components.llms.openai_llm import OpenAILLM

    shim = OpenAILLM.__new__(OpenAILLM)
    shim._model = getattr(llm, "_model", llm.model_name)
    shim._temperature = getattr(llm, "_temperature", 0.0)
    shim._extra = getattr(llm, "_extra", {})
    return _build_openai_request_trace(shim, messages, tools)


def _build_openai_request_trace(
    llm: Any,
    messages: list[Message],
    tools: list[ToolSpec] | None,
) -> dict[str, Any]:
    import json as _json

    api_messages: list[dict[str, Any]] = []
    for m in messages:
        msg: dict[str, Any] = {"role": m.role}
        if m.role == "tool":
            msg["tool_call_id"] = m.tool_call_id
            if m.name is not None:
                msg["name"] = m.name
            msg["content"] = m.content or ""
        else:
            msg["content"] = m.content or ""
            if m.role == "assistant" and m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": _json.dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
        api_messages.append(msg)

    call_kwargs: dict[str, Any] = {
        "provider": "openai",
        "model": llm._model,
        "messages": api_messages,
        "temperature": llm._temperature,
        **getattr(llm, "_extra", {}),
    }

    if tools:
        call_kwargs["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    return call_kwargs


def _build_anthropic_request_trace(
    llm: Any,
    messages: list[Message],
    tools: list[ToolSpec] | None,
) -> dict[str, Any]:
    system_prompt = None
    api_messages: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            system_prompt = m.content
        else:
            api_messages.append({"role": m.role, "content": m.content})

    call_kwargs: dict[str, Any] = {
        "provider": "anthropic",
        "model": llm._model,
        "messages": api_messages,
        "max_tokens": llm._max_tokens,
        "temperature": llm._temperature,
        **getattr(llm, "_extra", {}),
    }

    if system_prompt:
        call_kwargs["system"] = system_prompt

    if tools:
        call_kwargs["tools"] = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    return call_kwargs


def llm_response_to_trace_dict(response: LLMResponse) -> dict[str, Any]:
    return response.model_dump(mode="json")


_MAX_FIELD_CHARS = 200_000


def truncate_for_storage(obj: Any, max_field_chars: int = _MAX_FIELD_CHARS) -> Any:
    """Clip very long strings in nested structures to keep SQLite rows bounded."""
    if isinstance(obj, str):
        if len(obj) > max_field_chars:
            return obj[:max_field_chars] + "\n... [truncated]"
        return obj
    if isinstance(obj, dict):
        return {k: truncate_for_storage(v, max_field_chars) for k, v in obj.items()}
    if isinstance(obj, list):
        return [truncate_for_storage(x, max_field_chars) for x in obj]
    return obj


def span_payload_size_ok(obj: Any, max_json_bytes: int = 1_500_000) -> bool:
    try:
        raw = json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return False
    return len(raw.encode("utf-8")) <= max_json_bytes


def ensure_span_payload_fits(
    request: dict[str, Any],
    response: dict[str, Any] | None,
    max_json_bytes: int = 1_500_000,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Truncate fields until combined JSON fits under max_json_bytes."""
    for max_chars in (_MAX_FIELD_CHARS, 50_000, 10_000, 2_000):
        req = truncate_for_storage(request, max_field_chars=max_chars)
        resp = (
            truncate_for_storage(response, max_field_chars=max_chars)
            if response is not None
            else None
        )
        if span_payload_size_ok({"request": req, "response": resp}, max_json_bytes):
            return req, resp
    return (
        {
            "_truncated": True,
            "_note": "request+response exceeded max_json_bytes after truncation",
        },
        {"_truncated": True} if response else None,
    )
