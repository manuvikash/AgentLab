"""Shell tool — execute commands in the sandbox."""

from __future__ import annotations

from typing import Any

from agentlab.core.component import BaseSandbox, BaseTool, ToolResult
from agentlab.core.registry import register


@register("tool", "shell")
class ShellTool(BaseTool):
    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute a shell command in the sandbox environment."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 60).",
                },
            },
            "required": ["command"],
        }

    async def execute(
        self, sandbox: BaseSandbox | None = None, **kwargs: Any
    ) -> ToolResult:
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 60)

        if sandbox is None:
            return ToolResult(output="Error: no sandbox available", success=False)

        if not command:
            return ToolResult(output="Error: empty command", success=False)

        try:
            result = await sandbox.execute(command, timeout=timeout)
            return ToolResult(output=result.output, success=result.success)
        except Exception as exc:
            return ToolResult(output=f"Error: {exc}", success=False)
