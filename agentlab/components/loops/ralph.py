"""RALPH loop — Reflect, Act, Learn, Persist, Hypothesize.

A Reflexion-style outer loop around a ReAct inner loop.

Each attempt:
  1. Inject prior reflections from memory into the context.
  2. Run a bounded ReAct inner loop (inner_max_steps per attempt).
  3. If the attempt doesn't clearly succeed, ask the model to reflect on
     *what went wrong* and *what to try differently*.
  4. Store the reflection in memory under "ralph_reflection_{attempt}".
  5. Repeat up to max_attempts times.

The key differentiator from plain ReAct:
  - Reflection produces explicit verbal self-critique.
  - Past reflections accumulate across attempts so each run is smarter.
  - Memory is required; if ctx.memory is None a transient dict is used.

Reference: Shinn et al. (2023) "Reflexion: Language Agents with Verbal
Reinforcement Learning". https://arxiv.org/abs/2303.11366
"""

from __future__ import annotations

import logging
from typing import Any

from agentlab.core.component import BaseLoop, BaseMemory, LoopResult, RuntimeContext, ToolResult
from agentlab.core.registry import register
from agentlab.models.schemas import Message, ToolCallRecord, TraceEntry

logger = logging.getLogger(__name__)

RALPH_SYSTEM_SUFFIX = (
    "\nYou are operating in RALPH mode (Reflect, Act, Learn, Persist, Hypothesize). "
    "Work step-by-step using tools. When you are confident you have the final answer, "
    "respond with plain text (no tool calls)."
)

REFLECTION_PROMPT = (
    "You just completed an attempt at this task.\n"
    "Task: {task}\n\n"
    "Attempt trace summary:\n{trace_summary}\n\n"
    "Reflect critically:\n"
    "1. What went wrong or what was incomplete?\n"
    "2. What specific information or actions did you miss?\n"
    "3. What concrete strategy would you use on the NEXT attempt to do better?\n\n"
    "Be concise and specific. Your reflection will be shown to you at the start of the next attempt."
)

REFLECTION_INJECTION = (
    "--- Prior attempt {n} reflection ---\n{reflection}\n"
    "--- End of reflection ---"
)


class _TransientMemory(BaseMemory):
    """Fallback in-memory store used when ctx.memory is None."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def store(self, key: str, value: Any) -> None:
        self._store[key] = value

    def retrieve(self, key: str) -> Any | None:
        return self._store.get(key)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, Any]]:
        return list(self._store.items())[:top_k]

    def clear(self) -> None:
        self._store.clear()


@register("loop", "ralph")
class RALPHLoop(BaseLoop):
    """RALPH: Reflexion-based outer loop with persisted verbal self-critique.

    Parameters (passed at construction time from registry):
      max_attempts: int — outer retry count (default 3).
      inner_max_steps: int — ReAct steps allowed per attempt (default 10).
    """

    def __init__(self, max_attempts: int = 3, inner_max_steps: int = 10, **_: Any) -> None:
        self._max_attempts = max_attempts
        self._inner_max_steps = inner_max_steps

    async def run(self, ctx: RuntimeContext, task_prompt: str) -> LoopResult:
        memory: BaseMemory = ctx.memory or _TransientMemory()
        tool_specs = [t.to_spec() for t in ctx.tools.values()]
        all_trace: list[dict[str, Any]] = []
        total_input = 0
        total_output = 0
        final_output: str | None = None
        succeeded = False

        for attempt in range(1, self._max_attempts + 1):
            logger.info("RALPH attempt %d/%d", attempt, self._max_attempts)

            # --- Build context with prior reflections ---
            system_prompt = (ctx.system_prompt or "") + RALPH_SYSTEM_SUFFIX
            ctx.context_manager.reset()
            ctx.context_manager.add(Message(role="system", content=system_prompt))

            # Inject all past reflections as assistant context
            for prev in range(1, attempt):
                reflection = memory.retrieve(f"ralph_reflection_{prev}")
                if reflection:
                    ctx.context_manager.add(
                        Message(
                            role="user",
                            content=REFLECTION_INJECTION.format(n=prev, reflection=reflection),
                        )
                    )
                    ctx.context_manager.add(
                        Message(
                            role="assistant",
                            content="Understood. I will use this reflection to improve my approach.",
                        )
                    )

            ctx.context_manager.add(Message(role="user", content=task_prompt))

            # --- Inner ReAct-style loop (bounded by inner_max_steps) ---
            attempt_trace: list[TraceEntry] = []
            attempt_step_base = len(all_trace)  # global step offset for trace

            for step in range(1, self._inner_max_steps + 1):
                global_step = attempt_step_base + step
                messages = ctx.context_manager.get_messages(max_tokens=ctx.max_tokens)
                response = await ctx.llm.generate(messages, tools=tool_specs or None)
                total_input += response.usage.input_tokens
                total_output += response.usage.output_tokens

                if not response.tool_calls:
                    # Final answer for this attempt
                    entry = TraceEntry(
                        step=global_step,
                        thought=response.content,
                        action="final_answer",
                        result=response.content,
                    )
                    attempt_trace.append(entry)
                    ctx.context_manager.add(
                        Message(role="assistant", content=response.content or "")
                    )
                    final_output = response.content
                    succeeded = True  # Optimistically mark as succeeded when model stops
                    break

                # Tool call round
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

                    attempt_trace.append(
                        TraceEntry(
                            step=global_step,
                            thought=thought,
                            action=f"tool:{tc.name}",
                            tool_call=ToolCallRecord(
                                tool=tc.name,
                                args=tc.arguments,
                                result=tool_result.output,
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

            all_trace.extend(e.model_dump() for e in attempt_trace)

            if succeeded or attempt == self._max_attempts:
                break

            # --- Reflection: ask model what went wrong ---
            trace_summary = _summarise_trace(attempt_trace)
            reflection_prompt = REFLECTION_PROMPT.format(
                task=task_prompt, trace_summary=trace_summary
            )
            reflect_messages = [
                Message(role="system", content="You are a self-reflective AI agent."),
                Message(role="user", content=reflection_prompt),
            ]
            reflect_response = await ctx.llm.generate(reflect_messages, tools=None)
            total_input += reflect_response.usage.input_tokens
            total_output += reflect_response.usage.output_tokens

            reflection_text = reflect_response.content or "(no reflection)"
            memory.store(f"ralph_reflection_{attempt}", reflection_text)
            logger.info(
                "RALPH reflection for attempt %d: %s", attempt, reflection_text[:200]
            )

            # Record the reflection as a trace entry
            all_trace.append(
                TraceEntry(
                    step=len(all_trace) + 1,
                    thought=reflection_text,
                    action=f"reflection:attempt_{attempt}",
                    result=reflection_text,
                ).model_dump()
            )

        unique_steps = len(set(e["step"] for e in all_trace))
        return LoopResult(
            success=None,
            output=final_output,
            trace=all_trace,
            steps=unique_steps,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
        )


def _summarise_trace(trace: list[TraceEntry]) -> str:
    """Produce a concise text summary of an attempt's trace for reflection."""
    lines = []
    for e in trace:
        if e.action and e.action.startswith("tool:"):
            tool_name = e.action.split(":", 1)[1]
            result_preview = (e.result or "")[:300]
            lines.append(f"  • Called {tool_name} → {result_preview}")
        elif e.action == "final_answer":
            answer_preview = (e.result or "")[:300]
            lines.append(f"  • Final answer: {answer_preview}")
    return "\n".join(lines) if lines else "(no steps taken)"
