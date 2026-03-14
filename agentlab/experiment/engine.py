"""Experiment engine — parameter sweeps across agent configurations."""

from __future__ import annotations

import itertools
import logging
from datetime import datetime, timezone
from typing import Any

from agentlab.models.schemas import (
    AgentConfig,
    ExperimentConfig,
    ExperimentRecord,
    RunRecord,
)
from agentlab.runtime.runner import AgentRunner
from agentlab.storage.store import Store

logger = logging.getLogger(__name__)

MATRIX_TO_CONFIG_FIELD = {
    "llm": "llm",
    "loop": "loop",
    "context": "context",
    "sandbox": "sandbox",
    "memory": "memory",
}


class ExperimentEngine:
    """Runs parameter sweeps by generating the Cartesian product of matrix values."""

    def __init__(self, store: Store | None = None) -> None:
        self._store = store or Store()
        self._runner = AgentRunner(store=self._store)

    def generate_configs(self, experiment: ExperimentConfig) -> list[AgentConfig]:
        """Expand the experiment matrix into individual AgentConfigs."""
        keys = list(experiment.matrix.keys())
        value_lists = [experiment.matrix[k] for k in keys]
        configs: list[AgentConfig] = []

        for combo in itertools.product(*value_lists):
            params: dict[str, Any] = dict(experiment.base)
            for key, value in zip(keys, combo):
                field = MATRIX_TO_CONFIG_FIELD.get(key, key)
                if field == "tools":
                    params[field] = value if isinstance(value, list) else [value]
                else:
                    params[field] = value

            label_parts = [f"{k}={v}" for k, v in zip(keys, combo)]
            params.setdefault("name", f"{experiment.name}_{'_'.join(label_parts)}")

            if "tools" in params and isinstance(params["tools"], str):
                params["tools"] = [params["tools"]]
            if "tools" not in params:
                params["tools"] = []

            configs.append(AgentConfig(**params))

        return configs

    async def run(self, experiment: ExperimentConfig) -> ExperimentRecord:
        """Execute an experiment — run every generated config against each task."""
        record = ExperimentRecord(
            name=experiment.name,
            config=experiment,
            status="running",
        )

        configs = self.generate_configs(experiment)
        task_ids = experiment.tasks or ([experiment.task] if experiment.task else [None])

        total = len(configs) * len(task_ids)
        logger.info(
            "Experiment '%s': %d configs × %d tasks = %d runs",
            experiment.name,
            len(configs),
            len(task_ids),
            total,
        )

        runs: list[RunRecord] = []
        for i, config in enumerate(configs, 1):
            for task_id in task_ids:
                task_prompt = ""
                if task_id:
                    try:
                        task_cfg = self._store.load_task(task_id)
                        task_prompt = task_cfg.prompt
                    except FileNotFoundError:
                        logger.warning("Task '%s' not found, using empty prompt", task_id)

                logger.info(
                    "  [%d/%d] Running %s on task=%s",
                    i, total, config.name, task_id or "(none)",
                )
                run = await self._runner.run(
                    config, task_prompt=task_prompt, task_id=task_id
                )
                runs.append(run)
                record.run_ids.append(run.id)

        record.status = "completed"
        record.completed_at = datetime.now(timezone.utc)
        self._store.save_experiment(record)

        logger.info("Experiment '%s' completed — %d runs", experiment.name, len(runs))
        return record
