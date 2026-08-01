"""User management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import or_, select

from app.core import security
from app.core.deps import DbSession, require_permission
from app.core.exceptions import not_found
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import user_service
from app.services.audit_service import write_audit
from app.services.permissions import USER_READ, USER_WRITE

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
async def list_users(
    db: DbSession,
    current_user: User = Depends(require_permission(USER_READ)),
    q: str | None = None,
    org_id: uuid.UUID | None = None,
) -> list[UserRead]:
    stmt = select(User).order_by(User.created_at)
    if current_user.is_superuser and org_id is not None:
        stmt = stmt.where(User.org_id == org_id)
    elif not current_user.is_superuser:
        stmt = stmt.where(User.org_id == current_user.org_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(User.full_name.ilike(like), User.email.ilike(like), User.username.ilike(like))
        )
    result = await db.execute(stmt)
    return [UserRead.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(USER_WRITE)),
) -> UserRead:
    org_id = payload.org_id or current_user.org_id
    user = await user_service.create_user(
        db, **payload.model_dump(exclude={"org_id"}), org_id=org_id
    )
    await write_audit(
        db,
        action="user.create",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=user.org_id,
        resource_type="user",
        resource_id=user.id,
        request=request,
        after={"email": user.email, "username": user.username, "roles": payload.role_names},
    )
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    db: DbSession,
    current_user: User = Depends(require_permission(USER_READ)),
) -> UserRead:
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("User not found")
    if not current_user.is_superuser and user.org_id != current_user.org_id:
        raise not_found("User not found")
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(USER_WRITE)),
) -> UserRead:
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("User not found")
    if not current_user.is_superuser and user.org_id != current_user.org_id:
        raise not_found("User not found")

    before = {"email": user.email, "is_active": user.is_active, "org_id": str(user.org_id)}
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] is not None:
        data["email"] = data["email"].lower()
    if "password" in data and data["password"] is not None:
        data["password_hash"] = security.hash_password(data.pop("password"))
    for field, value in data.items():
        if hasattr(user, field) and value is not None:
            setattr(user, field, value)
    await write_audit(
        db,
        action="user.update",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=user.org_id,
        resource_type="user",
        resource_id=user.id,
        request=request,
        before=before,
        after={"email": user.email, "is_active": user.is_active},
    )
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)
