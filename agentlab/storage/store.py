"""File-based storage for runs, agents, experiments, and tasks."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from agentlab.models.schemas import (
    AgentConfig,
    ExperimentRecord,
    RunRecord,
    SkillDocument,
    TaskConfig,
)
from agentlab.skills.parser import meta_name_description, parse_skill_md, skill_instruction_body

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Max UTF-8 text returned by read_skill_bundle_file (UI preview).
_MAX_SKILL_BUNDLE_FILE_BYTES = 512_000


class Store:
    """Manages on-disk persistence for AgentLab artifacts.

    Directory layout::

        <root>/
            agents/       # YAML agent configs
            runs/         # run directories (metrics.json, trace.json, config.yaml)
            experiments/  # experiment records
            tasks/        # task definitions
            skills/       # skills/<id>/SKILL.md
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
    # Skills (skills/<skill_id>/SKILL.md)
    # ------------------------------------------------------------------

    @property
    def skills_dir(self) -> Path:
        return self._root / "skills"

    def _skill_id_ok(self, skill_id: str) -> bool:
        if not skill_id or skill_id.strip() != skill_id:
            return False
        if "/" in skill_id or "\\" in skill_id or ".." in skill_id:
            return False
        return True

    def skill_md_path(self, skill_id: str) -> Path:
        if not self._skill_id_ok(skill_id):
            raise ValueError(f"Invalid skill id: {skill_id!r}")
        return self.skills_dir / skill_id / "SKILL.md"

    def read_skill_raw(self, skill_id: str) -> str:
        path = self.skill_md_path(skill_id)
        if not path.exists():
            raise FileNotFoundError(f"SKILL.md not found: {path}")
        return path.read_text(encoding="utf-8")

    def load_skill_name_description(self, skill_id: str) -> tuple[str, str]:
        raw = self.read_skill_raw(skill_id)
        meta, _body = parse_skill_md(raw)
        name, desc = meta_name_description(meta)
        if not name:
            name = skill_id
        return name, desc

    def skill_instruction_for_tool(self, skill_id: str) -> str:
        """Body of SKILL.md for LLM tool result (progressive disclosure)."""
        raw = self.read_skill_raw(skill_id)
        return skill_instruction_body(raw)

    def list_skill_ids(self) -> list[str]:
        if not self.skills_dir.exists():
            return []
        ids: list[str] = []
        for d in sorted(self.skills_dir.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                ids.append(d.name)
        return ids

    def load_skill_document(self, skill_id: str) -> SkillDocument:
        raw = self.read_skill_raw(skill_id)
        meta, body = parse_skill_md(raw)
        name, desc = meta_name_description(meta)
        return SkillDocument(
            id=skill_id,
            name=name or skill_id,
            description=desc,
            body=body,
        )

    def save_skill_document(self, doc: SkillDocument) -> Path:
        if not self._skill_id_ok(doc.id):
            raise ValueError(f"Invalid skill id: {doc.id!r}")
        skill_dir = self.skills_dir / doc.id
        skill_dir.mkdir(parents=True, exist_ok=True)
        fm = yaml.dump(
            {"name": doc.name, "description": doc.description},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        text = f"---\n{fm}\n---\n{doc.body}"
        path = skill_dir / "SKILL.md"
        path.write_text(text, encoding="utf-8")
        return path

    def delete_skill(self, skill_id: str) -> None:
        skill_dir = self.skills_dir / skill_id
        if not self._skill_id_ok(skill_id):
            raise ValueError(f"Invalid skill id: {skill_id!r}")
        if skill_dir.exists() and skill_dir.is_dir():
            shutil.rmtree(skill_dir)

    def _skill_bundle_root(self, skill_id: str) -> Path:
        if not self._skill_id_ok(skill_id):
            raise ValueError(f"Invalid skill id: {skill_id!r}")
        root = (self.skills_dir / skill_id).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Skill directory not found: {root}")
        return root

    def resolve_skill_bundle_path(self, skill_id: str, rel_path: str) -> Path:
        """Resolve a path inside skills/<skill_id>/; rejects traversal outside."""
        root = self._skill_bundle_root(skill_id)
        rel = (rel_path or "").strip().replace("\\", "/")
        if not rel or rel.startswith("/"):
            raise ValueError("Invalid path")
        if ".." in Path(rel).parts:
            raise ValueError("Invalid path")
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("Invalid path") from exc
        return target

    def skill_file_tree(self, skill_id: str) -> dict[str, Any]:
        """Nested directory listing for UI (name, kind, path, size for files)."""
        root = self._skill_bundle_root(skill_id)
        return self._skill_file_tree_node(root, root)

    def _skill_file_tree_node(self, path: Path, root: Path) -> dict[str, Any]:
        rel = path.relative_to(root)
        rel_str = "" if rel == Path(".") else str(rel).replace("\\", "/")
        name = path.name if rel != Path(".") else root.name

        if path.is_file():
            return {
                "path": rel_str,
                "name": name,
                "kind": "file",
                "size": path.stat().st_size,
            }

        children: list[dict[str, Any]] = []
        for child in sorted(
            path.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        ):
            if child.name == "__pycache__":
                continue
            children.append(self._skill_file_tree_node(child, root))

        return {
            "path": rel_str,
            "name": name,
            "kind": "dir",
            "children": children,
        }

    def read_skill_bundle_file(self, skill_id: str, rel_path: str) -> str:
        """Read a UTF-8 text file under the skill bundle; raises if binary or too large."""
        target = self.resolve_skill_bundle_path(skill_id, rel_path)
        if not target.is_file():
            raise FileNotFoundError(f"Not a file: {target}")
        data = target.read_bytes()
        if len(data) > _MAX_SKILL_BUNDLE_FILE_BYTES:
            raise ValueError(
                f"File too large to preview (max {_MAX_SKILL_BUNDLE_FILE_BYTES} bytes)"
            )
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("File is not valid UTF-8 text") from exc

    def list_skill_documents(self) -> list[SkillDocument]:
        out: list[SkillDocument] = []
        for sid in self.list_skill_ids():
            try:
                out.append(self.load_skill_document(sid))
            except Exception as exc:
                logger.warning("Failed to load skill %s: %s", sid, exc)
        return out

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
