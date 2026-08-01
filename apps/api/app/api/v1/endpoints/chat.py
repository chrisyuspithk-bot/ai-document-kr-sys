"""Chat and conversation endpoints — RAG queries + history management."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, not_found
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.chat import (
    ChatCitation,
    ChatRequest,
    ChatResponse,
    ConversationListItem,
    ConversationRead,
)
from app.services.audit_service import write_audit
from app.services.llm import MODELS
from app.services.permissions import KB_READ
from app.services.rag import (
    _FORMAT_INSTRUCTIONS,
    RAGCitation,
    RAGRequest,
    rag_query,
    rag_query_stream,
)

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


#  ---------------------------------------------------------------------------
#  Chat (non-streaming)
#  ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_READ)),
) -> ChatResponse:
    if payload.model not in MODELS:
        raise bad_request(f"Unknown model: {payload.model}")
    if payload.format not in _FORMAT_INSTRUCTIONS:
        raise bad_request(f"Unknown format: {payload.format}")

    # Create or reuse conversation
    conversation = await _get_or_create_conversation(
        db, current_user, payload.conversation_id, payload.query
    )

    # Save user message
    user_msg = Message(conversation_id=conversation.id, role="user", content=payload.query)
    db.add(user_msg)

    # Execute RAG
    rag_req = RAGRequest(
        query=payload.query,
        kb_ids=[str(k) for k in payload.kb_ids],
        user=current_user,
        model_name=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
        format=payload.format,
    )
    rag_resp = await rag_query(db, rag_req)

    # Save assistant message
    citations_dict = {
        "items": [
            {
                "document_id": c.document_id,
                "document_title": c.document_title,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "snippet": c.snippet,
                "score": c.score,
            }
            for c in rag_resp.citations
        ]
    }
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=rag_resp.answer,
        citations=citations_dict,
        model=rag_resp.model,
        usage=rag_resp.usage,
    )
    db.add(assistant_msg)

    # Audit
    await write_audit(
        db,
        action="chat.query",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=current_user.org_id,
        resource_type="conversation",
        resource_id=conversation.id,
        request=request,
        after={
            "query": payload.query[:500],
            "kb_ids": [str(k) for k in payload.kb_ids],
            "model": payload.model,
            "citations_count": len(rag_resp.citations),
        },
    )

    await db.commit()

    return ChatResponse(
        answer=rag_resp.answer,
        conversation_id=conversation.id,
        citations=[
            ChatCitation(
                document_id=c.document_id,
                document_title=c.document_title,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                snippet=c.snippet,
                score=c.score,
            )
            for c in rag_resp.citations
        ],
        model=rag_resp.model,
        usage=rag_resp.usage,
    )


#  ---------------------------------------------------------------------------
#  Chat (streaming SSE)
#  ---------------------------------------------------------------------------


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_READ)),
):
    if payload.model not in MODELS:
        raise bad_request(f"Unknown model: {payload.model}")
    if payload.format not in _FORMAT_INSTRUCTIONS:
        raise bad_request(f"Unknown format: {payload.format}")

    # Create or reuse conversation
    conversation = await _get_or_create_conversation(
        db, current_user, payload.conversation_id, payload.query
    )

    # Save user message
    user_msg = Message(conversation_id=conversation.id, role="user", content=payload.query)
    db.add(user_msg)
    await db.flush()

    rag_req = RAGRequest(
        query=payload.query,
        kb_ids=[str(k) for k in payload.kb_ids],
        user=current_user,
        model_name=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
        format=payload.format,
    )

    async def event_stream():
        full_answer: list[str] = []
        citations: list[dict] = []

        try:
            async for item in rag_query_stream(db, rag_req):
                if isinstance(item, RAGCitation):
                    citations.append(
                        {
                            "document_id": item.document_id,
                            "document_title": item.document_title,
                            "chunk_index": item.chunk_index,
                            "page_number": item.page_number,
                            "snippet": item.snippet,
                            "score": item.score,
                        }
                    )
                else:
                    # LlmStreamChunk
                    if item.delta:
                        full_answer.append(item.delta)
                        yield (
                            "data: "
                            + json.dumps(
                                {"type": "token", "content": item.delta},
                                ensure_ascii=False,
                            )
                            + "\n\n"
                        )

            # Save assistant message
            answer_text = "".join(full_answer)
            citations_dict = {"items": citations}
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer_text,
                citations=citations_dict,
                model=payload.model,
            )
            db.add(assistant_msg)
            await db.commit()

            # Send citations and done
            yield (
                "data: "
                + json.dumps({"type": "citations", "items": citations}, ensure_ascii=False)
                + "\n\n"
            )
            yield (
                "data: "
                + json.dumps(
                    {"type": "done", "conversation_id": str(conversation.id)},
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        except Exception as exc:
            logger.exception("Streaming chat failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


#  ---------------------------------------------------------------------------
#  Conversations CRUD
#  ---------------------------------------------------------------------------


@router.get("/conversations", response_model=list[ConversationListItem])
async def list_conversations(
    db: DbSession,
    current_user: User = Depends(require_permission(KB_READ)),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/conversations/{conv_id}", response_model=ConversationRead)
async def get_conversation(
    conv_id: uuid.UUID,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_READ)),
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise not_found("Conversation not found")
    return conv


@router.delete("/conversations/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: uuid.UUID,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_READ)),
) -> None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise not_found("Conversation not found")
    # Delete messages first (CASCADE may not work in SQLite without FK pragma)
    messages = (
        (await db.execute(select(Message).where(Message.conversation_id == conv_id)))
        .scalars()
        .all()
    )
    for msg in messages:
        await db.delete(msg)
    await db.delete(conv)
    await db.commit()


#  ---------------------------------------------------------------------------
#  Helpers
#  ---------------------------------------------------------------------------


async def _get_or_create_conversation(
    db: AsyncSession,
    user: User,
    conv_id: uuid.UUID | None,
    query: str,
) -> Conversation:
    if conv_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conv_id,
                Conversation.user_id == user.id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise not_found("Conversation not found")
        return conv

    title = query[:80] + ("…" if len(query) > 80 else "")
    conv = Conversation(
        user_id=user.id,
        org_id=user.org_id,
        title=title,
    )
    db.add(conv)
    await db.flush()
    return conv
