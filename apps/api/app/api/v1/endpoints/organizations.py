"""Organization (tenant / service unit) endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select

from app.core.deps import DbSession, require_permission
from app.core.exceptions import conflict, not_found
from app.models.organization import Organization
from app.models.user import User
from app.schemas.org import OrgCreate, OrgRead, OrgUpdate
from app.services.audit_service import write_audit
from app.services.permissions import ORG_READ, ORG_WRITE

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrgRead])
async def list_organizations(
    db: DbSession,
    _: User = Depends(require_permission(ORG_READ)),
) -> list[OrgRead]:
    result = await db.execute(select(Organization).order_by(Organization.name))
    return [OrgRead.model_validate(o) for o in result.scalars().all()]


@router.post("", response_model=OrgRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrgCreate,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(ORG_WRITE)),
) -> OrgRead:
    existing = await db.execute(select(Organization.id).where(Organization.code == payload.code))
    if existing.first() is not None:
        raise conflict("Organization code already exists")
    org = Organization(
        name=payload.name,
        code=payload.code,
        org_type=payload.org_type,
        parent_id=payload.parent_id,
    )
    db.add(org)
    await db.flush()
    await write_audit(
        db,
        action="organization.create",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=org.id,
        resource_type="organization",
        resource_id=org.id,
        request=request,
        after={"name": org.name, "code": org.code},
    )
    await db.commit()
    return OrgRead.model_validate(org)


@router.patch("/{org_id}", response_model=OrgRead)
async def update_organization(
    org_id: uuid.UUID,
    payload: OrgUpdate,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(ORG_WRITE)),
) -> OrgRead:
    org = await db.get(Organization, org_id)
    if org is None:
        raise not_found("Organization not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is not None:
            setattr(org, field, value)
    await write_audit(
        db,
        action="organization.update",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=org.id,
        resource_type="organization",
        resource_id=org.id,
        request=request,
        after=data,
    )
    await db.commit()
    return OrgRead.model_validate(org)
