"""Hybrid retrieval: vector (pgvector) + keyword (pg_trgm / ILIKE).

Ranking combines both signals with Reciprocal Rank Fusion; ``score`` is a
weighted blend of the raw similarity values (0..1) so callers get an
interpretable confidence plus per-signal breakdowns for the UI.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy import and_, bindparam, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import DOC_STATUS_INDEXED, Document, DocumentChunk
from app.services.embeddings import EMBEDDING_DIM, get_embedding_provider

logger = logging.getLogger(__name__)

RRF_K = 60
VECTOR_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.4


@dataclass
class SearchResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    kb_id: uuid.UUID
    document_title: str
    content: str
    page: int | None
    score: float
    vector_score: float | None
    keyword_score: float | None


@dataclass
class RetrievalQuery:
    query: str
    kb_ids: list[uuid.UUID] | None = None
    org_ids: list[uuid.UUID] | None = None
    top_k: int = 10
    min_score: float = 0.0


async def hybrid_search(
    db: AsyncSession,
    params: RetrievalQuery,
) -> list[SearchResult]:
    if not params.query.strip():
        return []

    top_k = max(1, min(params.top_k, 50))
    scope_filters = _scope_filters(params)
    dialect = db.bind.dialect.name if db.bind is not None else ""

    vectors: list[tuple[DocumentChunk, float]] = []
    keywords: list[tuple[DocumentChunk, float]] = []

    if dialect == "postgresql":
        vectors = await _vector_candidates(db, params, scope_filters, top_k)
        keywords = await _keyword_candidates(db, params, scope_filters, top_k)
    else:
        # SQLite / other dialects: keyword-only via ILIKE.
        keywords = await _keyword_candidates(db, params, scope_filters, top_k)

    if not vectors and not keywords:
        return []

    documents = await _load_documents(db, {c.document_id for c, _ in [*vectors, *keywords]})
    fused = _rrf_rank(vectors, keywords)

    results: list[SearchResult] = []
    for chunk, _rrf_score in fused:
        vector_score = next((s for c, s in vectors if c.id == chunk.id), None)
        keyword_score = next((s for c, s in keywords if c.id == chunk.id), None)
        score = _blend_score(vector_score, keyword_score)
        if score < params.min_score:
            continue
        results.append(
            SearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                kb_id=chunk.kb_id,
                document_title=documents.get(chunk.document_id, ""),
                content=chunk.content,
                page=(chunk.metadata_ or {}).get("page"),
                score=score,
                vector_score=vector_score,
                keyword_score=keyword_score,
            )
        )
        if len(results) >= top_k:
            break
    return results


def _scope_filters(params: RetrievalQuery) -> list:
    conditions = [
        DocumentChunk.version_number == Document.version_number,
        Document.status == DOC_STATUS_INDEXED,
        DocumentChunk.document_id == Document.id,
    ]
    if params.kb_ids:
        conditions.append(DocumentChunk.kb_id.in_(params.kb_ids))
    if params.org_ids:
        conditions.append(DocumentChunk.org_id.in_(params.org_ids))
    return conditions


async def _vector_candidates(
    db: AsyncSession,
    params: RetrievalQuery,
    scope_filters: list,
    top_k: int,
) -> list[tuple[DocumentChunk, float]]:
    provider = get_embedding_provider()
    query_vector = (await provider.embed([params.query]))[0]

    from pgvector.sqlalchemy import Vector as PGVector

    # Bind the query vector with the pgvector type so its bind processor renders
    # the Python list as a vector literal. `return_type` must be set on the op
    # so the resulting expression is numeric and binds correctly.
    query_bind = bindparam("query_vec", value=query_vector, type_=PGVector(EMBEDDING_DIM))
    distance = DocumentChunk.embedding.op("<=>", return_type=sa.Float)(query_bind)

    stmt = (
        select(DocumentChunk, (1 - distance).label("vector_score"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(and_(*scope_filters, DocumentChunk.embedding.is_not(None)))
        .order_by(distance.asc())
        .limit(top_k * 4)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [(row[0], float(row[1])) for row in rows]


async def _keyword_candidates(
    db: AsyncSession,
    params: RetrievalQuery,
    scope_filters: list,
    top_k: int,
) -> list[tuple[DocumentChunk, float]]:
    dialect = db.bind.dialect.name if db.bind is not None else ""
    query = params.query.strip()
    escaped = query.replace("%", r"\%").replace("_", r"\_")

    stmt = select(DocumentChunk).join(Document, Document.id == DocumentChunk.document_id)
    if dialect == "postgresql":
        # word_similarity matches the query's trigram set against the best
        # continuous extent of the content, which suits CJK phrases far better
        # than whole-string similarity.
        word_sim = func.word_similarity(query, DocumentChunk.content)
        stmt = (
            select(DocumentChunk, word_sim.label("keyword_score"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(and_(*scope_filters, word_sim > 0.05))
            .order_by(word_sim.desc())
            .limit(top_k * 4)
        )
        result = await db.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

    stmt = stmt.where(and_(*scope_filters, DocumentChunk.content.ilike(f"%{escaped}%"))).limit(
        top_k * 4
    )
    result = await db.execute(stmt)
    return [(chunk, 1.0) for chunk in result.scalars().all()]


async def _load_documents(db: AsyncSession, document_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not document_ids:
        return {}
    result = await db.execute(
        select(Document.id, Document.title).where(Document.id.in_(document_ids))
    )
    return {row.id: row.title for row in result.all()}


def _rrf_rank(
    vectors: list[tuple[DocumentChunk, float]],
    keywords: list[tuple[DocumentChunk, float]],
) -> list[tuple[DocumentChunk, float]]:
    fused: dict[uuid.UUID, float] = defaultdict(float)
    chunk_by_id: dict[uuid.UUID, DocumentChunk] = {}
    for method in (vectors, keywords):
        for rank, (chunk, _score) in enumerate(method):
            fused[chunk.id] += 1.0 / (RRF_K + rank + 1)
            chunk_by_id[chunk.id] = chunk
    ranked = sorted(fused.items(), key=lambda item: item[1], reverse=True)
    return [(chunk_by_id[chunk_id], score) for chunk_id, score in ranked]


def _blend_score(vector_score: float | None, keyword_score: float | None) -> float:
    # Clamp negative cosine similarity (orthogonal vectors, mock embeddings) to
    # zero so they never penalise a strong keyword match.
    vector = max(vector_score or 0.0, 0.0)
    keyword = keyword_score or 0.0
    if vector_score is not None and keyword_score is not None:
        return VECTOR_WEIGHT * vector + KEYWORD_WEIGHT * keyword
    return vector if vector_score is not None else keyword
