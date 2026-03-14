"""OpenAI LLM adapter."""

from __future__ import annotations

import json
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


@register("llm", "openai")
class OpenAILLM(BaseLLM):
    """LLM provider backed by the OpenAI API."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._temperature = temperature
        self._extra = kwargs
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key)
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

        api_messages: list[dict[str, Any]] = []
        for m in messages:
            msg: dict[str, Any] = {"role": m.role}
            if m.role == "tool":
                # Tool result message associated with a previous assistant.tool_calls entry
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
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in m.tool_calls
                    ]
            api_messages.append(msg)

        call_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": self._temperature,
            **self._extra,
            **kwargs,
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

        response = await client.chat.completions.create(**call_kwargs)
        choice = response.choices[0]

        tool_calls: list[LLMToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    LLMToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        usage = TokenUsage()
        if response.usage:
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )

        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            usage=usage,
        )
