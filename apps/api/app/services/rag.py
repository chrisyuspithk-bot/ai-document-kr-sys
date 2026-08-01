"""RAG pipeline: retrieval → context assembly → LLM generation with citations."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.llm import (
    LlmMessage,
    LlmRole,
    LlmStreamChunk,
    get_provider_for,
)
from app.services.retrieval import RetrievalQuery, SearchResult, hybrid_search

logger = logging.getLogger(__name__)

#  ---------------------------------------------------------------------------
#  Public types
#  ---------------------------------------------------------------------------


@dataclass
class RAGCitation:
    document_id: str
    document_title: str
    chunk_index: int
    page_number: int | None
    snippet: str
    score: float


@dataclass
class RAGRequest:
    query: str
    kb_ids: list[str]
    user: User
    model_name: str = "deepseek-v4-flash"
    temperature: float = 0.3
    max_tokens: int = 4096
    top_k: int = 8
    similarity_threshold: float = 0.5
    format: str = "default"  # default | summary | bullets | table | formal


@dataclass
class RAGResponse:
    answer: str
    citations: list[RAGCitation] = field(default_factory=list)
    model: str = ""
    usage: dict | None = None


#  ---------------------------------------------------------------------------
#  System prompts per output format
#  ---------------------------------------------------------------------------

_FORMAT_INSTRUCTIONS: dict[str, str] = {
    "default": "請以自然段落回答問題，使用繁體中文，語氣專業。",
    "summary": "請以摘要形式回答，使用繁體中文，列出重點要點。",
    "bullets": "請以要點（bullet points）形式回答，使用繁體中文，每項簡潔清晰。",
    "table": "請盡量以表格形式整理回答，使用繁體中文，表格欄位清晰。",
    "formal": "請以正式公文語氣回答，使用繁體中文，結構嚴謹，適用於政府或機構文件。",
}

_SYSTEM_TEMPLATE = (
    "你是一個專業的知識助手，服務於仁愛堂社會服務部（Yan Oi Tong Social Services Division）。\n"
    "你必須僅根據以下提供的參考資料回答問題。如果參考資料中沒有足夠資訊，"
    "請明確說明「根據現有資料無法回答此問題」，不要猜測或編造資訊。\n"
    "\n"
    "回答規範：\n"
    "- 使用繁體中文（Traditional Chinese），專有名詞可保留英文\n"
    "- {format_instruction}\n"
    "- 回答時引用來源，格式為【來源：文件名稱，第X段】\n"
    "- 保持專業、準確、客觀的語氣\n"
    "\n"
    "{context}\n"
    "\n"
    "---\n"
    "\n"
    "問題：{question}\n"
    "\n"
    "回答："
)


def _build_system_prompt(context: str, question: str, fmt: str) -> str:
    instruction = _FORMAT_INSTRUCTIONS.get(fmt, _FORMAT_INSTRUCTIONS["default"])
    return _SYSTEM_TEMPLATE.format(
        context=context,
        question=question,
        format_instruction=instruction,
    )


def _assemble_context(
    search_results: list[SearchResult], top_k: int
) -> tuple[str, list[RAGCitation]]:
    """Build a context block from retrieved chunks and return citations."""
    context_parts: list[str] = []
    citations: list[RAGCitation] = []

    for i, sr in enumerate(search_results[:top_k], 1):
        context_parts.append(f"【參考資料 {i}】來源：{sr.document_title}\n{sr.content}\n")
        citations.append(
            RAGCitation(
                document_id=str(sr.document_id),
                document_title=sr.document_title,
                chunk_index=0,
                page_number=sr.page,
                snippet=sr.content[:300],
                score=sr.score,
            )
        )

    return "\n".join(context_parts), citations


def _org_ids_for_user(user: User) -> list[uuid.UUID] | None:
    return None if user.is_superuser else [uuid.UUID(str(user.org_id))]


#  ---------------------------------------------------------------------------
#  Main pipeline
#  ---------------------------------------------------------------------------


async def rag_query(db: AsyncSession, request: RAGRequest) -> RAGResponse:
    """Execute a full RAG query: retrieve → build context → generate."""
    # 1. Retrieve
    kb_ids = [u for k in request.kb_ids if (u := _try_parse_uuid(k))]
    query_params = RetrievalQuery(
        query=request.query,
        kb_ids=kb_ids if kb_ids else None,
        org_ids=_org_ids_for_user(request.user),
        top_k=request.top_k,
        min_score=request.similarity_threshold,
    )
    results = await hybrid_search(db, query_params)

    # 2. Build context
    context, citations = _assemble_context(results, request.top_k)

    # 3. Generate
    provider, model_info = get_provider_for(request.model_name)
    system_prompt = _build_system_prompt(context, request.query, request.format)

    messages = [
        LlmMessage(role=LlmRole.SYSTEM, content=system_prompt),
        LlmMessage(role=LlmRole.USER, content=request.query),
    ]

    llm_resp = await provider.chat(
        messages,
        model=model_info.id,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )

    return RAGResponse(
        answer=llm_resp.content,
        citations=citations,
        model=llm_resp.model or request.model_name,
        usage={
            "prompt_tokens": llm_resp.usage.prompt_tokens,
            "completion_tokens": llm_resp.usage.completion_tokens,
        },
    )


async def rag_query_stream(
    db: AsyncSession, request: RAGRequest
) -> AsyncIterator[LlmStreamChunk | RAGCitation]:
    """Streaming RAG: yields tokens, then yields citations as a final pseudo-chunk."""
    # 1. Retrieve
    kb_ids = [u for k in request.kb_ids if (u := _try_parse_uuid(k))]
    query_params = RetrievalQuery(
        query=request.query,
        kb_ids=kb_ids if kb_ids else None,
        org_ids=_org_ids_for_user(request.user),
        top_k=request.top_k,
        min_score=request.similarity_threshold,
    )
    results = await hybrid_search(db, query_params)

    # 2. Build context
    context, citations = _assemble_context(results, request.top_k)

    # 3. Stream generation
    provider, model_info = get_provider_for(request.model_name)
    system_prompt = _build_system_prompt(context, request.query, request.format)

    messages = [
        LlmMessage(role=LlmRole.SYSTEM, content=system_prompt),
        LlmMessage(role=LlmRole.USER, content=request.query),
    ]

    async for chunk in provider.chat_stream(
        messages,
        model=model_info.id,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    ):
        yield chunk

    # Yield citations as final items
    for citation in citations:
        yield citation


def _try_parse_uuid(s: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(s)
    except (ValueError, AttributeError):
        return None
