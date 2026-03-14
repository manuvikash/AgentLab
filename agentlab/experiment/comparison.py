"""Run and experiment comparison utilities."""

from __future__ import annotations

from agentlab.models.schemas import Metrics, RunRecord
from agentlab.storage.store import Store


def compare_runs(run_a: RunRecord, run_b: RunRecord) -> dict[str, dict[str, object]]:
    """Compare two runs side-by-side and return metric diffs."""
    fields = ["success", "steps", "tokens_used", "input_tokens", "output_tokens",
              "runtime_seconds", "patch_size"]
    result: dict[str, dict[str, object]] = {}

    for field in fields:
        val_a = getattr(run_a.metrics, field, None)
        val_b = getattr(run_b.metrics, field, None)
        entry: dict[str, object] = {"run_a": val_a, "run_b": val_b}

        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            entry["diff"] = val_b - val_a
            if val_a != 0:
                entry["pct_change"] = round((val_b - val_a) / val_a * 100, 1)
        result[field] = entry

    return result


def experiment_summary(experiment_id: str, store: Store) -> list[dict[str, object]]:
    """Build a summary table of all runs in an experiment."""
    experiment = store.load_experiment(experiment_id)
    rows: list[dict[str, object]] = []

    for run_id in experiment.run_ids:
        try:
            run = store.load_run(run_id)
        except FileNotFoundError:
            continue

        rows.append({
            "run_id": run.id,
            "agent": run.agent_name,
            "task": run.task_id or "-",
            "status": run.status,
            "success": run.metrics.success,
            "steps": run.metrics.steps,
            "tokens": run.metrics.tokens_used,
            "runtime_s": run.metrics.runtime_seconds,
        })

    return rows
