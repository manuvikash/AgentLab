"""Trace recording for agent runs."""

from __future__ import annotations

from agentlab.models.schemas import TokenUsage, ToolCallRecord, TraceEntry


class TraceRecorder:
    """Accumulates trace entries during an agent run."""

    def __init__(self) -> None:
        self._entries: list[TraceEntry] = []
        self._step = 0

    def record(
        self,
        *,
        thought: str | None = None,
        action: str | None = None,
        tool_call: ToolCallRecord | None = None,
        result: str | None = None,
        token_usage: TokenUsage | None = None,
    ) -> TraceEntry:
        self._step += 1
        entry = TraceEntry(
            step=self._step,
            thought=thought,
            action=action,
            tool_call=tool_call,
            result=result,
            token_usage=token_usage,
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> list[TraceEntry]:
        return list(self._entries)

    @property
    def step_count(self) -> int:
        return self._step

    @property
    def total_tokens(self) -> TokenUsage:
        inp = sum(e.token_usage.input_tokens for e in self._entries if e.token_usage)
        out = sum(e.token_usage.output_tokens for e in self._entries if e.token_usage)
        return TokenUsage(input_tokens=inp, output_tokens=out)

    def reset(self) -> None:
        self._entries.clear()
        self._step = 0
