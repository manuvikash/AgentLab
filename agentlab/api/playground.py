"""Playground API: chat-style conversations with registered agents.

Endpoints
---------
GET    /api/conversations                  – list all conversations
POST   /api/conversations                  – create a new conversation (bind an agent)
GET    /api/conversations/{id}             – get conversation + all messages
DELETE /api/conversations/{id}             – delete conversation and its messages
POST   /api/conversations/{id}/messages    – send a user turn; **streams SSE events** back

SSE event format (``data: <json>\\n\\n``)
-----------------------------------------
{"event": "thinking",     "step": N, "content": "..."}
{"event": "tool_call",    "step": N, "tool": "...", "args": {...}}
{"event": "tool_result",  "step": N, "tool": "...", "result": "..."}
{"event": "final",        "content": "...", "message_id": <int>}
{"event": "error",        "message": "..."}
{"event": "done"}
"""

from __future__ import annotations

import json
import logging
from asyncio import CancelledError
from typing import AsyncGenerator

import agentlab.components  # noqa: F401 — trigger auto-registration
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agentlab.core.component import RuntimeContext, ToolResult
from agentlab.core.registry import get_registry
from agentlab.models.schemas import (
    AgentConfig,
    ConversationMessage,
    ConversationRecord,
    Message,
    TraceEntry,
    ToolCallRecord,
)
from agentlab.storage.conversation_store import ConversationStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["playground"])

_conv_store: ConversationStore | None = None


def get_conv_store() -> ConversationStore:
    global _conv_store
    if _conv_store is None:
        from pathlib import Path
        _conv_store = ConversationStore(Path.cwd() / "conversations.db")
    return _conv_store


def set_conv_store(store: ConversationStore) -> None:
    global _conv_store
    _conv_store = store


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    agent_name: str


class SendMessageRequest(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_conversations(agent: str | None = None):
    return [c.model_dump() for c in get_conv_store().list_conversations(agent)]


@router.post("", status_code=201)
def create_conversation(req: CreateConversationRequest):
    from agentlab.api.routes import get_store

    try:
        agent_config = get_store().load_agent(req.agent_name)
    except FileNotFoundError:
        raise HTTPException(404, f"Agent '{req.agent_name}' not found")

    record = ConversationRecord(
        agent_name=req.agent_name,
        agent_snapshot=agent_config,
    )
    get_conv_store().create_conversation(record)
    return record.model_dump()


@router.get("/{conv_id}")
def get_conversation(conv_id: str):
    store = get_conv_store()
    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(404, f"Conversation '{conv_id}' not found")
    messages = store.get_messages(conv_id)
    result = conv.model_dump()
    result["messages"] = [m.model_dump() for m in messages]
    return result


@router.delete("/{conv_id}", status_code=204)
def delete_conversation(conv_id: str):
    store = get_conv_store()
    if store.get_conversation(conv_id) is None:
        raise HTTPException(404, f"Conversation '{conv_id}' not found")
    store.delete_conversation(conv_id)


@router.post("/{conv_id}/messages")
async def send_message(conv_id: str, req: SendMessageRequest):
    """Send a user message; response is an SSE stream of agent reasoning steps."""
    store = get_conv_store()
    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(404, f"Conversation '{conv_id}' not found")
    if not conv.agent_snapshot:
        raise HTTPException(400, "Conversation has no agent snapshot — cannot run agent")

    history = store.get_messages(conv_id)
    user_seq = store.next_seq(conv_id)

    return StreamingResponse(
        _run_turn(conv_id, req.content, conv.agent_snapshot, history, user_seq, store),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# SSE streaming agent turn
# ---------------------------------------------------------------------------


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _run_turn(
    conv_id: str,
    user_content: str,
    agent_config: AgentConfig,
    history: list[ConversationMessage],
    user_seq: int,
    store: ConversationStore,
) -> AsyncGenerator[str, None]:
    # 1. Persist the user message immediately
    user_msg = ConversationMessage(
        conversation_id=conv_id,
        seq=user_seq,
        role="user",
        content=user_content,
    )
    store.add_message(user_msg)

    # Auto-title from first user turn
    if user_seq == 1:
        title = user_content[:60].strip()
        store.update_conversation_title(conv_id, title)

    # 2. Resolve agent components
    registry = get_registry()
    try:
        llm = registry.create("llm", agent_config.llm)
        context_mgr = registry.create("context", agent_config.context)
        tools_list = [registry.create("tool", t) for t in agent_config.tools]
        sandbox = registry.create("sandbox", agent_config.sandbox)
        memory = (
            registry.create("memory", agent_config.memory)
            if agent_config.memory
            else None
        )
    except Exception as exc:
        yield _sse({"event": "error", "message": f"Failed to resolve components: {exc}"})
        yield _sse({"event": "done"})
        return

    ctx = RuntimeContext(
        llm=llm,
        context_manager=context_mgr,
        tools=tools_list,
        sandbox=sandbox,
        memory=memory,
        system_prompt=agent_config.prompt,
        max_steps=agent_config.max_steps,
        max_tokens=agent_config.max_tokens,
    )

    # 3. Replay conversation history into the context manager
    if agent_config.prompt:
        ctx.context_manager.add(Message(role="system", content=agent_config.prompt))

    for msg in history:
        ctx.context_manager.add(Message(role=msg.role, content=msg.content or ""))

    ctx.context_manager.add(Message(role="user", content=user_content))

    tool_specs = [t.to_spec() for t in ctx.tools.values()]
    tools_map = ctx.tools
    trace_entries: list[TraceEntry] = []

    # 4. Run the ReAct loop, yielding SSE events at each step
    try:
        async with sandbox:
            for step in range(1, agent_config.max_steps + 1):
                messages = ctx.context_manager.get_messages(
                    max_tokens=agent_config.max_tokens
                )
                response = await ctx.llm.generate(messages, tools=tool_specs or None)

                if not response.tool_calls:
                    # Final answer
                    entry = TraceEntry(
                        step=step,
                        thought=response.content,
                        action="final_answer",
                        result=response.content,
                    )
                    trace_entries.append(entry)
                    ctx.context_manager.add(
                        Message(role="assistant", content=response.content or "")
                    )
                    yield _sse(
                        {
                            "event": "thinking",
                            "step": step,
                            "content": response.content or "",
                        }
                    )
                    break

                # Thinking / tool-requesting step
                thought = response.content
                if thought:
                    yield _sse({"event": "thinking", "step": step, "content": thought})

                ctx.context_manager.add(
                    Message(
                        role="assistant",
                        content=thought or "",
                        tool_calls=response.tool_calls,
                    )
                )

                for tc in response.tool_calls:
                    yield _sse(
                        {
                            "event": "tool_call",
                            "step": step,
                            "tool": tc.name,
                            "args": tc.arguments,
                        }
                    )

                    tool_impl = tools_map.get(tc.name)
                    if tool_impl is None:
                        result = ToolResult(
                            output=f"Error: unknown tool '{tc.name}'", success=False
                        )
                    else:
                        try:
                            result = await tool_impl.execute(
                                sandbox=sandbox, **tc.arguments
                            )
                        except Exception as exc:
                            result = ToolResult(output=f"Error: {exc}", success=False)

                    entry = TraceEntry(
                        step=step,
                        thought=thought,
                        action=f"tool:{tc.name}",
                        tool_call=ToolCallRecord(
                            tool=tc.name,
                            args=tc.arguments,
                            result=result.output,
                        ),
                        result=result.output,
                    )
                    trace_entries.append(entry)

                    yield _sse(
                        {
                            "event": "tool_result",
                            "step": step,
                            "tool": tc.name,
                            "result": result.output,
                        }
                    )

                    ctx.context_manager.add(
                        Message(
                            role="tool",
                            content=result.output,
                            tool_call_id=tc.id,
                            name=tc.name,
                        )
                    )

    except CancelledError:
        yield _sse({"event": "error", "message": "Request cancelled"})
        yield _sse({"event": "done"})
        return
    except Exception as exc:
        logger.exception("Playground agent turn failed")
        yield _sse({"event": "error", "message": str(exc)})
        yield _sse({"event": "done"})
        return

    # 5. Persist the assistant message with full trace
    final_content = trace_entries[-1].result if trace_entries else ""
    assistant_seq = store.next_seq(conv_id)
    assistant_msg = ConversationMessage(
        conversation_id=conv_id,
        seq=assistant_seq,
        role="assistant",
        content=final_content,
        trace=[e.model_dump(mode="json") for e in trace_entries],
    )
    store.add_message(assistant_msg)

    yield _sse(
        {
            "event": "final",
            "content": final_content,
            "message_id": assistant_msg.id,
        }
    )
    yield _sse({"event": "done"})
