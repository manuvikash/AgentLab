"""Local sandbox — executes commands directly on the host filesystem."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from agentlab.core.component import BaseSandbox, ExecutionResult
from agentlab.core.registry import register


@register("sandbox", "local")
class LocalSandbox(BaseSandbox):
    """Runs commands in a local working directory. No isolation."""

    def __init__(self, workdir: str | None = None, **kwargs: Any) -> None:
        self._workdir = Path(workdir) if workdir else Path.cwd()

    async def start(self) -> None:
        self._workdir.mkdir(parents=True, exist_ok=True)

    async def stop(self) -> None:
        pass

    async def execute(
        self, command: str, timeout: int | None = None
    ) -> ExecutionResult:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._workdir),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout or 60
            )
            return ExecutionResult(
                exit_code=proc.returncode or 0,
                stdout=stdout_bytes.decode(errors="replace"),
                stderr=stderr_bytes.decode(errors="replace"),
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ExecutionResult(exit_code=-1, stdout="", stderr="Command timed out")
        except Exception as exc:
            return ExecutionResult(exit_code=-1, stdout="", stderr=str(exc))

    async def read_file(self, path: str) -> str:
        full = self._resolve(path)
        return full.read_text(encoding="utf-8")

    async def write_file(self, path: str, content: str) -> None:
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    async def list_files(self, path: str = ".") -> list[str]:
        full = self._resolve(path)
        if not full.is_dir():
            return []
        entries: list[str] = []
        for item in sorted(full.iterdir()):
            rel = str(item.relative_to(self._workdir))
            entries.append(rel + ("/" if item.is_dir() else ""))
        return entries

    def _resolve(self, path: str) -> Path:
        target = (self._workdir / path).resolve()
        base = self._workdir.resolve()
        if not str(target).startswith(str(base)):
            raise PermissionError(f"Path escapes sandbox: {path}")
        return target
