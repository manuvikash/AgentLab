"""Anthropic LLM adapter."""

from __future__ import annotations

import os
from typing import Any

from agentlab.core.component import BaseLLM
from agentlab.core.registry import register
from agentlab.models.schemas import (
    LLMResponse,
    LLMToolCall,
    Message,
    TokenUsage,
    ToolSpec,
)


@register("llm", "anthropic")
class AnthropicLLM(BaseLLM):
    """LLM provider backed by the Anthropic API."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._extra = kwargs
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()

        system_prompt = None
        api_messages = []
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                api_messages.append({"role": m.role, "content": m.content})

        call_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            **self._extra,
            **kwargs,
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

        response = await client.messages.create(**call_kwargs)

        content_text = ""
        tool_calls: list[LLMToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    LLMToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            usage=usage,
        )
