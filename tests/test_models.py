"""Tests for Pydantic data models."""

from __future__ import annotations

from agentlab.models.schemas import (
    AgentConfig,
    ExperimentConfig,
    Metrics,
    RunRecord,
    TaskConfig,
    TraceEntry,
    ToolCallRecord,
    TokenUsage,
)


def test_agent_config_defaults():
    cfg = AgentConfig(name="test", llm="openai")
    assert cfg.loop == "react"
    assert cfg.context == "sliding"
    assert cfg.sandbox == "local"
    assert cfg.tools == []
    assert cfg.max_steps == 30


def test_agent_config_full():
    cfg = AgentConfig(
        name="full",
        llm="anthropic",
        loop="react",
        context="simple",
        tools=["filesystem", "shell"],
        sandbox="docker",
        prompt="Do stuff",
        memory="simple",
        max_steps=50,
    )
    assert cfg.name == "full"
    assert cfg.tools == ["filesystem", "shell"]


def test_run_record_defaults():
    run = RunRecord()
    assert run.status == "pending"
    assert run.metrics.steps == 0
    assert run.trace == []
    assert run.id  # auto-generated


def test_trace_entry():
    entry = TraceEntry(
        step=1,
        thought="thinking",
        action="tool:shell",
        tool_call=ToolCallRecord(tool="shell", args={"command": "ls"}),
    )
    assert entry.step == 1
    assert entry.tool_call.tool == "shell"


def test_metrics():
    m = Metrics(success=True, steps=5, tokens_used=1000, runtime_seconds=2.5)
    assert m.success is True
    assert m.steps == 5


def test_task_config():
    task = TaskConfig(id="bug1", prompt="fix the bug")
    assert task.repo is None
    assert task.validator is None


def test_experiment_config():
    exp = ExperimentConfig(
        name="test_exp",
        matrix={"llm": ["openai", "anthropic"], "context": ["sliding"]},
        base={"loop": "react", "tools": ["shell"]},
        task="bug1",
    )
    assert len(exp.matrix["llm"]) == 2


def test_run_record_serialization():
    run = RunRecord(agent_name="test_agent", status="completed")
    json_str = run.model_dump_json()
    loaded = RunRecord.model_validate_json(json_str)
    assert loaded.agent_name == "test_agent"
    assert loaded.status == "completed"


def test_token_usage():
    usage = TokenUsage(input_tokens=100, output_tokens=50)
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
