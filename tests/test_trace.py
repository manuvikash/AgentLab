"""Tests for the trace recorder."""

from __future__ import annotations

from agentlab.models.schemas import TokenUsage, ToolCallRecord
from agentlab.runtime.trace import TraceRecorder


def test_record_entries():
    recorder = TraceRecorder()
    recorder.record(thought="thinking", action="tool:shell")
    recorder.record(thought="more thinking", result="done")
    assert recorder.step_count == 2
    assert len(recorder.entries) == 2


def test_record_with_tool_call():
    recorder = TraceRecorder()
    recorder.record(
        thought="let me run ls",
        action="tool:shell",
        tool_call=ToolCallRecord(tool="shell", args={"command": "ls"}, result="file.py"),
    )
    entry = recorder.entries[0]
    assert entry.tool_call.tool == "shell"
    assert entry.tool_call.result == "file.py"


def test_total_tokens():
    recorder = TraceRecorder()
    recorder.record(
        thought="a",
        token_usage=TokenUsage(input_tokens=100, output_tokens=50),
    )
    recorder.record(
        thought="b",
        token_usage=TokenUsage(input_tokens=200, output_tokens=100),
    )
    totals = recorder.total_tokens
    assert totals.input_tokens == 300
    assert totals.output_tokens == 150


def test_reset():
    recorder = TraceRecorder()
    recorder.record(thought="something")
    recorder.reset()
    assert recorder.step_count == 0
    assert len(recorder.entries) == 0
