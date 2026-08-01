"""Authentication flow tests: login, refresh rotation, logout, profile."""

from __future__ import annotations

from tests.conftest import auth_headers, login


async def test_login_success(client) -> None:
    body = await login(client, "admin", "admin-password-123")
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_login_failure(client) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert resp.status_code == 400


async def test_login_unknown_user(client) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "nobody", "password": "whatever"}
    )
    assert resp.status_code == 400


async def test_me(client) -> None:
    token = (await login(client, "admin", "admin-password-123"))["access_token"]
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "admin@test.hk"
    assert body["is_superuser"] is True


async def test_me_unauthenticated(client) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_invalid_token(client) -> None:
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


async def test_refresh_rotation(client) -> None:
    first = await login(client, "staff", "staff-password-123")
    refresh = first["refresh_token"]

    # Rotate: valid once
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    second = resp.json()
    assert second["access_token"]
    assert second["refresh_token"] != refresh

    # Old refresh token must now be rejected
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401


async def test_logout_revokes_refresh(client) -> None:
    body = await login(client, "staff", "staff-password-123")
    resp = await client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]})
    assert resp.status_code == 204

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert resp.status_code == 401


async def test_change_password(client) -> None:
    token = (await login(client, "staff", "staff-password-123"))["access_token"]
    headers = auth_headers(token)
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "staff-password-123", "new_password": "brand-new-pass-456"},
        headers=headers,
    )
    assert resp.status_code == 204

    # Old password no longer works
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "staff", "password": "staff-password-123"}
    )
    assert resp.status_code == 400

    # New password works
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "staff", "password": "brand-new-pass-456"}
    )
    assert resp.status_code == 200
