"""Seed script: root org, permission catalog, default roles, demo users.

Idempotent — safe to run multiple times.
Run: ``python -m app.db.seed``
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.organization import ORG_TYPE_ROOT, ORG_TYPE_SERVICE_UNIT, Organization
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.services.permissions import (
    PERMISSION_CATALOG,
    ROLE_APPROVER,
    ROLE_AUDITOR,
    ROLE_DEFINITIONS,
    ROLE_POWER_USER,
    ROLE_STAFF,
    ROLE_SYSTEM_ADMIN,
)

logger = get_logger(__name__)


async def seed(session: AsyncSession) -> None:
    # --- Root organization ----------------------------------------------------
    root_result = await session.execute(
        select(Organization).where(Organization.org_type == ORG_TYPE_ROOT)
    )
    root = root_result.scalars().first()
    if root is None:
        root = Organization(
            name="組織總部",
            code="ORG-ROOT",
            org_type=ORG_TYPE_ROOT,
        )
        session.add(root)
        await session.flush()
        logger.info("Created root organization")

    hq_result = await session.execute(select(Organization).where(Organization.code == "ORG-HQ"))
    hq = hq_result.scalars().first()
    if hq is None:
        hq = Organization(
            name="總部",
            code="ORG-HQ",
            org_type=ORG_TYPE_SERVICE_UNIT,
            parent_id=root.id,
        )
        session.add(hq)
        await session.flush()
        logger.info("Created HQ service unit")

    # --- Permissions -----------------------------------------------------------
    permission_ids: dict[str, object] = {}
    for code, description in PERMISSION_CATALOG:
        result = await session.execute(select(Permission).where(Permission.code == code))
        perm = result.scalar_one_or_none()
        if perm is None:
            perm = Permission(code=code, description=description)
            session.add(perm)
            await session.flush()
        permission_ids[code] = perm.id

    # --- Roles -------------------------------------------------------------------
    role_ids: dict[str, object] = {}
    for role_name in ROLE_DEFINITIONS:
        result = await session.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=role_name, description=f"Default role: {role_name}", is_system=True)
            session.add(role)
            await session.flush()
        role_ids[role_name] = role.id

    # --- Role → permission links ---------------------------------------------------
    for role_name, codes in ROLE_DEFINITIONS.items():
        for code in codes:
            link = await session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role_ids[role_name],
                    RolePermission.permission_id == permission_ids[code],
                )
            )
            if link.first() is None:
                session.add(
                    RolePermission(
                        role_id=role_ids[role_name],
                        permission_id=permission_ids[code],
                    )
                )

    # --- Users ---------------------------------------------------------------------
    settings = get_settings()
    users_to_create = [
        {
            "email": "admin@yot.hk",
            "username": "admin",
            "full_name": "系統管理員 (System Admin)",
            "password": settings.seed_admin_password,
            "org_id": hq.id,
            "roles": [ROLE_SYSTEM_ADMIN],
        },
        {
            "email": "poweruser@yot.hk",
            "username": "poweruser",
            "full_name": "高級用戶 (Power User)",
            "password": settings.seed_admin_password,
            "org_id": hq.id,
            "roles": [ROLE_POWER_USER],
        },
        {
            "email": "staff@yot.hk",
            "username": "staff",
            "full_name": "職員 (Staff)",
            "password": settings.seed_admin_password,
            "org_id": hq.id,
            "roles": [ROLE_STAFF],
        },
        {
            "email": "approver@yot.hk",
            "username": "approver",
            "full_name": "審批員 (Approver)",
            "password": settings.seed_admin_password,
            "org_id": hq.id,
            "roles": [ROLE_APPROVER],
        },
        {
            "email": "auditor@yot.hk",
            "username": "auditor",
            "full_name": "審計員 (Auditor)",
            "password": settings.seed_admin_password,
            "org_id": hq.id,
            "roles": [ROLE_AUDITOR],
        },
    ]
    for data in users_to_create:
        result = await session.execute(select(User).where(User.email == data["email"]))
        user = result.scalar_one_or_none()
        if user is not None:
            continue
        user = User(
            email=data["email"],
            username=data["username"],
            full_name=data["full_name"],
            password_hash=hash_password(data["password"]),
            org_id=data["org_id"],
            locale="zh-Hant",
            is_active=True,
            is_superuser=data["roles"] == [ROLE_SYSTEM_ADMIN],
        )
        session.add(user)
        await session.flush()
        for role_name in data["roles"]:
            session.add(UserRole(user_id=user.id, role_id=role_ids[role_name], org_id=None))
        logger.info("Seeded user %s", data["email"])

    await session.commit()


async def main() -> None:
    async with async_session_factory() as session:
        await seed(session)
    logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
