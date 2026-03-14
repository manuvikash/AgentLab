"""Docker sandbox — executes commands in an isolated container."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

from agentlab.core.component import BaseSandbox, ExecutionResult
from agentlab.core.registry import register

logger = logging.getLogger(__name__)


@register("sandbox", "docker")
class DockerSandbox(BaseSandbox):
    """Runs commands inside a Docker container for isolation."""

    def __init__(
        self,
        image: str = "python:3.11-slim",
        workdir: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._image = image
        self._host_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="agentlab_"))
        self._container_workdir = "/workspace"
        self._container_id: str | None = None

    async def start(self) -> None:
        self._host_dir.mkdir(parents=True, exist_ok=True)
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "run",
            "-d",
            "--rm",
            "-v",
            f"{self._host_dir}:{self._container_workdir}",
            "-w",
            self._container_workdir,
            self._image,
            "sleep",
            "infinity",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to start Docker container: {stderr.decode()}")
        self._container_id = stdout.decode().strip()
        logger.info("Started Docker container %s", self._container_id[:12])

    async def stop(self) -> None:
        if self._container_id:
            proc = await asyncio.create_subprocess_exec(
                "docker", "kill", self._container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            logger.info("Stopped Docker container %s", self._container_id[:12])
            self._container_id = None

    async def execute(
        self, command: str, timeout: int | None = None
    ) -> ExecutionResult:
        if not self._container_id:
            raise RuntimeError("Container not started")

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                self._container_id,
                "sh",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout or 60
            )
            return ExecutionResult(
                exit_code=proc.returncode or 0,
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
            )
        except asyncio.TimeoutError:
            return ExecutionResult(exit_code=-1, stdout="", stderr="Command timed out")

    async def read_file(self, path: str) -> str:
        full = self._host_dir / path
        return full.read_text(encoding="utf-8")

    async def write_file(self, path: str, content: str) -> None:
        full = self._host_dir / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    async def list_files(self, path: str = ".") -> list[str]:
        full = self._host_dir / path
        if not full.is_dir():
            return []
        return [
            str(p.relative_to(self._host_dir)) + ("/" if p.is_dir() else "")
            for p in sorted(full.iterdir())
        ]
