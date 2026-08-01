"""User creation / update helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.exceptions import conflict
from app.models.rbac import Role, UserRole
from app.models.user import User


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    username: str,
    full_name: str,
    password: str,
    org_id: uuid.UUID | None = None,
    locale: str = "zh-Hant",
    role_names: list[str] | None = None,
    is_active: bool = True,
) -> User:
    email = email.lower()
    existing = await session.execute(
        select(User.id).where(or_(User.email == email, User.username == username))
    )
    if existing.first() is not None:
        raise conflict("Email or username already exists")

    user = User(
        email=email,
        username=username,
        full_name=full_name,
        password_hash=security.hash_password(password),
        org_id=org_id,
        locale=locale,
        is_active=is_active,
    )
    session.add(user)
    await session.flush()

    for role_name in role_names or []:
        result = await session.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if role is not None:
            session.add(UserRole(user_id=user.id, role_id=role.id, org_id=None))
    await session.flush()
    return user


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)
