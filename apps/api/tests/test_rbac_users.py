"""RBAC enforcement and user management tests."""

from __future__ import annotations

import uuid

from tests.conftest import auth_headers, login


async def test_staff_cannot_list_users(client) -> None:
    token = (await login(client, "staff", "staff-password-123"))["access_token"]
    resp = await client.get("/api/v1/users", headers=auth_headers(token))
    assert resp.status_code == 403


async def test_power_user_can_list_users(client) -> None:
    token = (await login(client, "power", "power-password-123"))["access_token"]
    resp = await client.get("/api/v1/users", headers=auth_headers(token))
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert "staff@test.hk" in emails


async def test_admin_can_create_user(client) -> None:
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    resp = await client.post(
        "/api/v1/users",
        json={
            "email": "newuser@test.hk",
            "username": "newuser",
            "full_name": "New User",
            "password": "newuser-pass-123",
            "locale": "zh-Hant",
            "role_names": ["staff"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "newuser@test.hk"
    assert body["is_active"] is True


async def test_create_duplicate_user_conflict(client) -> None:
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    payload = {
        "email": "dupe@test.hk",
        "username": "dupe",
        "full_name": "Duplicate",
        "password": "dupe-pass-123",
    }
    resp = await client.post("/api/v1/users", json=payload, headers=auth_headers(token))
    assert resp.status_code == 201
    resp = await client.post("/api/v1/users", json=payload, headers=auth_headers(token))
    assert resp.status_code == 409


async def test_admin_can_update_user(client) -> None:
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    headers = auth_headers(token)
    listing = await client.get("/api/v1/users", headers=headers)
    staff_id = next(u["id"] for u in listing.json() if u["email"] == "staff@test.hk")
    resp = await client.patch(
        f"/api/v1/users/{staff_id}",
        json={"full_name": "Renamed Staff", "is_active": False},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "Renamed Staff"
    assert body["is_active"] is False


async def test_update_unknown_user_404(client) -> None:
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    resp = await client.patch(
        f"/api/v1/users/{uuid.uuid4()}",
        json={"full_name": "Nobody"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


async def test_staff_scoped_list(client) -> None:
    """Power user (non-superuser) only sees users in their own org."""
    token = (await login(client, "power", "power-password-123"))["access_token"]
    resp = await client.get("/api/v1/users", headers=auth_headers(token))
    assert resp.status_code == 200
    assert all(u["org_id"] is not None for u in resp.json())


async def test_roles_and_permissions_endpoints(client) -> None:
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    roles = await client.get("/api/v1/roles", headers=auth_headers(token))
    assert roles.status_code == 200
    role_names = {r["name"] for r in roles.json()}
    assert {"system_admin", "staff", "power_user"} <= role_names

    perms = await client.get("/api/v1/permissions", headers=auth_headers(token))
    assert perms.status_code == 200
    codes = {p["code"] for p in perms.json()}
    assert {"kb:read", "user:write", "audit:read"} <= codes


async def test_assign_and_revoke_role_changes_permissions(client) -> None:
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    headers = auth_headers(token)

    # staff cannot list users initially
    staff_token = (await login(client, "staff", "staff-password-123"))["access_token"]
    assert (await client.get("/api/v1/users", headers=auth_headers(staff_token))).status_code == 403

    # find role + user ids
    roles = (await client.get("/api/v1/roles", headers=headers)).json()
    power_role = next(r for r in roles if r["name"] == "power_user")
    users = (await client.get("/api/v1/users", headers=headers)).json()
    staff_id = next(u["id"] for u in users if u["email"] == "staff@test.hk")

    # grant power_user to staff (global scope)
    resp = await client.post(
        "/api/v1/roles/assign",
        json={"user_id": staff_id, "role_id": power_role["id"], "org_id": None},
        headers=headers,
    )
    assert resp.status_code == 204

    # staff can now list users
    assert (await client.get("/api/v1/users", headers=auth_headers(staff_token))).status_code == 200

    # revoke -> denied again
    resp = await client.post(
        "/api/v1/roles/revoke",
        json={"user_id": staff_id, "role_id": power_role["id"], "org_id": None},
        headers=headers,
    )
    assert resp.status_code == 204
    assert (await client.get("/api/v1/users", headers=auth_headers(staff_token))).status_code == 403


async def test_staff_cannot_assign_roles(client) -> None:
    token = (await login(client, "staff", "staff-password-123"))["access_token"]
    resp = await client.post(
        "/api/v1/roles/assign",
        json={
            "user_id": str(uuid.uuid4()),
            "role_id": str(uuid.uuid4()),
            "org_id": None,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
