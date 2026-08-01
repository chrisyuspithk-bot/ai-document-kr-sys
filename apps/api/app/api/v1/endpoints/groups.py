"""Group management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, not_found
from app.models.rbac import Group, UserGroup
from app.models.user import User
from app.schemas.user import GroupCreate, GroupMemberRequest, GroupRead
from app.services.audit_service import write_audit
from app.services.permissions import GROUP_READ, GROUP_WRITE

router = APIRouter(prefix="/groups", tags=["groups"])


async def _to_read(db: DbSession, group: Group) -> GroupRead:
    count = await db.scalar(
        select(func.count(UserGroup.user_id)).where(UserGroup.group_id == group.id)
    )
    return GroupRead(
        id=group.id,
        org_id=group.org_id,
        name=group.name,
        description=group.description,
        member_count=count or 0,
        created_at=group.created_at,
    )


@router.get("", response_model=list[GroupRead])
async def list_groups(
    db: DbSession,
    current_user: User = Depends(require_permission(GROUP_READ)),
) -> list[GroupRead]:
    stmt = select(Group).order_by(Group.name)
    if not current_user.is_superuser:
        stmt = stmt.where(Group.org_id == current_user.org_id)
    result = await db.execute(stmt)
    return [await _to_read(db, g) for g in result.scalars().all()]


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(GROUP_WRITE)),
) -> GroupRead:
    org_id = payload.org_id or current_user.org_id
    group = Group(name=payload.name, description=payload.description, org_id=org_id)
    db.add(group)
    await db.flush()
    await write_audit(
        db,
        action="group.create",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=org_id,
        resource_type="group",
        resource_id=group.id,
        request=request,
        after={"name": group.name},
    )
    await db.commit()
    return await _to_read(db, group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(GROUP_WRITE)),
) -> None:
    group = await db.get(Group, group_id)
    if group is None:
        raise not_found("Group not found")
    await db.delete(group)
    await write_audit(
        db,
        action="group.delete",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=group.org_id,
        resource_type="group",
        resource_id=group.id,
        request=request,
    )
    await db.commit()


@router.post("/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(
    group_id: uuid.UUID,
    payload: GroupMemberRequest,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(GROUP_WRITE)),
) -> None:
    group = await db.get(Group, group_id)
    user = await db.get(User, payload.user_id)
    if group is None or user is None:
        raise not_found("Group or user not found")
    existing = await db.execute(
        select(UserGroup).where(
            UserGroup.group_id == group_id, UserGroup.user_id == payload.user_id
        )
    )
    if existing.first() is not None:
        raise bad_request("User is already a member")
    db.add(UserGroup(group_id=group_id, user_id=payload.user_id))
    await write_audit(
        db,
        action="group.add_member",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=group.org_id,
        resource_type="group",
        resource_id=group_id,
        request=request,
        after={"user_id": str(payload.user_id)},
    )
    await db.commit()


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(GROUP_WRITE)),
) -> None:
    result = await db.execute(
        select(UserGroup).where(UserGroup.group_id == group_id, UserGroup.user_id == user_id)
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise not_found("Membership not found")
    await db.delete(membership)
    await write_audit(
        db,
        action="group.remove_member",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=current_user.org_id,
        resource_type="group",
        resource_id=group_id,
        request=request,
        after={"user_id": str(user_id)},
    )
    await db.commit()
