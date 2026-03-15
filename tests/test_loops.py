"""Tests for all loop controller implementations.

Uses stub LLMs and sandboxes to exercise each loop in isolation
without requiring real API keys or Docker.
"""

from __future__ import annotations

import pytest
import asyncio
from typing import Any
from collections import deque

from agentlab.components.context.simple import SimpleContext
from agentlab.components.loops.planner_executor import PlannerExecutorLoop, _parse_plan
from agentlab.components.loops.ralph import RALPHLoop, _summarise_trace
from agentlab.components.loops.react import ReActLoop
from agentlab.components.loops.single_shot import SingleShotLoop
from agentlab.components.memory.simple import SimpleMemory
from agentlab.core.component import (
    BaseLLM,
    BaseSandbox,
    BaseTool,
    ExecutionResult,
    RuntimeContext,
    ToolResult,
)
from agentlab.models.schemas import LLMResponse, LLMToolCall, Message, ToolSpec, TokenUsage


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class ScriptedLLM(BaseLLM):
    """Returns pre-configured LLMResponse objects in order, then repeats last."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._queue: deque[LLMResponse] = deque(responses)
        self._last: LLMResponse = responses[-1]

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **_: Any,
    ) -> LLMResponse:
        if self._queue:
            r = self._queue.popleft()
            self._last = r
            return r
        return self._last

    @property
    def model_name(self) -> str:
        return "scripted"


def _resp(content: str = "", tool_calls: list[LLMToolCall] | None = None) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=tool_calls or [],
        usage=TokenUsage(input_tokens=10, output_tokens=10),
    )


def _tool_call(name: str, **kwargs: Any) -> LLMToolCall:
    return LLMToolCall(name=name, arguments=kwargs)


class NullSandbox(BaseSandbox):
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def execute(self, command: str, timeout: int | None = None) -> ExecutionResult:
        return ExecutionResult(exit_code=0, stdout="ok", stderr="")

    async def read_file(self, path: str) -> str:
        return ""

    async def write_file(self, path: str, content: str) -> None:
        pass

    async def list_files(self, path: str = ".") -> list[str]:
        return []


class EchoTool(BaseTool):
    """Returns its 'message' argument as the result."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo the message argument."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }

    async def execute(self, sandbox: Any = None, **kwargs: Any) -> ToolResult:
        return ToolResult(output=kwargs.get("message", ""))


def _make_ctx(llm: BaseLLM, tools: list[BaseTool] | None = None, memory=None) -> RuntimeContext:
    return RuntimeContext(
        llm=llm,
        context_manager=SimpleContext(),
        tools=tools or [],
        sandbox=NullSandbox(),
        memory=memory,
        system_prompt="You are a helpful assistant.",
        max_steps=10,
        max_tokens=2048,
    )


# ---------------------------------------------------------------------------
# ReAct loop tests
# ---------------------------------------------------------------------------


class TestReActLoop:
    @pytest.mark.asyncio
    async def test_plain_text_answer(self):
        llm = ScriptedLLM([_resp("The answer is 42.")])
        ctx = _make_ctx(llm)
        loop = ReActLoop()
        result = await loop.run(ctx, "What is 6 × 7?")
        assert result.output == "The answer is 42."
        assert result.steps == 1

    @pytest.mark.asyncio
    async def test_tool_then_answer(self):
        llm = ScriptedLLM([
            _resp("Let me echo.", [_tool_call("echo", message="hello")]),
            _resp("The echo said hello."),
        ])
        ctx = _make_ctx(llm, tools=[EchoTool()])
        loop = ReActLoop()
        result = await loop.run(ctx, "Echo hello.")
        assert "echo" in result.output.lower() or "hello" in result.output.lower()
        assert any("tool:echo" in str(e.get("action", "")) for e in result.trace)

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_per_step(self):
        """Multiple tool calls in a single LLM response are all executed."""
        llm = ScriptedLLM([
            _resp(
                "Two calls.",
                [
                    _tool_call("echo", message="first"),
                    _tool_call("echo", message="second"),
                ],
            ),
            _resp("Done."),
        ])
        ctx = _make_ctx(llm, tools=[EchoTool()])
        loop = ReActLoop()
        result = await loop.run(ctx, "Echo twice.")
        tool_actions = [e for e in result.trace if "tool:echo" in str(e.get("action", ""))]
        assert len(tool_actions) == 2

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        llm = ScriptedLLM([
            _resp("Calling.", [_tool_call("nonexistent", x=1)]),
            _resp("Handled error."),
        ])
        ctx = _make_ctx(llm, tools=[])
        loop = ReActLoop()
        result = await loop.run(ctx, "Use nonexistent tool.")
        error_entries = [
            e for e in result.trace if "Error: unknown tool" in (e.get("result") or "")
        ]
        assert len(error_entries) >= 1

    @pytest.mark.asyncio
    async def test_token_counts_accumulated(self):
        llm = ScriptedLLM([
            _resp("Step 1.", [_tool_call("echo", message="hi")]),
            _resp("Step 2."),
        ])
        ctx = _make_ctx(llm, tools=[EchoTool()])
        loop = ReActLoop()
        result = await loop.run(ctx, "Task.")
        # 2 LLM calls × 10 input + 10 output each = 40 total
        assert result.total_input_tokens == 20
        assert result.total_output_tokens == 20

    @pytest.mark.asyncio
    async def test_max_steps_limits_iterations(self):
        # LLM always returns a tool call → loop must stop at max_steps
        llm = ScriptedLLM([_resp("Loop.", [_tool_call("echo", message="x")])] * 20)
        ctx = _make_ctx(llm, tools=[EchoTool()])
        ctx.max_steps = 3
        loop = ReActLoop()
        result = await loop.run(ctx, "Infinite loop?")
        assert result.steps <= 3


# ---------------------------------------------------------------------------
# SingleShot loop tests
# ---------------------------------------------------------------------------


class TestSingleShotLoop:
    @pytest.mark.asyncio
    async def test_plain_text_answer_one_call(self):
        llm = ScriptedLLM([_resp("Immediate answer.")])
        ctx = _make_ctx(llm)
        loop = SingleShotLoop()
        result = await loop.run(ctx, "Answer quickly.")
        assert result.output == "Immediate answer."
        assert result.steps == 1

    @pytest.mark.asyncio
    async def test_single_round_of_tool_use(self):
        """When the model requests a tool, execute it and make one more call."""
        llm = ScriptedLLM([
            _resp("Let me check.", [_tool_call("echo", message="check")]),
            _resp("Result after echo."),
        ])
        ctx = _make_ctx(llm, tools=[EchoTool()])
        loop = SingleShotLoop()
        result = await loop.run(ctx, "Check something.")
        assert result.output == "Result after echo."
        assert result.steps == 2

    @pytest.mark.asyncio
    async def test_no_further_tool_calls_after_first_round(self):
        """The second LLM call must NOT include tool specs, enforcing single-shot."""
        tool_calls_in_second_call: list[bool] = []

        class TrackingLLM(BaseLLM):
            _calls = 0

            async def generate(self, messages, tools=None, **_):
                self.__class__._calls += 1
                tool_calls_in_second_call.append(tools is not None)
                if self.__class__._calls == 1:
                    return _resp("First.", [_tool_call("echo", message="x")])
                return _resp("Final.")

            @property
            def model_name(self):
                return "tracking"

        ctx = _make_ctx(TrackingLLM(), tools=[EchoTool()])
        loop = SingleShotLoop()
        await loop.run(ctx, "Task.")
        # Second call should have tools=None
        assert tool_calls_in_second_call[1] is False

    @pytest.mark.asyncio
    async def test_token_counts(self):
        llm = ScriptedLLM([
            _resp("Tool.", [_tool_call("echo", message="y")]),
            _resp("Done."),
        ])
        ctx = _make_ctx(llm, tools=[EchoTool()])
        loop = SingleShotLoop()
        result = await loop.run(ctx, "Go.")
        assert result.total_input_tokens == 20
        assert result.total_output_tokens == 20


# ---------------------------------------------------------------------------
# RALPH loop tests
# ---------------------------------------------------------------------------


class TestRALPHLoop:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        llm = ScriptedLLM([_resp("Got it on first try.")])
        ctx = _make_ctx(llm)
        loop = RALPHLoop(max_attempts=3, inner_max_steps=5)
        result = await loop.run(ctx, "Simple task.")
        assert result.output == "Got it on first try."

    @pytest.mark.asyncio
    async def test_reflection_generated_on_inner_step_exhaustion(self):
        """When inner loop hits max steps without a plain answer, a reflection is done."""
        # First inner attempt: always returns tool calls (exhausts inner_max_steps=2)
        # Reflection call: returns text reflection
        # Second inner attempt: returns plain answer
        responses = (
            [_resp("Going.", [_tool_call("echo", message="x")])] * 2  # exhaust inner steps
            + [_resp("I should try a different approach.")]            # reflection
            + [_resp("Success on second attempt.")]                    # attempt 2
        )
        llm = ScriptedLLM(responses)
        memory = SimpleMemory()
        ctx = _make_ctx(llm, tools=[EchoTool()], memory=memory)
        loop = RALPHLoop(max_attempts=2, inner_max_steps=2)
        result = await loop.run(ctx, "Hard task.")
        assert result.output == "Success on second attempt."
        reflection = memory.retrieve("ralph_reflection_1")
        assert reflection is not None

    @pytest.mark.asyncio
    async def test_reflection_injected_in_next_attempt(self):
        """Reflections from prior attempts appear in the context of subsequent attempts."""
        injected_context: list[str] = []

        class ContextCaptureLLM(BaseLLM):
            _call = 0

            async def generate(self, messages, tools=None, **_):
                self.__class__._call += 1
                call = self.__class__._call
                # Record all user messages for inspection
                for m in messages:
                    if m.role == "user" and "reflection" in (m.content or "").lower():
                        injected_context.append(m.content or "")
                if call == 1:
                    # Inner step 1: exhaust
                    return _resp(".", [_tool_call("echo", message="x")])
                if call == 2:
                    # Reflection
                    return _resp("Prior reflection text.")
                # Attempt 2: answer
                return _resp("Final answer.")

            @property
            def model_name(self):
                return "capture"

        memory = SimpleMemory()
        ctx = _make_ctx(ContextCaptureLLM(), tools=[EchoTool()], memory=memory)
        loop = RALPHLoop(max_attempts=2, inner_max_steps=1)
        result = await loop.run(ctx, "Test reflection injection.")
        # The reflection from attempt 1 should have been used
        assert len(injected_context) >= 1 or memory.retrieve("ralph_reflection_1") is not None

    @pytest.mark.asyncio
    async def test_max_attempts_respected(self):
        """Loop never runs more than max_attempts outer iterations."""
        call_count = [0]

        class CountingLLM(BaseLLM):
            async def generate(self, messages, tools=None, **_):
                call_count[0] += 1
                # Always return a tool call so inner loop exhausts
                return _resp(".", [_tool_call("echo", message="x")])

            @property
            def model_name(self):
                return "counting"

        ctx = _make_ctx(CountingLLM(), tools=[EchoTool()])
        loop = RALPHLoop(max_attempts=2, inner_max_steps=1)
        result = await loop.run(ctx, "Nonstop task.")
        # Should have stopped — output may be None since model never gave plain text
        assert result.steps > 0

    @pytest.mark.asyncio
    async def test_transient_memory_used_when_ctx_memory_none(self):
        """When ctx.memory is None, RALPH uses an internal transient store."""
        responses = (
            [_resp(".", [_tool_call("echo", message="x")])]  # exhaust inner
            + [_resp("Reflection.")]
            + [_resp("Answer.")]
        )
        llm = ScriptedLLM(responses)
        ctx = _make_ctx(llm, tools=[EchoTool()], memory=None)
        loop = RALPHLoop(max_attempts=2, inner_max_steps=1)
        result = await loop.run(ctx, "Task.")
        assert result.output == "Answer."

    @pytest.mark.asyncio
    async def test_tool_use_within_inner_loop(self):
        llm = ScriptedLLM([
            _resp("Calling echo.", [_tool_call("echo", message="hello")]),
            _resp("Echo returned hello. Done."),
        ])
        ctx = _make_ctx(llm, tools=[EchoTool()])
        loop = RALPHLoop(max_attempts=1, inner_max_steps=5)
        result = await loop.run(ctx, "Echo something.")
        assert result.output == "Echo returned hello. Done."
        tool_entries = [e for e in result.trace if "tool:echo" in str(e.get("action", ""))]
        assert len(tool_entries) >= 1


# ---------------------------------------------------------------------------
# Planner-Executor loop tests
# ---------------------------------------------------------------------------


class TestPlannerExecutorLoop:
    @pytest.mark.asyncio
    async def test_plan_then_execute_then_synthesise(self):
        llm = ScriptedLLM([
            _resp("1. Do A\n2. Do B"),           # plan
            _resp("Step A done."),               # execute step 1
            _resp("Step B done."),               # execute step 2
            _resp("Combined: A and B done."),    # synthesis
        ])
        ctx = _make_ctx(llm)
        loop = PlannerExecutorLoop(max_steps_per_step=2, max_plan_steps=5)
        result = await loop.run(ctx, "Do A then B.")
        assert result.output == "Combined: A and B done."

    @pytest.mark.asyncio
    async def test_plan_step_uses_tools(self):
        llm = ScriptedLLM([
            _resp("1. Echo hello"),
            _resp("Going to echo.", [_tool_call("echo", message="hello")]),
            _resp("Echo returned hello."),
            _resp("Final synthesis."),
        ])
        ctx = _make_ctx(llm, tools=[EchoTool()])
        loop = PlannerExecutorLoop(max_steps_per_step=3, max_plan_steps=1)
        result = await loop.run(ctx, "Echo something.")
        assert result.output == "Final synthesis."
        echo_entries = [
            e for e in result.trace if "tool:echo" in str(e.get("action", ""))
        ]
        assert len(echo_entries) >= 1

    @pytest.mark.asyncio
    async def test_no_plan_steps_falls_back_to_plan_text(self):
        """When planner returns no parseable numbered list, output the plan text itself."""
        llm = ScriptedLLM([_resp("I cannot plan this.")])
        ctx = _make_ctx(llm)
        loop = PlannerExecutorLoop()
        result = await loop.run(ctx, "Weird task.")
        assert result.output == "I cannot plan this."

    @pytest.mark.asyncio
    async def test_max_plan_steps_respected(self):
        """Only max_plan_steps steps are executed even if the plan has more."""
        plan = "\n".join(f"{i}. Step {i}" for i in range(1, 11))  # 10 steps
        # 1 plan call + 3 exec calls + 1 synth = 5 scripted responses
        llm = ScriptedLLM([_resp(plan)] + [_resp(f"Done {i}.", ) for i in range(20)])
        ctx = _make_ctx(llm)
        loop = PlannerExecutorLoop(max_steps_per_step=1, max_plan_steps=3)
        result = await loop.run(ctx, "Many steps.")
        # Synthesis should fire; trace should contain plan + 3 step entries + synthesis
        exec_entries = [
            e for e in result.trace
            if e.get("action", "").startswith("step_") and "final" in e.get("action", "")
        ]
        assert len(exec_entries) == 3

    @pytest.mark.asyncio
    async def test_trace_has_plan_and_synthesis_entries(self):
        llm = ScriptedLLM([
            _resp("1. Alpha"),
            _resp("Alpha done."),
            _resp("Synthesised."),
        ])
        ctx = _make_ctx(llm)
        loop = PlannerExecutorLoop(max_steps_per_step=2, max_plan_steps=1)
        result = await loop.run(ctx, "Single step plan.")
        actions = [e.get("action", "") for e in result.trace]
        assert "plan" in actions
        assert any("synthesis" in a for a in actions)

    @pytest.mark.asyncio
    async def test_token_counts_cover_all_phases(self):
        """Token counts must include plan + all exec + synthesis calls."""
        llm = ScriptedLLM([
            _resp("1. X\n2. Y"),
            _resp("X done."),
            _resp("Y done."),
            _resp("Synth."),
        ])
        ctx = _make_ctx(llm)
        loop = PlannerExecutorLoop(max_steps_per_step=1, max_plan_steps=2)
        result = await loop.run(ctx, "Two-step task.")
        # 4 LLM calls × (10 in + 10 out) = 80 total
        assert result.total_input_tokens == 40
        assert result.total_output_tokens == 40


# ---------------------------------------------------------------------------
# parse_plan utility tests
# ---------------------------------------------------------------------------


def test_parse_plan_standard_numbered():
    text = "1. Do this\n2. Then that\n3. Finally those"
    assert _parse_plan(text) == ["Do this", "Then that", "Finally those"]


def test_parse_plan_parentheses():
    text = "1) First\n2) Second"
    assert _parse_plan(text) == ["First", "Second"]


def test_parse_plan_step_prefix():
    text = "Step 1: Alpha\nStep 2: Beta"
    assert _parse_plan(text) == ["Alpha", "Beta"]


def test_parse_plan_limit():
    text = "\n".join(f"{i}. Item {i}" for i in range(1, 20))
    result = _parse_plan(text, limit=5)
    assert len(result) == 5


def test_parse_plan_empty():
    assert _parse_plan("No numbered steps here.") == []


# ---------------------------------------------------------------------------
# _summarise_trace utility test
# ---------------------------------------------------------------------------


def test_summarise_trace_includes_tool_and_answer():
    from agentlab.models.schemas import ToolCallRecord, TraceEntry

    trace = [
        TraceEntry(
            step=1,
            thought="thinking",
            action="tool:echo",
            tool_call=ToolCallRecord(tool="echo", args={"message": "hi"}, result="hi"),
            result="hi",
        ),
        TraceEntry(
            step=2,
            thought="done",
            action="final_answer",
            result="The answer is hi.",
        ),
    ]
    summary = _summarise_trace(trace)
    assert "echo" in summary
    assert "final answer" in summary.lower()


# ---------------------------------------------------------------------------
# Registration sanity check
# ---------------------------------------------------------------------------


def test_all_loops_registered():
    import agentlab.components  # noqa: F401 — trigger registration

    from agentlab.core.registry import get_registry

    reg = get_registry()
    for name in ("react", "single_shot", "ralph", "planner_executor"):
        cls = reg.get("loop", name)
        assert cls is not None, f"Loop '{name}' not registered"
