"""Metric computation for agent evaluation."""

from __future__ import annotations

from agentlab.models.schemas import Metrics, RunRecord


class MetricsCollector:
    """Computes evaluation metrics from a run record and validation result."""

    def compute(
        self,
        run: RunRecord,
        validator_passed: bool | None = None,
        patch_diff: str | None = None,
    ) -> Metrics:
        metrics = run.metrics.model_copy()
        metrics.success = validator_passed
        if patch_diff is not None:
            metrics.patch_size = _count_changed_lines(patch_diff)
        return metrics


def _count_changed_lines(diff: str) -> int:
    count = 0
    for line in diff.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            count += 1
    return count
