"""Memory components.

Available implementations:
- ``"simple"``          — dict-backed with substring search (SimpleMemory)
- ``"sliding_window"``  — bounded window, evicts oldest on overflow (SlidingWindowMemory)
- ``"compaction"``      — auto-summarises old entries when over threshold (CompactionMemory)
- ``"rag"``             — ChromaDB-backed semantic retrieval (RAGMemory); requires
                          ``pip install agentlab[vector]``
"""

from agentlab.components.memory.compaction import CompactionMemory
from agentlab.components.memory.simple import SimpleMemory
from agentlab.components.memory.sliding_window import SlidingWindowMemory

__all__ = ["CompactionMemory", "RAGMemory", "SimpleMemory", "SlidingWindowMemory"]


def __getattr__(name: str):  # noqa: N807
    if name == "RAGMemory":
        from agentlab.components.memory.rag import RAGMemory

        return RAGMemory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

