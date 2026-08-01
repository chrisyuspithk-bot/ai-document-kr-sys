"""Health endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.api.v1.endpoints import health


async def test_healthz(client) -> None:
    resp = await client.get("/api/v1/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz_ok(client) -> None:
    with patch.object(health, "Redis") as mock_redis:
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_redis.from_url.return_value = mock_client
        resp = await client.get("/api/v1/readyz")
    assert resp.status_code == 200
    assert resp.json()["checks"] == {"database": "ok", "redis": "ok"}


async def test_readyz_redis_down(client) -> None:
    with patch.object(health, "Redis") as mock_redis:
        mock_client = AsyncMock()
        mock_client.ping.side_effect = ConnectionError("redis down")
        mock_redis.from_url.return_value = mock_client
        resp = await client.get("/api/v1/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["detail"]["checks"]["database"] == "ok"
    assert body["detail"]["checks"]["redis"] == "error"
