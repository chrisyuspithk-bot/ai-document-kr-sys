"""Tests for AI Assistant CRUD endpoints with versioning and rollback."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers, login

ADMIN = ("admin", "admin-password-123")
POWER = ("power", "power-password-123")
STAFF = ("staff", "staff-password-123")


class TestAssistantCrud:
    @pytest.mark.asyncio
    async def test_create_and_list(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/assistants",
            json={
                "name": "長者服務助理",
                "description": "協助長者服務相關查詢",
                "system_prompt": "你是一個專業的長者服務助理。請用繁體中文回答。",
                "model": "deepseek-v4-flash",
                "mode": "internal",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "長者服務助理"
        assert data["version"] == 1
        assert data["mode"] == "internal"
        assert data["is_active"] is True
        assistant_id = data["id"]

        # List
        resp = await client.get("/api/v1/assistants", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "長者服務助理"

        # Get
        resp = await client.get(f"/api/v1/assistants/{assistant_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["system_prompt"] == "你是一個專業的長者服務助理。請用繁體中文回答。"

    @pytest.mark.asyncio
    async def test_update_creates_new_version(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/assistants",
            json={"name": "測試助理", "system_prompt": "v1 prompt", "model": "deepseek-v4-flash"},
            headers=headers,
        )
        assistant_id = resp.json()["id"]
        assert resp.json()["version"] == 1

        # Update the system prompt (should bump version)
        resp = await client.patch(
            f"/api/v1/assistants/{assistant_id}",
            json={"system_prompt": "v2 prompt improved"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2
        assert resp.json()["system_prompt"] == "v2 prompt improved"

        # Check versions list
        resp = await client.get(f"/api/v1/assistants/{assistant_id}/versions", headers=headers)
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) == 2
        assert versions[0]["version"] == 2
        assert versions[1]["version"] == 1

    @pytest.mark.asyncio
    async def test_rollback(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/assistants",
            json={"name": "可回滾助理", "system_prompt": "original prompt v1"},
            headers=headers,
        )
        assistant_id = resp.json()["id"]

        # Update twice
        await client.patch(
            f"/api/v1/assistants/{assistant_id}",
            json={"system_prompt": "updated prompt v2"},
            headers=headers,
        )
        await client.patch(
            f"/api/v1/assistants/{assistant_id}",
            json={"system_prompt": "updated prompt v3"},
            headers=headers,
        )

        # Rollback to v1
        resp = await client.post(
            f"/api/v1/assistants/{assistant_id}/rollback/1", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["system_prompt"] == "original prompt v1"
        assert data["version"] == 4  # v3 → rollback creates v4

    @pytest.mark.asyncio
    async def test_update_non_prompt_fields_no_version_bump(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/assistants",
            json={"name": "名稱測試", "system_prompt": "test"},
            headers=headers,
        )
        assistant_id = resp.json()["id"]
        assert resp.json()["version"] == 1

        # Update name/description only (not prompt-related)
        resp = await client.patch(
            f"/api/v1/assistants/{assistant_id}",
            json={"name": "新名稱", "description": "新描述"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "新名稱"
        assert resp.json()["version"] == 1  # no version bump for non-config changes

    @pytest.mark.asyncio
    async def test_delete_soft(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/assistants",
            json={"name": "待刪除助理"},
            headers=headers,
        )
        assistant_id = resp.json()["id"]

        resp = await client.delete(f"/api/v1/assistants/{assistant_id}", headers=headers)
        assert resp.status_code == 204

        # Should not appear in default list
        resp = await client.get("/api/v1/assistants", headers=headers)
        assert len(resp.json()) == 0

        # Should appear when include_inactive=True
        resp = await client.get("/api/v1/assistants?include_inactive=true", headers=headers)
        items = resp.json()
        assert len(items) == 1
        assert items[0]["is_active"] is False

    @pytest.mark.asyncio
    async def test_staff_cannot_create(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])
        resp = await client.post(
            "/api/v1/assistants",
            json={"name": "非法助理"},
            headers=headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_staff_can_list(self, client):
        admin_headers = auth_headers((await login(client, *ADMIN))["access_token"])
        staff_headers = auth_headers((await login(client, *STAFF))["access_token"])

        await client.post(
            "/api/v1/assistants",
            json={"name": "員工可見助理"},
            headers=admin_headers,
        )

        resp = await client.get("/api/v1/assistants", headers=staff_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_version(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])
        resp = await client.post(
            "/api/v1/assistants",
            json={"name": "測試"},
            headers=headers,
        )
        assistant_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/assistants/{assistant_id}/rollback/99", headers=headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_org_isolation(self, client):
        """Assistants from different orgs should not be visible across orgs."""
        admin_headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/assistants",
            json={"name": "管理員助理"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
