"""Embedding service that calls ZhipuAI and falls back to a deterministic hash embedder."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache
from typing import Sequence


LOGGER = logging.getLogger(__name__)
DEFAULT_DIMENSION = 1024
DEFAULT_BATCH_SIZE = 64
_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    lowered = text.lower()
    return _TOKEN_PATTERN.findall(lowered)


def _hash_token(token: str, dimension: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimension


def hash_embed(text: str, dimension: int = DEFAULT_DIMENSION) -> list[float]:
    """Compute a deterministic, dependency-free embedding for text."""
    if dimension <= 0:
        raise ValueError("dimension must be a positive integer")

    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * dimension

    counts: dict[int, float] = {}
    for token in tokens:
        bucket = _hash_token(token, dimension)
        counts[bucket] = counts.get(bucket, 0.0) + 1.0

    vector = [0.0] * dimension
    norm = 0.0
    for index, value in counts.items():
        vector[index] = value
        norm += value * value
    norm = math.sqrt(norm) or 1.0
    return [value / norm for value in vector]


def hash_embed_batch(texts: Sequence[str], dimension: int = DEFAULT_DIMENSION) -> list[list[float]]:
    return [hash_embed(text, dimension) for text in texts]


class EmbeddingService:
    """ZhipuAI embedding wrapper with a deterministic offline fallback."""

    def __init__(self, *, config=None) -> None:
        from config import get_config

        self.config = config if config is not None else get_config()
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None or not self.config.zhipuai_enabled:
            return
        try:
            from zhipuai import ZhipuAI

            self._client = ZhipuAI(
                api_key=self.config.zhipuai_api_key,
                base_url=self.config.zhipuai_base_url,
            )
        except Exception as exc:
            LOGGER.warning(
                "ZhipuAI client unavailable; using local hash embedder: %s",
                exc,
            )
            self._client = None

    @property
    def dimension(self) -> int:
        return self.config.vector_dimension or DEFAULT_DIMENSION

    def embed(self, text: str) -> list[float]:
        """Return an embedding for a single text, falling back to the hash model."""
        if not isinstance(text, str) or not text.strip():
            return [0.0] * self.dimension

        self._ensure_client()
        if self._client is None:
            return hash_embed(text, self.dimension)

        try:
            response = self._client.embeddings.create(
                model=self.config.zhipuai_model,
                input=[text],
                timeout=self.config.zhipuai_timeout_seconds,
            )
            data = getattr(response, "data", None) or []
            if not data or not getattr(data[0], "embedding", None):
                raise ValueError("empty embedding response")
            return list(data[0].embedding)
        except Exception as exc:
            LOGGER.warning(
                "ZhipuAI embedding call failed; using local hash embedder: %s",
                exc,
            )
            return hash_embed(text, self.dimension)

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embeddings for many texts, batching remote calls when possible."""
        if not isinstance(texts, list):
            raise TypeError("texts must be a list")
        if not texts:
            return []

        self._ensure_client()
        if self._client is None:
            return hash_embed_batch(texts, self.dimension)

        vectors: list[list[float] | None] = [None] * len(texts)
        pending: list[tuple[int, str]] = [
            (index, text) for index, text in enumerate(texts) if isinstance(text, str) and text.strip()
        ]

        try:
            for start in range(0, len(pending), DEFAULT_BATCH_SIZE):
                chunk = pending[start : start + DEFAULT_BATCH_SIZE]
                inputs = [text for _, text in chunk]
                response = self._client.embeddings.create(
                    model=self.config.zhipuai_model,
                    input=inputs,
                    timeout=self.config.zhipuai_timeout_seconds,
                )
                data = getattr(response, "data", None) or []
                for offset, item in enumerate(data):
                    embedding = getattr(item, "embedding", None)
                    if not embedding:
                        continue
                    original_index = chunk[offset][0]
                    vectors[original_index] = list(embedding)
        except Exception as exc:
            LOGGER.warning(
                "ZhipuAI batch embedding call failed; using local hash embedder: %s",
                exc,
            )
            return hash_embed_batch(texts, self.dimension)

        for index, text in enumerate(texts):
            if vectors[index] is None:
                vectors[index] = hash_embed(text, self.dimension)
        return [cast_list(vector) for vector in vectors]


def cast_list(value: list[float] | None) -> list[float]:
    return value if value is not None else []


@lru_cache(maxsize=1)
def default_embedding_service() -> EmbeddingService:
    return EmbeddingService()
