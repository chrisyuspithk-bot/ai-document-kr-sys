"""Group and organization management tests."""

from __future__ import annotations

from tests.conftest import auth_headers, login


async def test_group_lifecycle(client) -> None:
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    headers = auth_headers(token)

    created = await client.post(
        "/api/v1/groups",
        json={"name": "家庭服務部", "description": "Family services"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    group_id = created.json()["id"]

    users = (await client.get("/api/v1/users", headers=headers)).json()
    staff_id = next(u["id"] for u in users if u["email"] == "staff@test.hk")

    added = await client.post(
        f"/api/v1/groups/{group_id}/members", json={"user_id": staff_id}, headers=headers
    )
    assert added.status_code == 204

    listing = await client.get("/api/v1/groups", headers=headers)
    assert listing.status_code == 200
    group = next(g for g in listing.json() if g["id"] == group_id)
    assert group["member_count"] == 1

    removed = await client.delete(f"/api/v1/groups/{group_id}/members/{staff_id}", headers=headers)
    assert removed.status_code == 204

    deleted = await client.delete(f"/api/v1/groups/{group_id}", headers=headers)
    assert deleted.status_code == 204


async def test_staff_cannot_manage_groups(client) -> None:
    token = (await login(client, "staff", "staff-password-123"))["access_token"]
    resp = await client.post(
        "/api/v1/groups", json={"name": "Blocked"}, headers=auth_headers(token)
    )
    assert resp.status_code == 403


async def test_organization_crud(client) -> None:
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    headers = auth_headers(token)

    created = await client.post(
        "/api/v1/organizations",
        json={"name": "葵青服務中心", "code": "KWAI-TSING", "org_type": "service_unit"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    org = created.json()
    assert org["code"] == "KWAI-TSING"

    duplicate = await client.post(
        "/api/v1/organizations",
        json={"name": "Dup", "code": "KWAI-TSING", "org_type": "service_unit"},
        headers=headers,
    )
    assert duplicate.status_code == 409

    updated = await client.patch(
        f"/api/v1/organizations/{org['id']}", json={"status": "inactive"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "inactive"


async def test_staff_cannot_create_organization(client) -> None:
    token = (await login(client, "staff", "staff-password-123"))["access_token"]
    resp = await client.post(
        "/api/v1/organizations",
        json={"name": "Blocked", "code": "BLOCKED", "org_type": "service_unit"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
