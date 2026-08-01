"""Document processing pipeline: fetch -> parse -> chunk -> embed -> persist."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.knowledge import (
    DOC_STATUS_FAILED,
    DOC_STATUS_INDEXED,
    DOC_STATUS_PROCESSING,
    JOB_STATUS_FAILED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    Document,
    DocumentChunk,
    DocumentVersion,
    ProcessingJob,
)
from app.services.chunker import chunk_text
from app.services.embeddings import get_embedding_provider
from app.services.parsers import parse_file
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

MAX_CHUNKS_PER_DOCUMENT = 5000


async def create_processing_job(
    db: AsyncSession, document_id: uuid.UUID, version_id: uuid.UUID
) -> ProcessingJob:
    job = ProcessingJob(
        document_id=document_id,
        document_version_id=version_id,
        status=JOB_STATUS_RUNNING,
        started_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def process_document_version(db: AsyncSession, version_id: uuid.UUID) -> ProcessingJob:
    """Run the full pipeline for one document version within ``db``.

    Throws on processing failures — the caller decides how to surface them
    (background wrapper marks the job failed).
    """
    settings = get_settings()
    version = await db.get(DocumentVersion, version_id)
    if version is None:
        raise ValueError(f"Document version not found: {version_id}")
    document = await db.get(Document, version.document_id)

    job = ProcessingJob(
        document_id=document.id,
        document_version_id=version.id,
        status=JOB_STATUS_RUNNING,
        started_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()

    document.status = DOC_STATUS_PROCESSING
    version.status = JOB_STATUS_RUNNING
    await db.commit()

    try:
        storage = get_storage(settings)
        data = await storage.get(version.storage_key)
        parsed = parse_file(version.filename, version.mime_type, data)

        chunks: list[tuple[int, str]] = []
        for page_number, page_text in enumerate(parsed.pages, start=1):
            for piece in chunk_text(page_text):
                if len(chunks) >= MAX_CHUNKS_PER_DOCUMENT:
                    logger.warning(
                        "Document %s exceeds %d chunks; truncating",
                        document.id,
                        MAX_CHUNKS_PER_DOCUMENT,
                    )
                    break
                chunks.append((page_number, piece))

        embedding_provider = get_embedding_provider(settings)
        vectors = await embedding_provider.embed([text for _, text in chunks])

        # Replacing the version's chunks makes re-processing idempotent.
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.version_number == version.version_number,
            )
        )

        for index, ((page_number, text), embedding) in enumerate(zip(chunks, vectors, strict=True)):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    kb_id=document.kb_id,
                    org_id=document.org_id,
                    version_number=version.version_number,
                    chunk_index=index,
                    content=text,
                    metadata_={"page": page_number},
                    embedding=embedding,
                )
            )

        document.status = DOC_STATUS_INDEXED
        document.version_number = version.version_number
        version.status = JOB_STATUS_SUCCEEDED
        version.chunk_count = len(chunks)
        version.error_message = None
        job.status = JOB_STATUS_SUCCEEDED
        job.finished_at = datetime.now(UTC)
        await db.commit()
    except Exception as exc:
        logger.exception("Processing failed for version %s", version.id)
        document.status = DOC_STATUS_FAILED
        version.status = JOB_STATUS_FAILED
        version.error_message = str(exc)[:2000]
        job.status = JOB_STATUS_FAILED
        job.error_message = str(exc)[:2000]
        job.finished_at = datetime.now(UTC)
        await db.commit()
        raise

    return job


async def run_processing_job_background(version_id: uuid.UUID) -> None:
    """Background-task entrypoint: owns its session and never raises."""
    async with async_session_factory() as db:
        try:
            await process_document_version(db, version_id)
        except Exception:
            logger.exception("Background processing failed for version %s", version_id)


async def get_latest_job(db: AsyncSession, document_id: uuid.UUID) -> ProcessingJob | None:
    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
