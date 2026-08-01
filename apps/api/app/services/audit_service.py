"""Append-only audit logging helper."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


def _request_meta(request: Request | None) -> dict[str, Any]:
    if request is None:
        return {}
    return {
        "request_id": getattr(request.state, "request_id", None),
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


async def write_audit(
    session: AsyncSession,
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    org_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | uuid.UUID | None = None,
    request: Request | None = None,
    detail: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    meta = _request_meta(request)
    entry = AuditLog(
        action=action,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        org_id=org_id,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        request_id=meta.get("request_id"),
        ip_address=meta.get("ip_address"),
        user_agent=meta.get("user_agent"),
        detail=detail,
        before_data=before,
        after_data=after,
    )
    session.add(entry)
    await session.flush()
    return entry
