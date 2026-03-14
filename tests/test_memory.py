"""Tests for the simple memory component."""

from __future__ import annotations

from agentlab.components.memory.simple import SimpleMemory


def test_store_and_retrieve():
    mem = SimpleMemory()
    mem.store("key1", "value1")
    assert mem.retrieve("key1") == "value1"


def test_retrieve_missing():
    mem = SimpleMemory()
    assert mem.retrieve("missing") is None


def test_search():
    mem = SimpleMemory()
    mem.store("user_name", "Alice")
    mem.store("user_age", "30")
    mem.store("project", "AgentLab")

    results = mem.search("user")
    assert len(results) == 2
    keys = {r[0] for r in results}
    assert keys == {"user_name", "user_age"}


def test_clear():
    mem = SimpleMemory()
    mem.store("k", "v")
    mem.clear()
    assert mem.retrieve("k") is None
