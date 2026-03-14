"""Tests for the experiment engine."""

from __future__ import annotations

from agentlab.experiment.engine import ExperimentEngine
from agentlab.models.schemas import ExperimentConfig


def test_generate_configs_cartesian():
    exp = ExperimentConfig(
        name="test",
        matrix={"llm": ["openai", "anthropic"], "context": ["sliding", "simple"]},
        base={"loop": "react", "tools": ["shell"], "sandbox": "local"},
    )
    engine = ExperimentEngine()
    configs = engine.generate_configs(exp)

    assert len(configs) == 4  # 2 × 2

    llms = {c.llm for c in configs}
    contexts = {c.context for c in configs}
    assert llms == {"openai", "anthropic"}
    assert contexts == {"sliding", "simple"}


def test_generate_configs_single_axis():
    exp = ExperimentConfig(
        name="single",
        matrix={"llm": ["openai"]},
        base={"loop": "react", "context": "sliding", "tools": [], "sandbox": "local"},
    )
    engine = ExperimentEngine()
    configs = engine.generate_configs(exp)
    assert len(configs) == 1
    assert configs[0].llm == "openai"


def test_generate_configs_preserves_base():
    exp = ExperimentConfig(
        name="base_test",
        matrix={"llm": ["openai"]},
        base={"loop": "react", "context": "simple", "tools": ["filesystem"], "sandbox": "docker"},
    )
    engine = ExperimentEngine()
    configs = engine.generate_configs(exp)
    assert configs[0].loop == "react"
    assert configs[0].sandbox == "docker"
    assert configs[0].tools == ["filesystem"]
