"""Tests for the component registry."""

from __future__ import annotations

import pytest

from agentlab.core.component import BaseLLM, BaseLoop, BaseTool
from agentlab.core.registry import ComponentRegistry, register
from agentlab.models.schemas import LLMResponse, Message, ToolSpec


@pytest.fixture(autouse=True)
def clean_registry():
    ComponentRegistry.reset()
    yield
    ComponentRegistry.reset()


class DummyLLM(BaseLLM):
    async def generate(self, messages, tools=None, **kw):
        return LLMResponse(content="ok")

    @property
    def model_name(self):
        return "dummy"


def test_register_and_get():
    reg = ComponentRegistry()
    reg.register("llm", "dummy", DummyLLM)
    assert reg.get("llm", "dummy") is DummyLLM


def test_register_decorator():
    @register("llm", "decorated")
    class DecoratedLLM(BaseLLM):
        async def generate(self, messages, tools=None, **kw):
            return LLMResponse(content="hi")

        @property
        def model_name(self):
            return "decorated"

    reg = ComponentRegistry()
    assert reg.get("llm", "decorated") is DecoratedLLM


def test_get_missing_raises():
    reg = ComponentRegistry()
    with pytest.raises(KeyError, match="No 'llm' component named 'missing'"):
        reg.get("llm", "missing")


def test_register_wrong_type_raises():
    reg = ComponentRegistry()
    with pytest.raises(TypeError, match="must be a subclass of BaseLLM"):
        reg.register("llm", "bad", str)


def test_register_unknown_component_type():
    reg = ComponentRegistry()
    with pytest.raises(ValueError, match="Unknown component type"):
        reg.register("unknown_type", "x", DummyLLM)


def test_create():
    reg = ComponentRegistry()
    reg.register("llm", "dummy", DummyLLM)
    instance = reg.create("llm", "dummy")
    assert isinstance(instance, DummyLLM)


def test_list_components():
    reg = ComponentRegistry()
    reg.register("llm", "dummy", DummyLLM)
    items = reg.list_components()
    assert len(items) == 1
    assert items[0]["type"] == "llm"
    assert items[0]["name"] == "dummy"


def test_list_components_with_filter():
    reg = ComponentRegistry()
    reg.register("llm", "dummy", DummyLLM)
    assert len(reg.list_components("llm")) == 1
    assert len(reg.list_components("tool")) == 0


def test_singleton():
    a = ComponentRegistry()
    b = ComponentRegistry()
    assert a is b


def test_reset():
    reg = ComponentRegistry()
    reg.register("llm", "dummy", DummyLLM)
    ComponentRegistry.reset()
    new_reg = ComponentRegistry()
    assert len(new_reg.list_components()) == 0
