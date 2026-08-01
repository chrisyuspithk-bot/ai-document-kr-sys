"""Role and permission endpoints + role assignment."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, not_found
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.schemas.user import PermissionRead, RoleAssignRequest, RoleRead, RoleRevokeRequest
from app.services.audit_service import write_audit
from app.services.permissions import USER_WRITE

router = APIRouter(tags=["rbac"])


async def _role_to_read(session: DbSession, role: Role) -> RoleRead:
    result = await session.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id)
    )
    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permission_codes=[row[0] for row in result],
    )


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(
    db: DbSession, _: User = Depends(require_permission(USER_WRITE))
) -> list[RoleRead]:
    result = await db.execute(select(Role).order_by(Role.name))
    return [await _role_to_read(db, role) for role in result.scalars().all()]


@router.get("/permissions", response_model=list[PermissionRead])
async def list_permissions(
    db: DbSession,
    _: User = Depends(require_permission(USER_WRITE)),
) -> list[PermissionRead]:
    result = await db.execute(select(Permission).order_by(Permission.code))
    return [PermissionRead.model_validate(p) for p in result.scalars().all()]


@router.post("/roles/assign", status_code=status.HTTP_204_NO_CONTENT)
async def assign_role(
    payload: RoleAssignRequest,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(USER_WRITE)),
) -> None:
    user = await db.get(User, payload.user_id)
    role = await db.get(Role, payload.role_id)
    if user is None or role is None:
        raise not_found("User or role not found")
    existing = await db.execute(
        select(UserRole).where(
            UserRole.user_id == payload.user_id,
            UserRole.role_id == payload.role_id,
            UserRole.org_id == payload.org_id,
        )
    )
    if existing.first() is not None:
        raise bad_request("Role already assigned")
    db.add(UserRole(user_id=payload.user_id, role_id=payload.role_id, org_id=payload.org_id))
    await write_audit(
        db,
        action="rbac.role_assign",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=user.org_id,
        resource_type="user",
        resource_id=user.id,
        request=request,
        after={
            "role": role.name,
            "scope": "global" if payload.org_id is None else str(payload.org_id),
        },
    )
    await db.commit()


@router.post("/roles/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_role(
    payload: RoleRevokeRequest,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(USER_WRITE)),
) -> None:
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == payload.user_id,
            UserRole.role_id == payload.role_id,
            UserRole.org_id == payload.org_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise not_found("Role assignment not found")
    await db.delete(assignment)
    await write_audit(
        db,
        action="rbac.role_revoke",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=current_user.org_id,
        resource_type="user",
        resource_id=payload.user_id,
        request=request,
        after={
            "role_id": str(payload.role_id),
            "scope": "global" if payload.org_id is None else str(payload.org_id),
        },
    )
    await db.commit()
