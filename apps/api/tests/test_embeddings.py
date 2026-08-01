"""Embedding provider tests (mock determinism + Jina request shape)."""

from __future__ import annotations

import httpx
import pytest

from app.services.embeddings import (
    EMBEDDING_DIM,
    EmbeddingError,
    JinaEmbeddingProvider,
    MockEmbeddingProvider,
)


async def test_mock_vectors_are_deterministic_and_normalized() -> None:
    provider = MockEmbeddingProvider()
    first = await provider.embed(["仁愛堂服務"])
    second = await provider.embed(["仁愛堂服務"])
    other = await provider.embed(["完全不同的內容"])

    assert first == second
    assert first[0] != other[0]
    assert len(first[0]) == EMBEDDING_DIM

    norm = sum(v * v for v in first[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-3


async def test_mock_identical_texts_are_similar() -> None:
    provider = MockEmbeddingProvider()
    a = (await provider.embed(["長者服務計劃文件"]))[0]
    b = (await provider.embed(["長者服務計劃文件"]))[0]
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    assert dot > 0.99


async def test_jina_request_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert request.url.path == "/v1/embeddings"
        assert b'"model":"jina-embeddings-v3"' in body
        assert b'"dimensions":1024' in body
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1] * EMBEDDING_DIM} for _ in range(2)]},
        )

    transport = httpx.MockTransport(handler)
    provider = JinaEmbeddingProvider(api_key="sk-jina-test")
    provider._client = httpx.AsyncClient(base_url="https://api.jina.ai/v1", transport=transport)
    try:
        vectors = await provider.embed(["a", "b"])
        assert len(vectors) == 2
        assert len(vectors[0]) == EMBEDDING_DIM
    finally:
        await provider.aclose()


async def test_jina_http_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    transport = httpx.MockTransport(handler)
    provider = JinaEmbeddingProvider(api_key="bad")
    provider._client = httpx.AsyncClient(base_url="https://api.jina.ai/v1", transport=transport)
    try:
        with pytest.raises(EmbeddingError, match="HTTP 401"):
            await provider.embed(["x"])
    finally:
        await provider.aclose()


async def test_empty_input() -> None:
    provider = MockEmbeddingProvider()
    assert await provider.embed([]) == []
