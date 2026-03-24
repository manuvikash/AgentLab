"""ReAct (Reason + Act) loop controller."""

from __future__ import annotations

import logging

from agentlab.core.component import BaseLoop, LoopResult, RuntimeContext, ToolResult
from agentlab.core.registry import register
from agentlab.models.schemas import Message, TraceEntry
from agentlab.skills.trace import enrich_tool_call_record

logger = logging.getLogger(__name__)

REACT_SYSTEM_SUFFIX = (
    "\nYou operate in a Reason-then-Act loop. "
    "For each step: first think about what to do, then call a tool or provide a final answer. "
    "When you have completed the task, respond with your final answer without calling any tools."
)


@register("loop", "react")
class ReActLoop(BaseLoop):
    """Standard ReAct reasoning loop.

    Each iteration:
    1. Build messages from context manager
    2. Call LLM with available tools
    3. If LLM returns tool calls → execute them, record trace, loop
    4. If LLM returns text only → treat as final answer, stop
    """

    async def run(self, ctx: RuntimeContext, task_prompt: str) -> LoopResult:
        trace: list[TraceEntry] = []
        total_input = 0
        total_output = 0

        system_prompt = (ctx.system_prompt or "") + REACT_SYSTEM_SUFFIX
        ctx.context_manager.reset()
        ctx.context_manager.add(Message(role="system", content=system_prompt))
        ctx.context_manager.add(Message(role="user", content=task_prompt))

        tool_specs = [t.to_spec() for t in ctx.tools.values()]

        for step in range(1, ctx.max_steps + 1):
            messages = ctx.context_manager.get_messages(max_tokens=ctx.max_tokens)

            response = await ctx.llm.generate(messages, tools=tool_specs or None)
            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            if not response.tool_calls:
                entry = TraceEntry(
                    step=step,
                    thought=response.content,
                    action="final_answer",
                    result=response.content,
                )
                trace.append(entry)
                ctx.context_manager.add(
                    Message(role="assistant", content=response.content or "")
                )
                break

            # Add the assistant message that requested tool calls, including tool_calls
            thought = response.content
            assistant_msg = Message(
                role="assistant",
                content=thought or "",
                tool_calls=response.tool_calls,
            )
            ctx.context_manager.add(assistant_msg)

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

                entry = TraceEntry(
                    step=step,
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
                trace.append(entry)

                # Tool result message that satisfies the OpenAI tools protocol
                ctx.context_manager.add(
                    Message(
                        role="tool",
                        content=tool_result.output,
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

        success = None
        output = trace[-1].result if trace else None

        return LoopResult(
            success=success,
            output=output,
            trace=[e.model_dump() for e in trace],
            steps=len(set(e.step for e in trace)),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
        )
