"""Repository search tool — grep and glob over files in the sandbox."""

from __future__ import annotations

from typing import Any

from agentlab.core.component import BaseSandbox, BaseTool, ToolResult
from agentlab.core.registry import register


@register("tool", "repo_search")
class RepoSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "repo_search"

    @property
    def description(self) -> str:
        return "Search repository files by content (grep) or name pattern (glob)."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["grep", "glob"],
                    "description": "'grep' to search file contents, 'glob' to match file names.",
                },
                "pattern": {
                    "type": "string",
                    "description": "Search pattern or glob expression.",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default '.').",
                },
            },
            "required": ["mode", "pattern"],
        }

    async def execute(
        self, sandbox: BaseSandbox | None = None, **kwargs: Any
    ) -> ToolResult:
        mode = kwargs.get("mode", "grep")
        pattern = kwargs.get("pattern", "")
        path = kwargs.get("path", ".")

        if sandbox is None:
            return ToolResult(output="Error: no sandbox available", success=False)

        try:
            if mode == "grep":
                result = await sandbox.execute(
                    f"grep -rn --include='*' '{pattern}' {path} 2>/dev/null | head -50"
                )
            elif mode == "glob":
                result = await sandbox.execute(
                    f"find {path} -name '{pattern}' 2>/dev/null | head -50"
                )
            else:
                return ToolResult(output=f"Unknown mode '{mode}'", success=False)

            output = result.stdout.strip() if result.stdout else "No matches found."
            return ToolResult(output=output, success=True)
        except Exception as exc:
            return ToolResult(output=f"Error: {exc}", success=False)
