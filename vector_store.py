"""Vector store abstraction for Moorchid memory, with Chroma and an in-memory backend."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


LOGGER = logging.getLogger(__name__)


@dataclass
class MemoryHit:
    """A single semantic memory retrieved from the vector store."""

    entry_id: int
    user_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryVectorStore:
    """Cosmetic Python list used as a fallback when Chroma is unavailable."""

    def __init__(self, persist_dir: Path) -> None:
        self.persist_dir = Path(persist_dir)
        self._records: dict[int, dict[str, Any]] = {}

    def upsert(self, entries: Sequence[dict[str, Any]], embeddings: Sequence[Sequence[float]]) -> None:
        if len(entries) != len(embeddings):
            raise ValueError("entries and embeddings must have the same length")
        for entry, embedding in zip(entries, embeddings):
            entry_id = int(entry["entry_id"])
            self._records[entry_id] = {
                "user_id": entry.get("user_id", ""),
                "content": entry.get("content", ""),
                "metadata": dict(entry.get("metadata", {})),
                "embedding": list(embedding),
            }

    def delete(self, entry_ids: Sequence[int]) -> None:
        for entry_id in entry_ids:
            self._records.pop(int(entry_id), None)

    def query(
        self,
        user_id: str,
        embedding: Sequence[float],
        top_k: int = 5,
    ) -> list[MemoryHit]:
        if not self._records:
            return []

        target = list(embedding)
        target_norm = _l2_norm(target)
        scored: list[MemoryHit] = []
        for entry_id, record in self._records.items():
            if record["user_id"] != user_id:
                continue
            vector = record["embedding"]
            score = _cosine_similarity(target, vector, target_norm)
            scored.append(
                MemoryHit(
                    entry_id=entry_id,
                    user_id=record["user_id"],
                    content=record["content"],
                    score=score,
                    metadata=record["metadata"],
                )
            )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[: max(1, top_k)]


def _l2_norm(vector: Sequence[float]) -> float:
    return sum(component * component for component in vector) ** 0.5


def _cosine_similarity(
    left: Sequence[float], right: Sequence[float], left_norm: float | None = None
) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    left_norm_value = left_norm if left_norm is not None else _l2_norm(left)
    right_norm = _l2_norm(right)
    if left_norm_value == 0.0 or right_norm == 0.0:
        return 0.0

    dot = sum(a * b for a, b in zip(left, right))
    return float(dot / (left_norm_value * right_norm))


class ChromaVectorStore:
    """Persistent vector store backed by ChromaDB."""

    def __init__(self, persist_dir: Path, collection_name: str) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._initialise()

    def _initialise(self) -> None:
        try:
            import chromadb
        except Exception as exc:
            LOGGER.warning("chromadb unavailable; falling back to in-memory store: %s", exc)
            return

        try:
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            LOGGER.warning("Failed to initialise Chroma; falling back to in-memory store: %s", exc)
            self._client = None
            self._collection = None

    @property
    def is_available(self) -> bool:
        return self._collection is not None

    def upsert(self, entries: Sequence[dict[str, Any]], embeddings: Sequence[Sequence[float]]) -> None:
        if not self.is_available:
            raise RuntimeError("Chroma collection is not initialised")
        if len(entries) != len(embeddings):
            raise ValueError("entries and embeddings must have the same length")

        ids = [str(entry["entry_id"]) for entry in entries]
        documents = [entry.get("content", "") for entry in entries]
        metadatas = [
            {
                "user_id": entry.get("user_id", ""),
                **{key: value for key, value in entry.get("metadata", {}).items() if isinstance(value, (str, int, float, bool))},
            }
            for entry in entries
        ]
        self._collection.upsert(
            ids=ids,
            embeddings=[list(embedding) for embedding in embeddings],
            documents=documents,
            metadatas=metadatas,
        )

    def delete(self, entry_ids: Sequence[int]) -> None:
        if not self.is_available or not entry_ids:
            return
        self._collection.delete(ids=[str(entry_id) for entry_id in entry_ids])

    def query(
        self,
        user_id: str,
        embedding: Sequence[float],
        top_k: int = 5,
    ) -> list[MemoryHit]:
        if not self.is_available:
            return []

        safe_top_k = max(1, top_k)
        response = self._collection.query(
            query_embeddings=[list(embedding)],
            n_results=safe_top_k,
            where={"user_id": user_id},
        )

        ids = (response.get("ids") or [[]])[0]
        documents = (response.get("documents") or [[]])[0]
        distances = (response.get("distances") or [[]])[0]
        metadatas = (response.get("metadatas") or [[]])[0]

        hits: list[MemoryHit] = []
        for index, raw_id in enumerate(ids):
            document = documents[index] if index < len(documents) else ""
            distance = float(distances[index]) if index < len(distances) else 0.0
            metadata = metadatas[index] if index < len(metadatas) else {}
            hits.append(
                MemoryHit(
                    entry_id=int(raw_id),
                    user_id=str(metadata.get("user_id", user_id)),
                    content=str(document),
                    score=1.0 - distance,
                    metadata=dict(metadata or {}),
                )
            )
        return hits


class VectorStore:
    """User-facing facade that picks the configured backend and hides failures."""

    def __init__(self, config=None) -> None:
        from config import get_config

        self.config = config if config is not None else get_config()
        backend = self._instantiate_backend()
        self.backend = backend
        self.backend_name = backend.__class__.__name__

    def _instantiate_backend(self):
        if self.config.vector_store_type == "chroma":
            chroma = ChromaVectorStore(
                persist_dir=self.config.chroma_persist_dir,
                collection_name=self.config.vector_collection_name,
            )
            if chroma.is_available:
                return chroma
            LOGGER.warning("Chroma unavailable; using in-memory vector store instead")
        return InMemoryVectorStore(persist_dir=self.config.chroma_persist_dir)

    def upsert(self, entries: Sequence[dict[str, Any]], embeddings: Sequence[Sequence[float]]) -> None:
        try:
            self.backend.upsert(entries, embeddings)
        except Exception as exc:
            LOGGER.warning("Vector store upsert failed; the entry was not persisted: %s", exc)

    def delete(self, entry_ids: Sequence[int]) -> None:
        try:
            self.backend.delete(entry_ids)
        except Exception as exc:
            LOGGER.warning("Vector store delete failed: %s", exc)

    def query(self, user_id: str, embedding: Sequence[float], top_k: int | None = None) -> list[MemoryHit]:
        try:
            return self.backend.query(
                user_id=user_id,
                embedding=embedding,
                top_k=top_k or self.config.vector_top_k,
            )
        except Exception as exc:
            LOGGER.warning("Vector store query failed: %s", exc)
            return []


default_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return a lazily-created :class:`VectorStore` instance."""
    global default_vector_store
    if default_vector_store is None:
        default_vector_store = VectorStore()
    return default_vector_store


def reset_vector_store() -> None:
    """Drop the cached vector store so the next call re-reads configuration."""
    global default_vector_store
    default_vector_store = None


def format_memory_hits(hits: Sequence[MemoryHit]) -> str:
    """Render retrieved memory hits as a short natural-language snippet."""
    if not hits:
        return "（暂时没有相关历史随记，请只陪伴当下。）"

    lines: list[str] = []
    for hit in hits:
        snippet = hit.content.strip()
        if len(snippet) > 240:
            snippet = snippet[:240] + "…"
        metadata = hit.metadata or {}
        emotion = metadata.get("emotion") or "未标注"
        lines.append(f"- [{emotion}|相关度{hit.score:.2f}] {snippet}")
    return "\n".join(lines)
