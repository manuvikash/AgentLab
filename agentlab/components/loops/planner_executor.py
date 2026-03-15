"""Planner-Executor loop: separate planning and execution phases.

Phase 1 — Plan:
  One LLM call that produces a numbered list of concrete steps.
  The model is explicitly told NOT to use tools yet, just to plan.

Phase 2 — Execute:
  For each step, a bounded ReAct-style inner loop executes that single step
  using the available tools and accumulates results.

Phase 3 — Synthesise:
  One final LLM call receives all step results and produces the final answer.

This mirrors classical hierarchical planning and benefits tasks that are:
  • Complex and multi-part  (decomposition helps)
  • Prone to losing track of sub-goals in long ReAct loops
  • Easier to debug step-by-step

Parameters (at construction time):
  max_steps_per_step: int — ReAct steps allowed per plan step (default 6).
  max_plan_steps: int — upper bound on plan steps parsed (default 10).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from agentlab.core.component import BaseLoop, LoopResult, RuntimeContext, ToolResult
from agentlab.core.registry import register
from agentlab.models.schemas import Message, ToolCallRecord, TraceEntry

logger = logging.getLogger(__name__)

PLANNER_SYSTEM = (
    "You are a planning assistant. Given a task, output ONLY a numbered list of concrete "
    "action steps to solve it. Do NOT execute anything yet. Do NOT call tools. "
    "Each step should be a single, specific, actionable instruction. "
    "Format exactly as:\n1. <step>\n2. <step>\n..."
)

EXECUTOR_SYSTEM_TEMPLATE = (
    "You are an execution assistant. You are working on step {step_num} of {total_steps} "
    "from the following plan:\n\n"
    "{plan}\n\n"
    "Overall task: {task}\n\n"
    "Focus ONLY on completing step {step_num}: {step_text}\n"
    "Use tools if needed. When done with this step, state your result clearly and stop."
)

SYNTHESISER_SYSTEM = (
    "You are a synthesis assistant. You will be given a task and the results from each "
    "step of executing a plan. Combine the results into a coherent, complete final answer."
)


@register("loop", "planner_executor")
class PlannerExecutorLoop(BaseLoop):
    """Planner-Executor loop: plan once, execute each step, synthesise.

    Parameters:
      max_steps_per_step: ReAct iterations budget per plan step (default 6).
      max_plan_steps: Maximum number of plan steps to execute (default 10).
    """

    def __init__(
        self,
        max_steps_per_step: int = 6,
        max_plan_steps: int = 10,
        **_: Any,
    ) -> None:
        self._max_steps_per_step = max_steps_per_step
        self._max_plan_steps = max_plan_steps

    async def run(self, ctx: RuntimeContext, task_prompt: str) -> LoopResult:
        tool_specs = [t.to_spec() for t in ctx.tools.values()]
        all_trace: list[dict[str, Any]] = []
        total_input = 0
        total_output = 0
        global_step = 0

        # ------------------------------------------------------------------ #
        # Phase 1: Planning                                                    #
        # ------------------------------------------------------------------ #
        logger.info("Planner-Executor: planning phase")
        plan_messages = [
            Message(role="system", content=PLANNER_SYSTEM),
            Message(role="user", content=task_prompt),
        ]
        plan_response = await ctx.llm.generate(plan_messages, tools=None)
        total_input += plan_response.usage.input_tokens
        total_output += plan_response.usage.output_tokens

        plan_text = plan_response.content or ""
        plan_steps = _parse_plan(plan_text, limit=self._max_plan_steps)

        global_step += 1
        all_trace.append(
            TraceEntry(
                step=global_step,
                thought=plan_text,
                action="plan",
                result=f"Generated {len(plan_steps)} steps",
            ).model_dump()
        )

        logger.info("Plan has %d steps: %s", len(plan_steps), plan_steps)

        if not plan_steps:
            # Planner returned no parseable steps — fall back to the plan text itself
            return LoopResult(
                success=None,
                output=plan_text,
                trace=all_trace,
                steps=global_step,
                total_input_tokens=total_input,
                total_output_tokens=total_output,
            )

        # ------------------------------------------------------------------ #
        # Phase 2: Execution                                                   #
        # ------------------------------------------------------------------ #
        step_results: list[str] = []

        for step_idx, step_text in enumerate(plan_steps, start=1):
            logger.info("Executing plan step %d/%d: %s", step_idx, len(plan_steps), step_text)

            executor_system = EXECUTOR_SYSTEM_TEMPLATE.format(
                step_num=step_idx,
                total_steps=len(plan_steps),
                plan=plan_text,
                task=task_prompt,
                step_text=step_text,
            )

            ctx.context_manager.reset()
            ctx.context_manager.add(Message(role="system", content=executor_system))
            ctx.context_manager.add(
                Message(role="user", content=f"Please complete step {step_idx}: {step_text}")
            )

            step_output: str | None = None

            for inner_step in range(1, self._max_steps_per_step + 1):
                global_step += 1
                messages = ctx.context_manager.get_messages(max_tokens=ctx.max_tokens)
                response = await ctx.llm.generate(messages, tools=tool_specs or None)
                total_input += response.usage.input_tokens
                total_output += response.usage.output_tokens

                if not response.tool_calls:
                    # Step complete
                    step_output = response.content
                    all_trace.append(
                        TraceEntry(
                            step=global_step,
                            thought=response.content,
                            action=f"step_{step_idx}:final",
                            result=response.content,
                        ).model_dump()
                    )
                    ctx.context_manager.add(
                        Message(role="assistant", content=response.content or "")
                    )
                    break

                # Tool calls
                thought = response.content
                ctx.context_manager.add(
                    Message(
                        role="assistant",
                        content=thought or "",
                        tool_calls=response.tool_calls,
                    )
                )

                for tc in response.tool_calls:
                    tool_impl = ctx.tools.get(tc.name)
                    if tool_impl is None:
                        tool_result = ToolResult(
                            output=f"Error: unknown tool '{tc.name}'", success=False
                        )
                    else:
                        try:
                            tool_result = await tool_impl.execute(
                                sandbox=ctx.sandbox, **tc.arguments
                            )
                        except Exception as exc:
                            tool_result = ToolResult(output=f"Error: {exc}", success=False)

                    all_trace.append(
                        TraceEntry(
                            step=global_step,
                            thought=thought,
                            action=f"step_{step_idx}:tool:{tc.name}",
                            tool_call=ToolCallRecord(
                                tool=tc.name,
                                args=tc.arguments,
                                result=tool_result.output,
                            ),
                            result=tool_result.output,
                        ).model_dump()
                    )
                    ctx.context_manager.add(
                        Message(
                            role="tool",
                            content=tool_result.output,
                            tool_call_id=tc.id,
                            name=tc.name,
                        )
                    )

            step_results.append(
                f"Step {step_idx} ({step_text}):\n{step_output or '(no output)'}"
            )

        # ------------------------------------------------------------------ #
        # Phase 3: Synthesis                                                   #
        # ------------------------------------------------------------------ #
        logger.info("Planner-Executor: synthesis phase")
        synthesis_input = (
            f"Task: {task_prompt}\n\n"
            f"Plan:\n{plan_text}\n\n"
            "Step results:\n"
            + "\n\n".join(step_results)
        )
        synth_messages = [
            Message(role="system", content=SYNTHESISER_SYSTEM),
            Message(role="user", content=synthesis_input),
        ]
        synth_response = await ctx.llm.generate(synth_messages, tools=None)
        total_input += synth_response.usage.input_tokens
        total_output += synth_response.usage.output_tokens

        global_step += 1
        final_output = synth_response.content
        all_trace.append(
            TraceEntry(
                step=global_step,
                thought=final_output,
                action="synthesis:final_answer",
                result=final_output,
            ).model_dump()
        )

        return LoopResult(
            success=None,
            output=final_output,
            trace=all_trace,
            steps=global_step,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
        )


def _parse_plan(plan_text: str, limit: int = 10) -> list[str]:
    """Extract numbered list items from planner output.

    Accepts patterns like:
      1. Do X
      1) Do X
      Step 1: Do X
    Returns a list of step strings (without the number prefix).
    """
    steps: list[str] = []
    pattern = re.compile(
        r"^\s*(?:step\s*)?\d+[.):\-]\s*(.+)", re.IGNORECASE | re.MULTILINE
    )
    for m in pattern.finditer(plan_text):
        steps.append(m.group(1).strip())
        if len(steps) >= limit:
            break
    return steps
