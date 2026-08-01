"""RAG retrieval endpoint: permission-scoped hybrid search."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, forbidden
from app.models.knowledge import KnowledgeBase
from app.models.user import User
from app.schemas.knowledge import RetrievalRequest, RetrievalResult
from app.services.audit_service import write_audit
from app.services.permissions import KB_READ
from app.services.retrieval import RetrievalQuery, hybrid_search

router = APIRouter(tags=["retrieval"])


@router.post("/retrieval/search", response_model=list[RetrievalResult])
async def search(
    payload: RetrievalRequest,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_READ)),
) -> list[RetrievalResult]:
    org_ids = None if current_user.is_superuser else [current_user.org_id]
    kb_ids = await _allowed_kb_ids(db, current_user, payload.kb_ids)

    results = await hybrid_search(
        db,
        RetrievalQuery(
            query=payload.query,
            kb_ids=kb_ids,
            org_ids=org_ids,
            top_k=payload.top_k,
            min_score=payload.min_score,
        ),
    )

    await write_audit(
        db,
        action="retrieval.search",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=current_user.org_id,
        resource_type="retrieval",
        request=request,
        after={
            "query": payload.query,
            "kb_ids": [str(k) for k in payload.kb_ids] if payload.kb_ids else None,
            "top_k": payload.top_k,
            "result_count": len(results),
        },
    )
    await db.commit()

    return [
        RetrievalResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            kb_id=r.kb_id,
            document_title=r.document_title,
            content=r.content,
            page=r.page,
            score=round(r.score, 4),
            vector_score=round(r.vector_score, 4) if r.vector_score is not None else None,
            keyword_score=round(r.keyword_score, 4) if r.keyword_score is not None else None,
        )
        for r in results
    ]


async def _allowed_kb_ids(
    db: AsyncSession, user: User, requested: list[uuid.UUID] | None
) -> list[uuid.UUID] | None:
    """Validate requested KB ids against the user's scope.

    Returns ``None`` when the user may search all visible KBs (superuser), and
    the restricted id list otherwise.
    """
    if requested is None:
        return None if user.is_superuser else await _visible_kb_ids(db, user)
    if user.is_superuser:
        found = set(
            (await db.execute(select(KnowledgeBase.id).where(KnowledgeBase.id.in_(requested))))
            .scalars()
            .all()
        )
        if len(found) != len(set(requested)):
            raise bad_request("One or more knowledge bases do not exist")
        return list(found)
    visible = set(await _visible_kb_ids(db, user))
    existing = set(
        (await db.execute(select(KnowledgeBase.id).where(KnowledgeBase.id.in_(requested))))
        .scalars()
        .all()
    )
    if not existing.intersection(set(requested)):
        raise bad_request("One or more knowledge bases do not exist")
    found = set(requested).intersection(visible)
    if len(found) != len(set(requested)):
        raise forbidden("One or more knowledge bases are outside your permission scope")
    return list(found)


async def _visible_kb_ids(db: AsyncSession, user: User) -> list[uuid.UUID]:
    result = await db.execute(
        select(KnowledgeBase.id).where(
            KnowledgeBase.org_id == user.org_id, KnowledgeBase.is_active.is_(True)
        )
    )
    kb_ids = list(result.scalars().all())
    return await _filter_kb_ids_by_group_membership(db, user, kb_ids)


async def _user_group_ids(db: AsyncSession, user: User) -> set[uuid.UUID]:
    """Group IDs the user belongs to inside their organisation."""
    from app.models.rbac import UserGroup

    rows = await db.execute(select(UserGroup.group_id).where(UserGroup.user_id == user.id))
    return set(rows.scalars().all())


async def _filter_kb_ids_by_group_membership(
    db: AsyncSession, user: User, kb_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    """Drop KBs that are group-restricted and the user is not a member of."""
    from app.models.knowledge import (
        KnowledgeBaseGroupPermission,
    )

    user_groups = await _user_group_ids(db, user)
    if not kb_ids:
        return []

    rows = await db.execute(
        select(
            KnowledgeBaseGroupPermission.knowledge_base_id,
            KnowledgeBaseGroupPermission.group_id,
        ).where(KnowledgeBaseGroupPermission.knowledge_base_id.in_(kb_ids))
    )
    perms_by_kb: dict[uuid.UUID, set[uuid.UUID]] = {}
    for kb_id, group_id in rows.all():
        perms_by_kb.setdefault(kb_id, set()).add(group_id)

    return [
        kb_id
        for kb_id in kb_ids
        if kb_id not in perms_by_kb or bool(perms_by_kb[kb_id] & user_groups)
    ]
