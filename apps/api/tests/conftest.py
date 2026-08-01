"""Shared pytest fixtures: in-memory SQLite database + seeded app client."""

from __future__ import annotations

import os

# Apply settings before any app module is imported (get_settings is cached).
os.environ["AIDG_STORAGE_BACKEND"] = "local"
os.environ["AIDG_LOCAL_STORAGE_ROOT"] = "data/uploads-test"
os.environ["AIDG_JINA_API_KEY"] = ""
os.environ["AIDG_STT_PROVIDER"] = "mock"

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import Base
from app.models.organization import ORG_TYPE_ROOT, ORG_TYPE_SERVICE_UNIT, Organization
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.services.permissions import (
    PERMISSION_CATALOG,
    ROLE_DEFINITIONS,
    ROLE_POWER_USER,
    ROLE_STAFF,
)


async def seed_minimal(session) -> None:
    """Seed the same structure as app.db.seed but only the essentials for tests."""
    root = Organization(name="Yan Oi Tong Limited (YOT)", code="YOT", org_type=ORG_TYPE_ROOT)
    hq = Organization(
        name="YOT 總部", code="YOT-HQ", org_type=ORG_TYPE_SERVICE_UNIT, parent_id=root.id
    )
    session.add_all([root, hq])
    await session.flush()

    permission_ids: dict[str, object] = {}
    for code, description in PERMISSION_CATALOG:
        perm = Permission(code=code, description=description)
        session.add(perm)
        await session.flush()
        permission_ids[code] = perm.id

    role_ids: dict[str, object] = {}
    for role_name in ROLE_DEFINITIONS:
        role = Role(name=role_name, description=role_name, is_system=True)
        session.add(role)
        await session.flush()
        role_ids[role_name] = role.id

    for role_name, codes in ROLE_DEFINITIONS.items():
        for code in codes:
            session.add(
                RolePermission(role_id=role_ids[role_name], permission_id=permission_ids[code])
            )

    admin = User(
        email="admin@test.hk",
        username="admin",
        full_name="Test Admin",
        password_hash=hash_password("admin-password-123"),
        org_id=hq.id,
        is_active=True,
        is_superuser=True,
    )
    staff = User(
        email="staff@test.hk",
        username="staff",
        full_name="Test Staff",
        password_hash=hash_password("staff-password-123"),
        org_id=hq.id,
        is_active=True,
    )
    power = User(
        email="power@test.hk",
        username="power",
        full_name="Test Power",
        password_hash=hash_password("power-password-123"),
        org_id=hq.id,
        is_active=True,
    )
    session.add_all([admin, staff, power])
    await session.flush()
    session.add(UserRole(user_id=staff.id, role_id=role_ids[ROLE_STAFF], org_id=None))
    session.add(UserRole(user_id=power.id, role_id=role_ids[ROLE_POWER_USER], org_id=None))
    await session.commit()


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        await seed_minimal(session)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def login(client: httpx.AsyncClient, username: str, password: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
