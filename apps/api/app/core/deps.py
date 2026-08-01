"""Shared FastAPI dependencies: current user + RBAC permission checks."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import forbidden, unauthorized
from app.core.security import decode_token
from app.models.user import User
from app.services.rbac_service import get_effective_permissions

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(request: Request, db: DbSession) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise unauthorized()
    payload = decode_token(auth_header.removeprefix("Bearer ").strip(), expected_type="access")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise unauthorized() from None
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(*codes: str):
    """Dependency factory: allows superusers and users holding any of ``codes``."""

    async def dependency(current_user: CurrentUser, db: DbSession) -> User:
        if current_user.is_superuser:
            return current_user
        permissions = await get_effective_permissions(db, current_user)
        if not set(codes).intersection(permissions):
            raise forbidden(f"Requires one of permissions: {', '.join(codes)}")
        return current_user

    return dependency
