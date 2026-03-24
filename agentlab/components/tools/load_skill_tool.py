"""Load full SKILL.md body for a configured skill (progressive disclosure)."""

from __future__ import annotations

from typing import Any

from agentlab.core.component import BaseSandbox, BaseTool, ToolResult
from agentlab.core.registry import register
from agentlab.storage.store import Store


@register("tool", "load_skill")
class LoadSkillTool(BaseTool):
    """Expose skill_id -> instruction body; only ids listed on the agent are allowed."""

    def __init__(
        self,
        store: Store | None = None,
        allowed_skill_ids: list[str] | None = None,
    ) -> None:
        self._store = store
        self._allowed = frozenset(allowed_skill_ids or [])

    @property
    def name(self) -> str:
        return "load_skill"

    @property
    def description(self) -> str:
        return (
            "Load the full instructions for a skill (SKILL.md body). "
            "Only skills configured for this agent can be loaded. "
            "Use when you need detailed guidance beyond the catalog summary."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "The skill directory id (as listed in Available skills).",
                },
            },
            "required": ["skill_id"],
        }

    async def execute(
        self, sandbox: BaseSandbox | None = None, **kwargs: Any
    ) -> ToolResult:
        del sandbox  # unused
        skill_id = str(kwargs.get("skill_id") or "").strip()
        if not skill_id:
            return ToolResult(output="Error: skill_id is required", success=False)

        if skill_id not in self._allowed:
            return ToolResult(
                output=(
                    f"Error: skill '{skill_id}' is not enabled for this agent. "
                    f"Allowed: {sorted(self._allowed)}"
                ),
                success=False,
            )

        if self._store is None:
            return ToolResult(output="Error: skill store not configured", success=False)

        try:
            body = self._store.skill_instruction_for_tool(skill_id)
        except FileNotFoundError:
            return ToolResult(
                output=f"Error: SKILL.md not found for skill '{skill_id}'",
                success=False,
            )
        except Exception as exc:
            return ToolResult(output=f"Error: {exc}", success=False)

        return ToolResult(output=body)
