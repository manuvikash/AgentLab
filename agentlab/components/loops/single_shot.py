"""Single-shot loop: one LLM call, one optional round of tool execution.

Useful as a zero-iteration baseline.
Two LLM calls at most:
  1. Initial prompt → model may request tool calls
  2. If tools were called, execute them, then one more LLM call for the final answer
If the model responds with plain text on the first call, that's the answer (one LLM call).
"""

from __future__ import annotations

import logging

from agentlab.core.component import BaseLoop, LoopResult, RuntimeContext, ToolResult
from agentlab.core.registry import register
from agentlab.models.schemas import Message, TraceEntry
from agentlab.skills.trace import enrich_tool_call_record

logger = logging.getLogger(__name__)

SINGLE_SHOT_SYSTEM_SUFFIX = (
    "\nYou operate in single-shot mode. "
    "You may call tools once to gather information, then give your final answer directly. "
    "Do not ask clarifying questions — produce the best answer you can with one round of tool use."
)


@register("loop", "single_shot")
class SingleShotLoop(BaseLoop):
    """Single-shot (zero-iteration) baseline loop.

    The model gets one chance to call tools; after executing them it produces
    one final response. Maximum two LLM calls total, regardless of complexity.
    Useful for evaluating how much iterative loops improve results.
    """

    async def run(self, ctx: RuntimeContext, task_prompt: str) -> LoopResult:
        trace: list[TraceEntry] = []
        total_input = 0
        total_output = 0

        system_prompt = (ctx.system_prompt or "") + SINGLE_SHOT_SYSTEM_SUFFIX
        ctx.context_manager.reset()
        ctx.context_manager.add(Message(role="system", content=system_prompt))
        ctx.context_manager.add(Message(role="user", content=task_prompt))

        tool_specs = [t.to_spec() for t in ctx.tools.values()]

        # --- Call 1: allow tool requests ---
        messages = ctx.context_manager.get_messages(max_tokens=ctx.max_tokens)
        response = await ctx.llm.generate(messages, tools=tool_specs or None)
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

        if not response.tool_calls:
            # Plain answer — we're done
            entry = TraceEntry(
                step=1,
                thought=response.content,
                action="final_answer",
                result=response.content,
            )
            trace.append(entry)
            return LoopResult(
                success=None,
                output=response.content,
                trace=[e.model_dump() for e in trace],
                steps=1,
                total_input_tokens=total_input,
                total_output_tokens=total_output,
            )

        # Record the assistant message requesting tools
        thought = response.content
        ctx.context_manager.add(
            Message(role="assistant", content=thought or "", tool_calls=response.tool_calls)
        )

        # --- Execute tools (single round) ---
        for tc in response.tool_calls:
            tool_impl = ctx.tools.get(tc.name)
            if tool_impl is None:
                tool_result = ToolResult(output=f"Error: unknown tool '{tc.name}'", success=False)
            else:
                try:
                    tool_result = await tool_impl.execute(sandbox=ctx.sandbox, **tc.arguments)
                except Exception as exc:
                    tool_result = ToolResult(output=f"Error: {exc}", success=False)

            trace.append(
                TraceEntry(
                    step=1,
                    thought=thought,
                    action=f"tool:{tc.name}",
                    tool_call=enrich_tool_call_record(
                        tc.name,
                        tc.arguments,
                        tool_result.output,
                        store=ctx.store,
                    ),
                    result=tool_result.output,
                )
            )
            ctx.context_manager.add(
                Message(
                    role="tool",
                    content=tool_result.output,
                    tool_call_id=tc.id,
                    name=tc.name,
                )
            )

        # --- Call 2: final answer after tools ---
        messages = ctx.context_manager.get_messages(max_tokens=ctx.max_tokens)
        final_response = await ctx.llm.generate(messages, tools=None)
        total_input += final_response.usage.input_tokens
        total_output += final_response.usage.output_tokens

        trace.append(
            TraceEntry(
                step=2,
                thought=final_response.content,
                action="final_answer",
                result=final_response.content,
            )
        )

        return LoopResult(
            success=None,
            output=final_response.content,
            trace=[e.model_dump() for e in trace],
            steps=2,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
        )
