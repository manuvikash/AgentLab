"""Tests for metrics computation."""

from __future__ import annotations

from agentlab.evaluation.metrics import MetricsCollector, _count_changed_lines
from agentlab.models.schemas import Metrics, RunRecord


def test_count_changed_lines():
    diff = """--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def foo():
-    return 1
+    return 2
"""
    assert _count_changed_lines(diff) == 2  # one - and one +


def test_count_changed_lines_empty():
    assert _count_changed_lines("") == 0


def test_metrics_collector():
    run = RunRecord(
        agent_name="test",
        metrics=Metrics(steps=5, tokens_used=1000, runtime_seconds=3.0),
    )
    collector = MetricsCollector()
    result = collector.compute(run, validator_passed=True, patch_diff="+line\n-old")
    assert result.success is True
    assert result.patch_size == 2
    assert result.steps == 5


def test_metrics_collector_no_validation():
    run = RunRecord(agent_name="test")
    collector = MetricsCollector()
    result = collector.compute(run)
    assert result.success is None
    assert result.patch_size is None
