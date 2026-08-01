"""Effective-permission resolution and org access helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rbac import Permission, RolePermission, UserRole
from app.models.user import User
from app.services.permissions import ALL_PERMISSION_CODES


async def get_effective_permissions(session: AsyncSession, user: User) -> set[str]:
    """Union of all permissions granted via the user's role assignments."""
    if user.is_superuser:
        return set(ALL_PERMISSION_CODES)
    result = await session.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user.id)
    )
    return {row[0] for row in result}


async def user_has_permission(session: AsyncSession, user: User, code: str) -> bool:
    return code in await get_effective_permissions(session, user)


async def user_can_access_org(session: AsyncSession, user: User, org_id: uuid.UUID) -> bool:
    """A user can access an org if it is their primary org, or if they hold an
    org-scoped role assignment within it (superusers always pass)."""
    if user.is_superuser:
        return True
    if user.org_id == org_id:
        return True
    result = await session.execute(
        select(UserRole.id).where(UserRole.user_id == user.id, UserRole.org_id == org_id)
    )
    return result.first() is not None
