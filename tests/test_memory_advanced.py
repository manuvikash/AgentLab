"""Tests for SlidingWindowMemory, CompactionMemory, and RAGMemory.

RAGMemory tests are skipped automatically if chromadb is not installed.
"""

from __future__ import annotations

import math
import pytest

from agentlab.components.memory.compaction import (
    CompactionMemory,
    async_compactor_from_llm,
    extractive_compactor,
    truncating_compactor,
)
from agentlab.components.memory.sliding_window import SlidingWindowMemory

# Check chromadb availability once at module load
try:
    import chromadb  # noqa: F401

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

chromadb_required = pytest.mark.skipif(
    not CHROMADB_AVAILABLE, reason="chromadb not installed (pip install agentlab[vector])"
)


# ===========================================================================
# SlidingWindowMemory
# ===========================================================================


class TestSlidingWindowMemory:
    def test_basic_store_retrieve(self):
        mem = SlidingWindowMemory(window=10)
        mem.store("a", 1)
        assert mem.retrieve("a") == 1

    def test_retrieve_missing_returns_none(self):
        mem = SlidingWindowMemory(window=10)
        assert mem.retrieve("missing") is None

    def test_evicts_oldest_when_full(self):
        mem = SlidingWindowMemory(window=3)
        mem.store("k1", "v1")
        mem.store("k2", "v2")
        mem.store("k3", "v3")
        # Adding k4 should evict k1
        mem.store("k4", "v4")
        assert mem.retrieve("k1") is None
        assert mem.retrieve("k2") == "v2"
        assert mem.retrieve("k4") == "v4"
        assert mem.size == 3

    def test_window_never_exceeded(self):
        mem = SlidingWindowMemory(window=5)
        for i in range(20):
            mem.store(f"k{i}", f"v{i}")
        assert mem.size == 5

    def test_update_moves_to_recent_end(self):
        """Updating an existing key removes-then-reinserts, so it becomes the most recent."""
        mem = SlidingWindowMemory(window=3)
        mem.store("a", 1)
        mem.store("b", 2)
        mem.store("c", 3)
        # Update 'a' — it should become the most recent, pushing 'b' to oldest
        mem.store("a", 99)
        # Adding 'd' should evict 'b' (oldest after 'a' was re-inserted)
        mem.store("d", 4)
        assert mem.retrieve("a") == 99  # updated, still present
        assert mem.retrieve("b") is None  # evicted
        assert mem.retrieve("c") == 3
        assert mem.retrieve("d") == 4

    def test_search_returns_matches(self):
        mem = SlidingWindowMemory(window=10)
        mem.store("user_name", "Alice")
        mem.store("user_email", "alice@example.com")
        mem.store("project", "AgentLab")

        results = mem.search("user")
        keys = {r[0] for r in results}
        assert keys == {"user_name", "user_email"}

    def test_search_newest_first_order(self):
        mem = SlidingWindowMemory(window=10)
        mem.store("old_key", "alpha query match")
        mem.store("new_key", "query match newer")

        results = mem.search("query")
        assert results[0][0] == "new_key"  # newest first
        assert results[1][0] == "old_key"

    def test_search_top_k_limit(self):
        mem = SlidingWindowMemory(window=10)
        for i in range(8):
            mem.store(f"item_{i}", f"searchable content {i}")
        results = mem.search("searchable", top_k=3)
        assert len(results) == 3

    def test_search_empty_store(self):
        mem = SlidingWindowMemory(window=10)
        assert mem.search("anything") == []

    def test_clear(self):
        mem = SlidingWindowMemory(window=10)
        mem.store("x", 1)
        mem.clear()
        assert mem.retrieve("x") is None
        assert mem.size == 0

    def test_keys_order_oldest_to_newest(self):
        mem = SlidingWindowMemory(window=5)
        for k in ["a", "b", "c"]:
            mem.store(k, k)
        assert mem.keys() == ["a", "b", "c"]

    def test_invalid_window_raises(self):
        with pytest.raises(ValueError, match="window must be"):
            SlidingWindowMemory(window=0)

    def test_window_of_one(self):
        mem = SlidingWindowMemory(window=1)
        mem.store("first", 1)
        mem.store("second", 2)
        assert mem.retrieve("first") is None
        assert mem.retrieve("second") == 2
        assert mem.size == 1


# ===========================================================================
# CompactionMemory
# ===========================================================================


class TestCompactionMemory:
    def test_basic_store_retrieve(self):
        mem = CompactionMemory(threshold=10)
        mem.store("a", "hello")
        assert mem.retrieve("a") == "hello"

    def test_retrieve_missing_returns_none(self):
        mem = CompactionMemory(threshold=10)
        assert mem.retrieve("nope") is None

    def test_no_compaction_below_threshold(self):
        mem = CompactionMemory(threshold=5)
        for i in range(5):
            mem.store(f"k{i}", f"v{i}")
        assert mem.compaction_count == 0
        assert mem.size == 5

    def test_compaction_triggered_at_threshold(self):
        mem = CompactionMemory(threshold=5, compact_ratio=0.5)
        for i in range(6):  # 6 > threshold(5) → triggers
            mem.store(f"k{i}", f"v{i}")
        assert mem.compaction_count == 1
        # After compacting 50% of 6 entries (3), we have 1 summary + 3 recent = 4
        assert mem.size < 6

    def test_compacted_summary_key_present(self):
        mem = CompactionMemory(threshold=3, compact_ratio=0.5)
        mem.store("x", "val_x")
        mem.store("y", "val_y")
        mem.store("z", "val_z")
        mem.store("w", "val_w")  # triggers compaction
        keys = list(mem._store.keys())
        assert any(k.startswith("__compacted_") for k in keys)

    def test_compaction_count_increments(self):
        mem = CompactionMemory(threshold=3, compact_ratio=0.5)
        for i in range(10):
            mem.store(f"k{i}", f"v{i}")
        assert mem.compaction_count >= 2

    def test_custom_compactor_called(self):
        called_with: list[dict] = []

        def my_compactor(entries: dict) -> str:
            called_with.append(dict(entries))
            return "custom summary"

        mem = CompactionMemory(threshold=3, compact_ratio=0.5, compactor=my_compactor)
        for i in range(4):
            mem.store(f"k{i}", f"v{i}")
        assert len(called_with) >= 1
        # custom summary is stored
        stored_values = list(mem._store.values())
        assert "custom summary" in stored_values

    def test_manual_compact(self):
        # compact_ratio=0.5 with 4 entries → ceil(4*0.5)=2 compacted, 2 remain + 1 summary
        mem = CompactionMemory(threshold=100, compact_ratio=0.5)  # won't auto-compact
        mem.store("a", "alpha")
        mem.store("b", "beta")
        mem.store("c", "gamma")
        mem.store("d", "delta")
        summary = mem.compact()
        assert isinstance(summary, str)
        assert mem.compaction_count == 1
        # The 2 oldest entries (a, b) should be gone; c, d remain
        assert mem.retrieve("a") is None
        assert mem.retrieve("b") is None
        assert mem.retrieve("c") == "gamma"
        assert mem.retrieve("d") == "delta"
        # A compacted summary key is present
        compacted_keys = [k for k in mem._store if k.startswith("__compacted_")]
        assert len(compacted_keys) == 1

    def test_search_includes_compacted_summaries(self):
        mem = CompactionMemory(threshold=3, compact_ratio=0.5)
        mem.store("old_important", "data about authentication")
        mem.store("old_2", "something else")
        mem.store("old_3", "another thing")
        mem.store("new_entry", "recent data")  # triggers compaction
        # The compacted summary should contain "authentication"
        results = mem.search("authentication")
        assert len(results) >= 1

    def test_clear_resets_compaction_count(self):
        mem = CompactionMemory(threshold=3)
        for i in range(5):
            mem.store(f"k{i}", f"v{i}")
        mem.clear()
        assert mem.compaction_count == 0
        assert mem.size == 0

    def test_update_key_moves_to_recent(self):
        """Updating a key makes it 'recent' — it's less likely to be compacted."""
        mem = CompactionMemory(threshold=3, compact_ratio=0.5)
        mem.store("a", "old")
        mem.store("b", "b")
        mem.store("a", "updated")  # move 'a' to recent end
        mem.store("c", "c")       # triggers compaction (threshold=3 → 4 entries after)
        # 'a' was re-inserted as newest, so 'b' (oldest) gets compacted
        assert mem.retrieve("a") == "updated"

    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError, match="threshold"):
            CompactionMemory(threshold=1)

    def test_invalid_ratio_raises(self):
        with pytest.raises(ValueError, match="compact_ratio"):
            CompactionMemory(compact_ratio=1.0)

    def test_extractive_compactor_format(self):
        entries = {"k1": "v1", "k2": "v2"}
        result = extractive_compactor(entries)
        assert "k1" in result
        assert "v1" in result
        assert "k2" in result

    def test_truncating_compactor(self):
        compactor = truncating_compactor(max_chars_per_entry=5)
        entries = {"key": "a" * 100}
        result = compactor(entries)
        assert "aaaaa" in result
        # Value should be truncated
        assert "a" * 100 not in result

    def test_multiple_compactions_dont_lose_summaries(self):
        """Each compaction run produces a unique __compacted_N__ key."""
        mem = CompactionMemory(threshold=4, compact_ratio=0.5)
        for i in range(12):
            mem.store(f"k{i}", f"v{i}")
        compacted_keys = [k for k in mem._store if k.startswith("__compacted_")]
        # Each round produces a distinct key
        assert len(compacted_keys) == len(set(compacted_keys))


# ===========================================================================
# extractive / truncating compactors (standalone)
# ===========================================================================


def test_extractive_compactor_empty_entries():
    result = extractive_compactor({})
    assert isinstance(result, str)


def test_truncating_compactor_limits_length():
    compactor = truncating_compactor(max_chars_per_entry=10)
    big_value = "x" * 1000
    result = compactor({"key": big_value})
    assert "x" * 1000 not in result
    assert "x" * 10 in result


# ===========================================================================
# RAGMemory (skipped if chromadb not installed)
# ===========================================================================


@chromadb_required
class TestRAGMemory:
    def _mem(self) -> "RAGMemory":
        from agentlab.components.memory.rag import RAGMemory

        return RAGMemory()  # ephemeral client

    def test_store_and_retrieve_exact(self):
        mem = self._mem()
        mem.store("fact_1", "Paris is the capital of France.")
        result = mem.retrieve("fact_1")
        assert result == "Paris is the capital of France."

    def test_retrieve_missing_returns_none(self):
        mem = self._mem()
        assert mem.retrieve("does_not_exist") is None

    def test_upsert_updates_existing(self):
        mem = self._mem()
        mem.store("key", "old value")
        mem.store("key", "new value")
        assert mem.retrieve("key") == "new value"
        assert mem.count == 1

    def test_search_returns_relevant(self):
        mem = self._mem()
        mem.store("bug_1", "NullPointerException in login module")
        mem.store("bug_2", "CSS layout broken on mobile")
        mem.store("bug_3", "Database timeout on user lookup")

        results = mem.search("authentication login error", top_k=2)
        assert len(results) >= 1
        # The login-related entry should be among the top results
        top_keys = [r[0] for r in results]
        assert "bug_1" in top_keys

    def test_search_empty_store(self):
        mem = self._mem()
        results = mem.search("anything")
        assert results == []

    def test_search_top_k_limit(self):
        mem = self._mem()
        for i in range(10):
            mem.store(f"doc_{i}", f"Content about topic {i} with searchable text")
        results = mem.search("searchable text", top_k=3)
        assert len(results) == 3

    def test_search_returns_key_value_pairs(self):
        mem = self._mem()
        mem.store("my_key", "value text")
        results = mem.search("value")
        assert len(results) >= 1
        key, val = results[0]
        assert key == "my_key"
        assert "value" in val

    def test_count_increments(self):
        mem = self._mem()
        assert mem.count == 0
        mem.store("a", "alpha")
        mem.store("b", "beta")
        assert mem.count == 2

    def test_delete_single_entry(self):
        mem = self._mem()
        mem.store("keep", "keep this")
        mem.store("remove", "remove this")
        mem.delete("remove")
        assert mem.retrieve("remove") is None
        assert mem.retrieve("keep") == "keep this"
        assert mem.count == 1

    def test_clear_removes_all(self):
        mem = self._mem()
        for i in range(5):
            mem.store(f"k{i}", f"v{i}")
        mem.clear()
        assert mem.count == 0

    def test_search_with_scores_returns_distances(self):
        mem = self._mem()
        mem.store("fact", "The sky is blue.")
        results = mem.search_with_scores("sky colour", top_k=1)
        assert len(results) == 1
        key, val, distance = results[0]
        assert key == "fact"
        assert isinstance(distance, float)

    def test_semantic_search_finds_paraphrase(self):
        """Semantic search should find related content even without exact word match."""
        mem = self._mem()
        mem.store("task_1", "Implement user authentication with JWT tokens")
        mem.store("task_2", "Fix broken image uploads")
        mem.store("task_3", "Improve database query performance")

        # Query uses different words but same meaning as task_1
        results = mem.search("add login security using bearer tokens", top_k=1)
        assert len(results) >= 1
        assert results[0][0] == "task_1"

    def test_registration(self):
        import agentlab.components  # noqa: F401

        from agentlab.core.registry import get_registry

        cls = get_registry().get("memory", "rag")
        from agentlab.components.memory.rag import RAGMemory

        assert cls is RAGMemory


# ===========================================================================
# Registration sanity check (no chromadb needed)
# ===========================================================================


def test_all_non_vector_memories_registered():
    import agentlab.components  # noqa: F401

    from agentlab.core.registry import get_registry

    reg = get_registry()
    for name in ("simple", "sliding_window", "compaction"):
        cls = reg.get("memory", name)
        assert cls is not None, f"Memory '{name}' not registered"
