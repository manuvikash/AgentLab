"""File-based storage for runs, agents, experiments, and tasks."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from agentlab.models.schemas import (
    AgentConfig,
    ExperimentRecord,
    RunRecord,
    TaskConfig,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class Store:
    """Manages on-disk persistence for AgentLab artifacts.

    Directory layout::

        <root>/
            agents/       # YAML agent configs
            runs/         # run directories (metrics.json, trace.json, config.yaml)
            experiments/  # experiment records
            tasks/        # task definitions
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self._root = Path(root) if root else Path.cwd()

    @property
    def root(self) -> Path:
        return self._root

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    @property
    def agents_dir(self) -> Path:
        return self._root / "agents"

    def save_agent(self, config: AgentConfig) -> Path:
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        path = self.agents_dir / f"{config.name}.yaml"
        path.write_text(yaml.dump(config.model_dump(), sort_keys=False), encoding="utf-8")
        return path

    def load_agent(self, name: str) -> AgentConfig:
        path = self.agents_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Agent config not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return AgentConfig(**data)

    def delete_agent(self, name: str) -> None:
        path = self.agents_dir / f"{name}.yaml"
        if path.exists():
            path.unlink()

    def list_agents(self) -> list[AgentConfig]:
        if not self.agents_dir.exists():
            return []
        agents = []
        for p in sorted(self.agents_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8"))
                agents.append(AgentConfig(**data))
            except Exception as exc:
                logger.warning("Failed to load agent %s: %s", p, exc)
        return agents

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    @property
    def runs_dir(self) -> Path:
        return self._root / "runs"

    def save_run(self, run: RunRecord) -> Path:
        run_dir = self.runs_dir / run.id
        run_dir.mkdir(parents=True, exist_ok=True)

        (run_dir / "run.json").write_text(
            run.model_dump_json(indent=2), encoding="utf-8"
        )

        metrics_data = run.metrics.model_dump()
        (run_dir / "metrics.json").write_text(
            json.dumps(metrics_data, indent=2), encoding="utf-8"
        )

        trace_data = [e.model_dump() for e in run.trace]
        (run_dir / "trace.json").write_text(
            json.dumps(trace_data, indent=2, default=str), encoding="utf-8"
        )

        if run.agent_config:
            (run_dir / "config.yaml").write_text(
                yaml.dump(run.agent_config.model_dump(), sort_keys=False),
                encoding="utf-8",
            )

        return run_dir

    def load_run(self, run_id: str) -> RunRecord:
        path = self.runs_dir / run_id / "run.json"
        if not path.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")
        return RunRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def delete_run(self, run_id: str) -> None:
        run_dir = self.runs_dir / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)

    def list_runs(self) -> list[RunRecord]:
        if not self.runs_dir.exists():
            return []
        runs = []
        for d in sorted(self.runs_dir.iterdir()):
            run_file = d / "run.json"
            if run_file.exists():
                try:
                    runs.append(
                        RunRecord.model_validate_json(
                            run_file.read_text(encoding="utf-8")
                        )
                    )
                except Exception as exc:
                    logger.warning("Failed to load run %s: %s", d.name, exc)
        return runs

    # ------------------------------------------------------------------
    # Experiments
    # ------------------------------------------------------------------

    @property
    def experiments_dir(self) -> Path:
        return self._root / "experiments"

    def save_experiment(self, experiment: ExperimentRecord) -> Path:
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        path = self.experiments_dir / f"{experiment.id}.json"
        path.write_text(experiment.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_experiment(self, experiment_id: str) -> ExperimentRecord:
        path = self.experiments_dir / f"{experiment_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Experiment not found: {experiment_id}")
        return ExperimentRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def delete_experiment(self, experiment_id: str) -> None:
        path = self.experiments_dir / f"{experiment_id}.json"
        if path.exists():
            path.unlink()

    def list_experiments(self) -> list[ExperimentRecord]:
        if not self.experiments_dir.exists():
            return []
        experiments = []
        for p in sorted(self.experiments_dir.glob("*.json")):
            try:
                experiments.append(
                    ExperimentRecord.model_validate_json(
                        p.read_text(encoding="utf-8")
                    )
                )
            except Exception as exc:
                logger.warning("Failed to load experiment %s: %s", p, exc)
        return experiments

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @property
    def tasks_dir(self) -> Path:
        return self._root / "tasks"

    def get_task_dir(self, task_id: str) -> Path:
        """Return the directory containing task.yaml for this task (for resolving repo paths)."""
        for candidate in [
            self.tasks_dir / task_id / "task.yaml",
            *self.tasks_dir.rglob(f"{task_id}/task.yaml"),
        ]:
            if candidate.exists():
                return candidate.parent
        raise FileNotFoundError(f"Task not found: {task_id}")

    def load_task(self, task_id: str) -> TaskConfig:
        """Load a task by searching for task.yaml under tasks/.

        Supports both flat (tasks/<id>/task.yaml) and nested
        (tasks/<category>/<id>/task.yaml) layouts.
        """
        for candidate in [
            self.tasks_dir / task_id / "task.yaml",
            *self.tasks_dir.rglob(f"{task_id}/task.yaml"),
        ]:
            if candidate.exists():
                data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                if "id" not in data:
                    data["id"] = task_id
                return TaskConfig(**data)
        raise FileNotFoundError(f"Task not found: {task_id}")

    def save_task(self, task: TaskConfig) -> Path:
        task_dir = self.tasks_dir / task.id
        task_dir.mkdir(parents=True, exist_ok=True)
        path = task_dir / "task.yaml"
        path.write_text(
            yaml.dump(task.model_dump(), sort_keys=False), encoding="utf-8"
        )
        return path

    def delete_task(self, task_id: str) -> None:
        try:
            task_dir = self.get_task_dir(task_id)
            shutil.rmtree(task_dir)
        except FileNotFoundError:
            pass

    def list_tasks(self) -> list[TaskConfig]:
        if not self.tasks_dir.exists():
            return []
        tasks = []
        for p in sorted(self.tasks_dir.rglob("task.yaml")):
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8"))
                if "id" not in data:
                    data["id"] = p.parent.name
                tasks.append(TaskConfig(**data))
            except Exception as exc:
                logger.warning("Failed to load task %s: %s", p, exc)
        return tasks
