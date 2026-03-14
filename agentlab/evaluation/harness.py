"""SWE evaluation harness — run an agent against a task and validate results."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from agentlab.core.registry import get_registry
from agentlab.evaluation.metrics import MetricsCollector
from agentlab.models.schemas import AgentConfig, RunRecord, TaskConfig
from agentlab.runtime.runner import AgentRunner
from agentlab.storage.store import Store

logger = logging.getLogger(__name__)


class EvalHarness:
    """Orchestrates the full evaluation workflow:

    1. Load task (repo, prompt, validator)
    2. Set up sandbox with the repo
    3. Run agent
    4. Execute validator inside sandbox
    5. Compute metrics
    6. Update and persist the run record
    """

    def __init__(self, store: Store | None = None) -> None:
        self._store = store or Store()
        self._runner = AgentRunner(store=self._store)
        self._metrics = MetricsCollector()
        self._registry = get_registry()

    async def evaluate(
        self,
        agent_config: AgentConfig,
        task: TaskConfig,
    ) -> RunRecord:
        """Run an agent on a task and validate the result.

        For tasks with a repo, this method:
        - Locates the task repo
        - Copies it into a fresh temporary directory
        - Forces the sandbox to Docker so all modifications happen inside
          a container and against the temp copy
        """
        sandbox_kwargs: dict = {}
        config_for_run = agent_config
        temp_root: Path | None = None

        if task.repo:
            # Resolve the original repo, then copy it into an isolated temp dir.
            original_repo = self._resolve_repo(task)
            temp_root = Path(tempfile.mkdtemp(prefix=f"agentlab_{task.id}_"))
            temp_repo = temp_root / "repo"
            logger.info("Copying repo for task %s to %s", task.id, temp_repo)
            shutil.copytree(original_repo, temp_repo, dirs_exist_ok=True)
            sandbox_kwargs["workdir"] = str(temp_repo)

            # Force Docker sandbox for repo tasks so all edits happen in a container
            config_for_run = agent_config.model_copy()
            config_for_run.sandbox = "docker"

        run = await self._runner.run(
            config_for_run,
            task_prompt=task.prompt,
            task_id=task.id,
            **sandbox_kwargs,
        )

        validator_passed = None
        patch_diff = None

        if task.validator:
            validator_passed = await self._run_validator(
                task, sandbox_kwargs.get("workdir")
            )

        if sandbox_kwargs.get("workdir"):
            patch_diff = await self._generate_diff(sandbox_kwargs["workdir"])

        run.metrics = self._metrics.compute(
            run, validator_passed=validator_passed, patch_diff=patch_diff
        )
        self._store.save_run(run)

        if patch_diff:
            run_dir = self._store.runs_dir / run.id
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "patch.diff").write_text(patch_diff, encoding="utf-8")

        return run

    def _resolve_repo(self, task: TaskConfig) -> Path:
        """Find the repo directory for a task (relative to the task's directory)."""
        if not task.repo:
            raise FileNotFoundError(f"Task {task.id} has no repo specified")
        repo = Path(task.repo)
        if repo.is_absolute() and repo.exists():
            return repo
        # Resolve relative to the directory that contains this task's task.yaml
        task_dir = self._store.get_task_dir(task.id)
        candidate = task_dir / task.repo
        if candidate.exists():
            return candidate
        # Fallbacks
        for candidate in [
            self._store.tasks_dir / task.id / task.repo,
            self._store.tasks_dir / task.repo,
            Path(task.repo),
        ]:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Repo not found for task {task.id}: {task.repo}")

    async def _run_validator(
        self, task: TaskConfig, workdir: str | None
    ) -> bool:
        """Execute the task validator and return pass/fail."""
        sandbox = self._registry.create("sandbox", "local", workdir=workdir or ".")

        async with sandbox:
            for cmd in task.setup_commands:
                await sandbox.execute(cmd)

            validator = task.validator or ""
            if validator.endswith(".py"):
                result = await sandbox.execute(f"python {validator}", timeout=120)
            else:
                result = await sandbox.execute(validator, timeout=120)

            logger.info(
                "Validator exit_code=%d stdout=%s",
                result.exit_code,
                result.stdout[:200],
            )
            return result.success

    async def _generate_diff(self, workdir: str) -> str | None:
        """Generate a git diff from the workdir if it's a git repo."""
        import asyncio

        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
            stdout, _ = await proc.communicate()
            diff = stdout.decode(errors="replace").strip()
            return diff if diff else None
        except Exception:
            return None
