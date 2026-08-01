"""Tests for integration API key management and public endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import auth_headers, login

POWER = ("power", "power-password-123")
STAFF = ("staff", "staff-password-123")


class TestApiKeyManagement:
    @pytest.mark.asyncio
    async def test_create_and_list_keys(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "Intranet Connector"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Intranet Connector"
        assert data["key_prefix"].startswith("ak_")
        assert "raw_key" in data
        assert data["message"]

        resp = await client.get("/api/v1/api-keys", headers=headers)
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) == 1
        assert keys[0]["name"] == "Intranet Connector"

    @pytest.mark.asyncio
    async def test_raw_key_not_in_list(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        await client.post(
            "/api/v1/api-keys",
            json={"name": "Test Key"},
            headers=headers,
        )
        resp = await client.get("/api/v1/api-keys", headers=headers)
        keys = resp.json()
        assert "raw_key" not in keys[0]

    @pytest.mark.asyncio
    async def test_revoke_key(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "Revokable Key"},
            headers=headers,
        )
        key_id = resp.json()["id"]
        raw_key = resp.json()["raw_key"]

        resp = await client.post(
            f"/api/v1/api-keys/{key_id}/revoke", headers=headers
        )
        assert resp.status_code == 204

        resp = await client.get("/api/v1/api-keys", headers=headers)
        keys = resp.json()
        assert len(keys) == 0

        resp = await client.get(
            "/api/v1/api-keys?include_inactive=true", headers=headers
        )
        keys = resp.json()
        assert len(keys) == 1
        assert keys[0]["is_active"] is False

        resp = await client.get(
            "/api/v1/integration/v1/health",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_key(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "Deletable Key"},
            headers=headers,
        )
        key_id = resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/api-keys/{key_id}", headers=headers
        )
        assert resp.status_code == 204

        resp = await client.get(
            "/api/v1/api-keys?include_inactive=true", headers=headers
        )
        assert len(resp.json()) == 0

    @pytest.mark.asyncio
    async def test_staff_cannot_manage_keys(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "Unauthorized"},
            headers=headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_cross_org_isolation(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        await client.post(
            "/api/v1/api-keys",
            json={"name": "Org A Key"},
            headers=headers,
        )
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/api/v1/api-keys/{fake_id}/revoke", headers=headers
        )
        assert resp.status_code == 404


class TestPublicIntegrationEndpoints:
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "Health Check Key"},
            headers=headers,
        )
        raw_key = resp.json()["raw_key"]

        resp = await client.get(
            "/api/v1/integration/v1/health",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["key_name"] == "Health Check Key"

    @pytest.mark.asyncio
    async def test_no_auth_header(self, client):
        resp = await client.get("/api/v1/integration/v1/health")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_key(self, client):
        resp = await client.get(
            "/api/v1/integration/v1/health",
            headers={"Authorization": "Bearer ak_invalid_key_here"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_knowledge_bases(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "KB Access Key"},
            headers=headers,
        )
        raw_key = resp.json()["raw_key"]

        resp = await client.get(
            "/api/v1/integration/v1/knowledge-bases",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_search_requires_query(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "Search Key"},
            headers=headers,
        )
        raw_key = resp.json()["raw_key"]

        resp = await client.post(
            "/api/v1/integration/v1/retrieval/search",
            json={"query": "", "top_k": 5},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_document_not_found(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "Doc Key"},
            headers=headers,
        )
        raw_key = resp.json()["raw_key"]

        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/integration/v1/documents/{fake_id}",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_expired_key(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        past_time = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
        resp = await client.post(
            "/api/v1/api-keys",
            json={"name": "Expired Key", "expires_at": past_time},
            headers=headers,
        )
        raw_key = resp.json()["raw_key"]

        resp = await client.get(
            "/api/v1/integration/v1/health",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code == 401
