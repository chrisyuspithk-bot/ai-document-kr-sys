"""Integration API: key management (admin) and public integration endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, not_found
from app.models.integration import ApiKey
from app.models.user import User
from app.schemas.integration import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services.api_key import create_api_key, get_api_key_by_raw
from app.services.audit_service import write_audit

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/api-keys", tags=["integration-keys"])
public_router = APIRouter(prefix="/integration/v1", tags=["integration-public"])
_bearer = HTTPBearer(auto_error=False)


# ── Admin: API key management ────────────────────────────────────────

@admin_router.get("", response_model=list[ApiKeyRead])
async def list_api_keys(
    include_inactive: bool = Query(False),
    db: DbSession = None,
    current_user: User = Depends(require_permission("api-key:manage")),
):
    conditions = [ApiKey.org_id == current_user.org_id]
    if not include_inactive:
        conditions.append(ApiKey.is_active.is_(True))
    stmt = select(ApiKey).where(*conditions).order_by(ApiKey.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@admin_router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_key(
    payload: ApiKeyCreate,
    db: DbSession = None,
    current_user: User = Depends(require_permission("api-key:manage")),
):
    key_record, raw_key = await create_api_key(
        db,
        org_id=current_user.org_id,
        name=payload.name,
        created_by=current_user.id,
        permissions=payload.permissions,
        expires_at=payload.expires_at,
    )
    await write_audit(
        db,
        action="api_key.created",
        actor_user_id=current_user.id,
        resource_id=str(key_record.id),
    )
    return ApiKeyCreated(
        id=key_record.id,
        name=key_record.name,
        key_prefix=key_record.key_prefix,
        raw_key=raw_key,
        is_active=key_record.is_active,
        permissions=key_record.permissions,
        expires_at=key_record.expires_at,
        created_at=key_record.created_at,
    )


@admin_router.post("/{key_id}/revoke", status_code=204)
async def revoke_key(
    key_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission("api-key:manage")),
):
    stmt = select(ApiKey).where(
        ApiKey.id == key_id, ApiKey.org_id == current_user.org_id
    )
    key = (await db.execute(stmt)).scalar_one_or_none()
    if not key:
        raise not_found("API key not found")
    key.is_active = False
    await db.commit()
    await write_audit(
        db,
        action="api_key.revoked",
        actor_user_id=current_user.id,
        resource_id=str(key_id),
    )


@admin_router.delete("/{key_id}", status_code=204)
async def delete_key(
    key_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission("api-key:manage")),
):
    stmt = select(ApiKey).where(
        ApiKey.id == key_id, ApiKey.org_id == current_user.org_id
    )
    key = (await db.execute(stmt)).scalar_one_or_none()
    if not key:
        raise not_found("API key not found")
    await db.delete(key)
    await db.commit()
    await write_audit(
        db,
        action="api_key.deleted",
        actor_user_id=current_user.id,
        resource_id=str(key_id),
    )


# ── Public Integration Endpoints ─────────────────────────────────────

async def _auth_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: DbSession = None,
) -> ApiKey:
    """Authenticate API key from Bearer token. Raises 401 on failure."""
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Missing API key")
    raw = credentials.credentials
    key = await get_api_key_by_raw(db, raw)
    if not key:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    return key


@public_router.get("/health")
async def integration_health(
    api_key: ApiKey = Depends(_auth_api_key),
):
    """Integration endpoint health check."""
    return {
        "status": "ok",
        "key_name": api_key.name,
        "org_id": str(api_key.org_id),
    }


@public_router.get("/knowledge-bases")
async def list_kb_via_api(
    api_key: ApiKey = Depends(_auth_api_key),
    db: DbSession = None,
):
    """List accessible knowledge bases for this API key."""
    from app.models.knowledge import KnowledgeBase

    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.org_id == api_key.org_id)
        .where(KnowledgeBase.is_active.is_(True))
        .order_by(KnowledgeBase.name)
    )
    result = await db.execute(stmt)
    kbs = result.scalars().all()
    return [
        {
            "id": str(kb.id),
            "name": kb.name,
            "description": kb.description,
            "document_count": kb.document_count,
        }
        for kb in kbs
    ]


@public_router.post("/retrieval/search")
async def search_via_api(
    request: Request,
    api_key: ApiKey = Depends(_auth_api_key),
    db: DbSession = None,
):
    """Search knowledge bases via the integration API."""
    body = await request.json()
    query = body.get("query", "").strip()
    kb_ids = body.get("kb_ids")
    top_k = body.get("top_k", 5)

    if not query:
        raise bad_request("Query is required")
    if top_k < 1 or top_k > 50:
        raise bad_request("top_k must be between 1 and 50")

    from app.services.retrieval import search_documents

    results = await search_documents(
        db,
        query=query,
        kb_ids=kb_ids,
        org_id=api_key.org_id,
        top_k=top_k,
    )

    return {
        "query": query,
        "results": [
            {
                "document_id": str(r.document_id),
                "document_title": r.document_title,
                "chunk_text": r.chunk_text,
                "score": round(r.score, 4),
                "metadata": r.metadata,
            }
            for r in results
        ],
    }


@public_router.get("/documents/{document_id}")
async def get_document_via_api(
    document_id: uuid.UUID,
    api_key: ApiKey = Depends(_auth_api_key),
    db: DbSession = None,
):
    """Get document metadata via integration API."""
    from app.models.knowledge import Document

    stmt = select(Document).where(
        Document.id == document_id,
        Document.org_id == api_key.org_id,
    )
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise not_found("Document not found")

    return {
        "id": str(doc.id),
        "title": doc.title,
        "file_type": doc.file_type,
        "status": doc.status,
        "kb_id": str(doc.kb_id) if doc.kb_id else None,
        "created_at": doc.created_at.isoformat(),
    }
