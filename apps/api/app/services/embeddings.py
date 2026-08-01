"""Embedding providers: Jina AI (production) and a deterministic mock.

Jina ``jina-embeddings-v3`` is used via its OpenAI-compatible endpoint so the
client shape stays swappable (the model registry could add providers later).
"""

from __future__ import annotations

import abc
import hashlib
import logging
import math

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1024
BATCH_SIZE = 32


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(abc.ABC):
    dim: int = EMBEDDING_DIM

    @abc.abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class JinaEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "jina-embeddings-v3",
        base_url: str = "https://api.jina.ai/v1",
        dim: int = EMBEDDING_DIM,
        timeout: httpx.Timeout = httpx.Timeout(connect=15.0, read=120.0, write=60.0, pool=15.0),
    ) -> None:
        self.model = model
        self.dim = dim
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            vectors.extend(await self._embed_batch(batch))
        return vectors

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dim,
            "task": "text-matching",
        }
        try:
            response = await self._client.post("/embeddings", json=payload)
        except httpx.HTTPError as exc:
            logger.warning("Jina embeddings request failed: %s", exc)
            raise EmbeddingError(f"Jina embeddings request failed: {exc}") from exc
        if response.status_code != 200:
            logger.warning(
                "Jina embeddings returned %s: %s", response.status_code, response.text[:300]
            )
            raise EmbeddingError(
                f"Jina embeddings failed with HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            data = response.json()
            return [item["embedding"] for item in data["data"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError("Malformed Jina embeddings response") from exc


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic pseudo-embeddings for tests and key-less development.

    Vectors are derived from a hash of the text so identical inputs produce
    identical vectors (queryable via cosine similarity) without any network.
    """

    dim = EMBEDDING_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big")
        vector: list[float] = []
        for i in range(EMBEDDING_DIM):
            # Mix the seed with a per-index salt; normalize magnitude ~1.
            value = math.sin(seed + i * 1103515245)
            vector.append(value)
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    if settings.jina_api_key:
        return JinaEmbeddingProvider(
            api_key=settings.jina_api_key,
            model=settings.jina_embedding_model,
            base_url=settings.jina_embedding_base_url,
        )
    logger.warning("AIDG_JINA_API_KEY not set — using mock embedding provider")
    return MockEmbeddingProvider()
