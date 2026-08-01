"""Audit log query + CSV export."""

from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.core.deps import DbSession, require_permission
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogPage, AuditLogRead
from app.services.permissions import AUDIT_EXPORT, AUDIT_READ

router = APIRouter(prefix="/audit-logs", tags=["audit"])

CSV_HEADERS = [
    "id",
    "created_at",
    "action",
    "actor_email",
    "org_id",
    "resource_type",
    "resource_id",
    "request_id",
    "ip_address",
    "detail",
]


@router.get("", response_model=AuditLogPage)
async def list_audit_logs(
    db: DbSession,
    _: User = Depends(require_permission(AUDIT_READ)),
    action: str | None = None,
    actor_email: str | None = None,
    org_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> AuditLogPage:
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if actor_email:
        filters.append(AuditLog.actor_email.ilike(f"%{actor_email}%"))
    if org_id:
        filters.append(AuditLog.org_id == org_id)

    total = await db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
    result = await db.execute(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = [AuditLogRead.model_validate(row) for row in result.scalars().all()]
    return AuditLogPage(items=items, total=total, page=page, size=size)


@router.get("/export")
async def export_audit_logs(
    db: DbSession,
    _: User = Depends(require_permission(AUDIT_EXPORT)),
    action: str | None = None,
    org_id: uuid.UUID | None = None,
) -> StreamingResponse:
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if org_id:
        filters.append(AuditLog.org_id == org_id)

    result = await db.execute(select(AuditLog).where(*filters).order_by(AuditLog.created_at.desc()))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    for entry in result.scalars().all():
        writer.writerow(
            [
                entry.id,
                entry.created_at.isoformat() if entry.created_at else "",
                entry.action,
                entry.actor_email or "",
                entry.org_id or "",
                entry.resource_type or "",
                entry.resource_id or "",
                entry.request_id or "",
                entry.ip_address or "",
                entry.detail or "",
            ]
        )
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit_logs.csv"'},
    )
