"""Tests for the file-based storage layer."""

from __future__ import annotations

import pytest

from agentlab.models.schemas import (
    AgentConfig,
    ExperimentRecord,
    Metrics,
    RunRecord,
    TraceEntry,
)
from agentlab.storage.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(root=tmp_path)


def test_save_and_load_agent(store):
    config = AgentConfig(name="test_agent", llm="openai", tools=["shell"])
    store.save_agent(config)

    loaded = store.load_agent("test_agent")
    assert loaded.name == "test_agent"
    assert loaded.llm == "openai"
    assert loaded.tools == ["shell"]


def test_list_agents(store):
    store.save_agent(AgentConfig(name="a1", llm="openai"))
    store.save_agent(AgentConfig(name="a2", llm="anthropic"))
    agents = store.list_agents()
    assert len(agents) == 2
    names = {a.name for a in agents}
    assert names == {"a1", "a2"}


def test_load_missing_agent_raises(store):
    with pytest.raises(FileNotFoundError):
        store.load_agent("nonexistent")


def test_save_and_load_run(store):
    run = RunRecord(
        agent_name="test",
        status="completed",
        metrics=Metrics(steps=3, tokens_used=500),
        trace=[TraceEntry(step=1, thought="hello")],
    )
    store.save_run(run)

    loaded = store.load_run(run.id)
    assert loaded.agent_name == "test"
    assert loaded.status == "completed"
    assert loaded.metrics.steps == 3
    assert len(loaded.trace) == 1


def test_list_runs(store):
    r1 = RunRecord(agent_name="a1")
    r2 = RunRecord(agent_name="a2")
    store.save_run(r1)
    store.save_run(r2)
    runs = store.list_runs()
    assert len(runs) == 2


def test_load_missing_run_raises(store):
    with pytest.raises(FileNotFoundError):
        store.load_run("nonexistent")


def test_save_and_load_experiment(store):
    exp = ExperimentRecord(name="test_exp", run_ids=["r1", "r2"])
    store.save_experiment(exp)
    loaded = store.load_experiment(exp.id)
    assert loaded.name == "test_exp"
    assert loaded.run_ids == ["r1", "r2"]


def test_list_experiments(store):
    store.save_experiment(ExperimentRecord(name="e1"))
    store.save_experiment(ExperimentRecord(name="e2"))
    exps = store.list_experiments()
    assert len(exps) == 2


def test_run_directory_contains_artifacts(store):
    config = AgentConfig(name="art_test", llm="openai")
    run = RunRecord(
        agent_name="art_test",
        agent_config=config,
        status="completed",
        metrics=Metrics(steps=1),
        trace=[TraceEntry(step=1, thought="done")],
    )
    run_dir = store.save_run(run)
    assert (run_dir / "run.json").exists()
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "trace.json").exists()
    assert (run_dir / "config.yaml").exists()
