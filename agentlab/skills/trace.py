"""Enrich trace ToolCallRecord for load_skill with skill_id / skill_name."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentlab.models.schemas import ToolCallRecord

if TYPE_CHECKING:
    from agentlab.storage.store import Store


def enrich_tool_call_record(
    tool: str,
    args: dict,
    result: str | None,
    *,
    store: "Store | None",
) -> ToolCallRecord:
    """Build ToolCallRecord; add skill_name when tool is load_skill."""
    rec = ToolCallRecord(tool=tool, args=args, result=result)
    if tool != "load_skill" or store is None:
        return rec

    sid = str(args.get("skill_id") or "").strip()
    if not sid:
        return rec

    rec.skill_id = sid
    try:
        name, _desc = store.load_skill_name_description(sid)
        rec.skill_name = name or None
    except (FileNotFoundError, OSError, ValueError):
        pass
    return rec
