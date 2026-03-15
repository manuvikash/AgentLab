"""RAG memory backed by ChromaDB — an open-source embedded vector database.

``search()`` performs semantic similarity retrieval via dense vector embeddings,
so agents can find relevant memories even when the query uses different wording
than what was originally stored.

Dependencies (install with ``pip install agentlab[vector]``):
    chromadb>=0.5          — embedded vector store, no server required
    sentence-transformers  — richer embedding models (optional; ChromaDB's
                             built-in onnxruntime-based model is used by default)

Registration name: ``"rag"``

Quick usage::

    from agentlab.components.memory.rag import RAGMemory

    mem = RAGMemory()                     # ephemeral, in-process
    mem = RAGMemory(path="./agent_mem")   # persists across runs

    mem.store("user_goal", "Fix the authentication bug in login.py")
    results = mem.search("login authentication issue", top_k=3)

Custom embedder::

    from chromadb.utils import embedding_functions as ef
    fn = ef.SentenceTransformerEmbeddingFunction("all-mpnet-base-v2")
    mem = RAGMemory(embedding_fn=fn)
"""

from __future__ import annotations

import logging
from typing import Any

from agentlab.core.component import BaseMemory
from agentlab.core.registry import register

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "agentlab_memory"


def _import_chromadb() -> Any:
    try:
        import chromadb

        return chromadb
    except ImportError as exc:
        raise ImportError(
            "RAGMemory requires chromadb. Install it with:\n"
            "  pip install agentlab[vector]\n"
            "  # or: pip install chromadb"
        ) from exc


def _default_embedding_fn() -> Any:
    """Return ChromaDB's built-in onnxruntime-based embedding function.

    Uses ``all-MiniLM-L6-v2`` via chromadb's bundled ``onnxruntime`` backend.
    No GPU required; ~23 MB model downloaded on first use.
    """
    from chromadb.utils import embedding_functions as ef  # type: ignore[attr-defined]

    return ef.DefaultEmbeddingFunction()


@register("memory", "rag")
class RAGMemory(BaseMemory):
    """Semantic memory using ChromaDB as the embedded vector store.

    ``store()`` upserts documents (keyed by ``key``).
    ``search()`` returns the top-k semantically closest entries using cosine
    similarity on dense embeddings.
    ``retrieve()`` performs exact key lookup (no vector search).

    Parameters:
        path: filesystem path for persistent storage. If ``None`` (default)
              an ephemeral in-memory client is used.
        embedding_fn: ChromaDB embedding function. Defaults to the built-in
                      onnxruntime ``all-MiniLM-L6-v2`` model.
        collection_name: ChromaDB collection to use (default ``"agentlab_memory"``).
        distance_fn: ChromaDB distance metric — ``"cosine"`` (default),
                     ``"l2"``, or ``"ip"``.
    """

    def __init__(
        self,
        path: str | None = None,
        embedding_fn: Any = None,
        collection_name: str = _COLLECTION_NAME,
        distance_fn: str = "cosine",
        **_: Any,
    ) -> None:
        chromadb = _import_chromadb()
        if path:
            self._client = chromadb.PersistentClient(path=path)
        else:
            self._client = chromadb.EphemeralClient()

        self._embedding_fn = embedding_fn or _default_embedding_fn()
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": distance_fn},
        )

    # ------------------------------------------------------------------
    # BaseMemory interface
    # ------------------------------------------------------------------

    def store(self, key: str, value: Any) -> None:
        """Upsert a document. The string representation of ``value`` is embedded."""
        text = str(value)
        self._collection.upsert(
            ids=[key],
            documents=[text],
            metadatas=[{"key": key}],
        )

    def retrieve(self, key: str) -> Any | None:
        """Exact key lookup. Returns the stored string or ``None`` if not found."""
        result = self._collection.get(ids=[key])
        docs = result.get("documents") or []
        return docs[0] if docs else None

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, Any]]:
        """Semantic similarity search. Returns ``[(key, value), ...]`` sorted by relevance."""
        count = self._collection.count()
        if count == 0:
            return []
        k = min(top_k, count)
        result = self._collection.query(
            query_texts=[query],
            n_results=k,
            include=["documents", "metadatas"],
        )
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        return list(zip(ids, docs))

    def clear(self) -> None:
        """Delete all documents from the collection."""
        ids = self._collection.get()["ids"]
        if ids:
            self._collection.delete(ids=ids)

    # ------------------------------------------------------------------
    # Extras
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        """Number of documents currently stored."""
        return self._collection.count()

    def delete(self, key: str) -> None:
        """Remove a single entry by key."""
        self._collection.delete(ids=[key])

    def search_with_scores(self, query: str, top_k: int = 5) -> list[tuple[str, Any, float]]:
        """Like ``search()`` but also returns the distance score for each result.

        Returns ``[(key, value, distance), ...]``. Lower distance = more similar
        (for cosine and l2 metrics).
        """
        count = self._collection.count()
        if count == 0:
            return []
        k = min(top_k, count)
        result = self._collection.query(
            query_texts=[query],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [(i, d, dist) for i, d, dist in zip(ids, docs, distances)]
