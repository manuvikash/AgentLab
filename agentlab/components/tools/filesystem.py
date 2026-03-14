"""Filesystem tool — read, write, and list files via the sandbox."""

from __future__ import annotations

from typing import Any

from agentlab.core.component import BaseSandbox, BaseTool, ToolResult
from agentlab.core.registry import register


@register("tool", "filesystem")
class FilesystemTool(BaseTool):
    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def description(self) -> str:
        return "Read, write, or list files in the workspace."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "list"],
                    "description": "The filesystem operation to perform.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (only for 'write' action).",
                },
            },
            "required": ["action", "path"],
        }

    async def execute(
        self, sandbox: BaseSandbox | None = None, **kwargs: Any
    ) -> ToolResult:
        action = kwargs.get("action", "")
        path = kwargs.get("path", ".")
        content = kwargs.get("content", "")

        if sandbox is None:
            return ToolResult(output="Error: no sandbox available", success=False)

        try:
            if action == "read":
                text = await sandbox.read_file(path)
                return ToolResult(output=text)
            elif action == "write":
                await sandbox.write_file(path, content)
                return ToolResult(output=f"Wrote {len(content)} chars to {path}")
            elif action == "list":
                files = await sandbox.list_files(path)
                return ToolResult(output="\n".join(files))
            else:
                return ToolResult(
                    output=f"Unknown action '{action}'", success=False
                )
        except Exception as exc:
            return ToolResult(output=f"Error: {exc}", success=False)
