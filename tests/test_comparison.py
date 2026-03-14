"""Tests for run comparison."""

from __future__ import annotations

from agentlab.experiment.comparison import compare_runs
from agentlab.models.schemas import Metrics, RunRecord


def test_compare_runs_basic():
    run_a = RunRecord(
        agent_name="a",
        metrics=Metrics(steps=5, tokens_used=1000, runtime_seconds=2.0),
    )
    run_b = RunRecord(
        agent_name="b",
        metrics=Metrics(steps=3, tokens_used=800, runtime_seconds=1.5),
    )
    diff = compare_runs(run_a, run_b)

    assert diff["steps"]["run_a"] == 5
    assert diff["steps"]["run_b"] == 3
    assert diff["steps"]["diff"] == -2

    assert diff["tokens_used"]["run_a"] == 1000
    assert diff["tokens_used"]["run_b"] == 800
    assert diff["tokens_used"]["diff"] == -200


def test_compare_runs_pct_change():
    run_a = RunRecord(
        agent_name="a",
        metrics=Metrics(steps=10, tokens_used=1000, runtime_seconds=2.0),
    )
    run_b = RunRecord(
        agent_name="b",
        metrics=Metrics(steps=5, tokens_used=500, runtime_seconds=1.0),
    )
    diff = compare_runs(run_a, run_b)
    assert diff["steps"]["pct_change"] == -50.0
    assert diff["tokens_used"]["pct_change"] == -50.0
