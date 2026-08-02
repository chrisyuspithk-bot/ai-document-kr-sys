"""Analytics & dashboard endpoints: token usage, system stats."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.deps import DbSession, require_permission
from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message
from app.models.document_gen import GeneratedDocument
from app.models.knowledge import Document, KnowledgeBase
from app.models.meeting import Meeting
from app.models.organization import Organization
from app.models.user import User
from app.services.llm import MODELS
from app.services.permissions import ANALYTICS_READ, MODEL_MANAGE

router = APIRouter(tags=["analytics"])
logger = __import__("logging").getLogger(__name__)


@router.get("/analytics/overview")
async def overview(
    db: DbSession = None,
    current_user: User = Depends(require_permission(ANALYTICS_READ)),
):
    org_id = current_user.org_id

    user_count = (await db.execute(
        select(func.count(User.id)).where(User.org_id == org_id, User.is_active.is_(True))
    )).scalar() or 0

    kb_count = (await db.execute(
        select(func.count(KnowledgeBase.id)).where(
            KnowledgeBase.org_id == org_id, KnowledgeBase.is_active.is_(True)
        )
    )).scalar() or 0

    doc_count = (await db.execute(
        select(func.count(Document.id)).where(Document.org_id == org_id)
    )).scalar() or 0

    gen_doc_count = (await db.execute(
        select(func.count(GeneratedDocument.id)).where(GeneratedDocument.org_id == org_id)
    )).scalar() or 0

    conv_count = (await db.execute(
        select(func.count(Conversation.id)).where(Conversation.org_id == org_id)
    )).scalar() or 0

    meeting_count = (await db.execute(
        select(func.count(Meeting.id)).where(Meeting.org_id == org_id)
    )).scalar() or 0

    assistant_count = (await db.execute(
        select(func.count(Assistant.id)).where(
            Assistant.org_id == org_id, Assistant.is_active.is_(True)
        )
    )).scalar() or 0

    return {
        "users": user_count,
        "knowledge_bases": kb_count,
        "documents": doc_count,
        "generated_documents": gen_doc_count,
        "conversations": conv_count,
        "meetings": meeting_count,
        "assistants": assistant_count,
    }


@router.get("/analytics/token-usage")
async def token_usage(
    days: int = Query(30, ge=1, le=365),
    db: DbSession = None,
    current_user: User = Depends(require_permission(ANALYTICS_READ)),
):
    """Aggregated token usage from chat messages in the last N days."""
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=days)

    result = await db.execute(
        select(Message).where(
            Message.created_at >= since,
            Message.role == "assistant",
            Message.usage.isnot(None),
        )
    )
    messages = result.scalars().all()

    total_prompt = sum((m.usage or {}).get("prompt_tokens", 0) for m in messages)
    total_completion = sum((m.usage or {}).get("completion_tokens", 0) for m in messages)

    by_model: dict[str, dict] = {}
    for m in messages:
        model = m.model or "unknown"
        if model not in by_model:
            by_model[model] = {"prompt_tokens": 0, "completion_tokens": 0, "requests": 0}
        by_model[model]["prompt_tokens"] += (m.usage or {}).get("prompt_tokens", 0)
        by_model[model]["completion_tokens"] += (m.usage or {}).get("completion_tokens", 0)
        by_model[model]["requests"] += 1

    return {
        "period_days": days,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_prompt + total_completion,
        "by_model": by_model,
    }


@router.get("/models")
async def list_models(
    current_user: User = Depends(require_permission(MODEL_MANAGE)),
):
    """List available LLM models with metadata."""
    return [
        {
            "name": info.id,
            "provider": info.provider,
            "max_tokens": info.max_tokens,
            "description": info.description,
        }
        for info in MODELS.values()
    ]
