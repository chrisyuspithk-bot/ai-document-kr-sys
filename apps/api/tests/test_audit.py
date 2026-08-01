"""Audit log tests: recording, permissioned read, CSV export."""

from __future__ import annotations

from tests.conftest import auth_headers, login


async def test_login_is_audited(client) -> None:
    await login(client, "admin", "admin-password-123")
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    resp = await client.get("/api/v1/audit-logs?action=auth.login", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(item["action"] == "auth.login" for item in body["items"])
    assert body["items"][0]["actor_email"] == "admin@test.hk"


async def test_failed_login_is_audited(client) -> None:
    await client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    resp = await client.get(
        "/api/v1/audit-logs?action=auth.login_failed", headers=auth_headers(token)
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_staff_cannot_read_audit(client) -> None:
    token = (await login(client, "staff", "staff-password-123"))["access_token"]
    resp = await client.get("/api/v1/audit-logs", headers=auth_headers(token))
    assert resp.status_code == 403


async def test_export_csv(client) -> None:
    await login(client, "admin", "admin-password-123")
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    resp = await client.get("/api/v1/audit-logs/export", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "auth.login" in resp.text


async def test_pagination(client) -> None:
    for _ in range(3):
        await login(client, "staff", "staff-password-123")
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    resp = await client.get(
        "/api/v1/audit-logs?page=1&size=2&action=auth.login", headers=auth_headers(token)
    )
    body = resp.json()
    assert body["size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 3
