"""Core data models for AgentLab."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """Declarative agent definition loaded from YAML."""

    name: str
    llm: str
    loop: str = "react"
    context: str = "sliding"
    tools: list[str] = Field(default_factory=list)
    sandbox: str = "local"
    prompt: str | None = None
    memory: str | None = None
    max_steps: int = 30
    max_tokens: int = 4096


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------


class ToolCallRecord(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    duration_ms: float | None = None


class TraceEntry(BaseModel):
    step: int
    thought: str | None = None
    action: str | None = None
    tool_call: ToolCallRecord | None = None
    result: str | None = None
    timestamp: datetime = Field(default_factory=_utcnow)
    token_usage: TokenUsage | None = None


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


class Metrics(BaseModel):
    success: bool | None = None
    steps: int = 0
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    runtime_seconds: float = 0.0
    patch_size: int | None = None


class RunRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    agent_name: str = ""
    agent_config: AgentConfig | None = None
    task_id: str | None = None
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    metrics: Metrics = Field(default_factory=Metrics)
    trace: list[TraceEntry] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TaskConfig(BaseModel):
    """A benchmark task definition."""

    id: str
    prompt: str
    repo: str | None = None
    validator: str | None = None
    setup_commands: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------


class ExperimentConfig(BaseModel):
    """YAML-driven experiment definition with a parameter matrix."""

    name: str
    matrix: dict[str, list[str]]
    base: dict[str, Any] = Field(default_factory=dict)
    task: str | None = None
    tasks: list[str] = Field(default_factory=list)


class ExperimentRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str = ""
    config: ExperimentConfig | None = None
    run_ids: list[str] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Messages (LLM conversation)
# ---------------------------------------------------------------------------


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    # For assistant messages only: tool calls returned by the model
    tool_calls: list["LLMToolCall"] = Field(default_factory=list)


class ToolSpec(BaseModel):
    """Schema passed to an LLM describing an available tool."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[LLMToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)


class LLMToolCall(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
