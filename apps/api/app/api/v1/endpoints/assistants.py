"""AI Assistant management endpoints: CRUD, version history, rollback."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, not_found
from app.models.assistant import Assistant, AssistantVersion
from app.models.user import User
from app.schemas.assistant import (
    AssistantCreate,
    AssistantListItem,
    AssistantRead,
    AssistantUpdate,
    AssistantVersionRead,
)
from app.services.audit_service import write_audit
from app.services.permissions import ASSISTANT_READ, ASSISTANT_WRITE

router = APIRouter(prefix="/assistants", tags=["assistants"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[AssistantListItem])
async def list_assistants(
    include_inactive: bool = Query(False),
    db: DbSession = None,
    current_user: User = Depends(require_permission(ASSISTANT_READ)),
):
    stmt = select(Assistant).where(Assistant.org_id == current_user.org_id)
    if not include_inactive:
        stmt = stmt.where(Assistant.is_active.is_(True))
    stmt = stmt.order_by(Assistant.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=AssistantRead, status_code=201)
async def create_assistant(
    payload: AssistantCreate,
    db: DbSession = None,
    current_user: User = Depends(require_permission(ASSISTANT_WRITE)),
):
    assistant = Assistant(
        org_id=current_user.org_id,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        model=payload.model,
        kb_ids=[str(k) for k in payload.kb_ids] if payload.kb_ids else None,
        tools=payload.tools,
        mode=payload.mode,
        is_active=payload.is_active,
        version=1,
        created_by=current_user.id,
    )
    db.add(assistant)
    await db.flush()

    # Save v1 in version history
    v1 = AssistantVersion(
        assistant_id=assistant.id,
        version=1,
        system_prompt=payload.system_prompt,
        model=payload.model,
        kb_ids=assistant.kb_ids,
        tools=payload.tools,
        mode=payload.mode,
        created_by=current_user.id,
    )
    db.add(v1)
    await db.commit()
    await db.refresh(assistant)

    await write_audit(db, action="assistant.created", actor_user_id=current_user.id, resource_id=str(assistant.id))
    logger.info("Assistant created: %s by user %s", assistant.id, current_user.id)
    return assistant


@router.get("/{assistant_id}", response_model=AssistantRead)
async def get_assistant(
    assistant_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(ASSISTANT_READ)),
):
    assistant = await _get_assistant(db, assistant_id, current_user.org_id)
    return assistant


@router.patch("/{assistant_id}", response_model=AssistantRead)
async def update_assistant(
    assistant_id: uuid.UUID,
    payload: AssistantUpdate,
    db: DbSession = None,
    current_user: User = Depends(require_permission(ASSISTANT_WRITE)),
):
    assistant = await _get_assistant(db, assistant_id, current_user.org_id)

    changed = False
    new_version_fields = ("system_prompt", "model", "kb_ids", "tools", "mode")

    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        if key == "kb_ids" and val is not None:
            val = [str(k) for k in val]
        if getattr(assistant, key) != val:
            setattr(assistant, key, val)
            if key in new_version_fields:
                changed = True

    if changed:
        assistant.version += 1
        ver = AssistantVersion(
            assistant_id=assistant.id,
            version=assistant.version,
            system_prompt=assistant.system_prompt,
            model=assistant.model,
            kb_ids=assistant.kb_ids,
            tools=assistant.tools,
            mode=assistant.mode,
            created_by=current_user.id,
        )
        db.add(ver)

    await db.commit()
    await db.refresh(assistant)
    await write_audit(db, action="assistant.updated", actor_user_id=current_user.id, resource_id=str(assistant.id))
    return assistant


@router.delete("/{assistant_id}", status_code=204)
async def delete_assistant(
    assistant_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(ASSISTANT_WRITE)),
):
    assistant = await _get_assistant(db, assistant_id, current_user.org_id)
    assistant.is_active = False
    await db.commit()
    await write_audit(db, action="assistant.deleted", actor_user_id=current_user.id, resource_id=str(assistant_id))


@router.get("/{assistant_id}/versions", response_model=list[AssistantVersionRead])
async def list_versions(
    assistant_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(ASSISTANT_READ)),
):
    _ = await _get_assistant(db, assistant_id, current_user.org_id)
    result = await db.execute(
        select(AssistantVersion)
        .where(AssistantVersion.assistant_id == assistant_id)
        .order_by(AssistantVersion.version.desc())
    )
    return list(result.scalars().all())


@router.post("/{assistant_id}/rollback/{version}", response_model=AssistantRead)
async def rollback_version(
    assistant_id: uuid.UUID,
    version: int,
    db: DbSession = None,
    current_user: User = Depends(require_permission(ASSISTANT_WRITE)),
):
    assistant = await _get_assistant(db, assistant_id, current_user.org_id)

    result = await db.execute(
        select(AssistantVersion).where(
            AssistantVersion.assistant_id == assistant_id,
            AssistantVersion.version == version,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise not_found(f"Version {version} not found")

    assistant.system_prompt = target.system_prompt
    assistant.model = target.model
    assistant.kb_ids = target.kb_ids
    assistant.tools = target.tools
    assistant.mode = target.mode
    assistant.version += 1

    rollback_ver = AssistantVersion(
        assistant_id=assistant.id,
        version=assistant.version,
        system_prompt=assistant.system_prompt,
        model=assistant.model,
        kb_ids=assistant.kb_ids,
        tools=assistant.tools,
        mode=assistant.mode,
        created_by=current_user.id,
    )
    db.add(rollback_ver)
    await db.commit()
    await db.refresh(assistant)

    await write_audit(
        db,
        action="assistant.rollback",
        actor_user_id=current_user.id,
        resource_id=str(assistant_id),
    )
    return assistant


async def _get_assistant(db, assistant_id: uuid.UUID, org_id: uuid.UUID) -> Assistant:
    result = await db.execute(
        select(Assistant).where(Assistant.id == assistant_id, Assistant.org_id == org_id)
    )
    assistant = result.scalar_one_or_none()
    if not assistant:
        raise not_found("Assistant not found")
    return assistant
