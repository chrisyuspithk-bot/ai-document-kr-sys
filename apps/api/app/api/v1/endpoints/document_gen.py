"""Document generation endpoints: templates, generate, revise, approve, export."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, not_found
from app.models.document_gen import (
    DOCGEN_STATUS_APPROVED,
    DOCGEN_STATUS_DRAFT,
    DOCGEN_STATUS_REJECTED,
    DOCGEN_STATUS_SUBMITTED,
    DocumentTemplate,
    GeneratedDocument,
)
from app.models.user import User
from app.schemas.document_gen import (
    DocumentListItem,
    DocumentRead,
    GenerateRequest,
    GenerateResponse,
    ReviewRequest,
    ReviseRequest,
    SubmitRequest,
    TemplateCreate,
    TemplateListItem,
    TemplateRead,
    TemplateUpdate,
)
from app.services.audit_service import write_audit
from app.services.document_gen import (
    export_document,
    generate_document,
    render_template,
    revise_document,
)
from app.services.llm import MODELS
from app.services.permissions import KB_READ, KB_WRITE
from app.services.rag import _FORMAT_INSTRUCTIONS

router = APIRouter(tags=["document-gen"])
logger = logging.getLogger(__name__)


#  ---------------------------------------------------------------------------
#  Templates CRUD
#  ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[TemplateListItem])
async def list_templates(
    category: str | None = Query(None),
    active_only: bool = Query(True),
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_READ)),
):
    stmt = select(DocumentTemplate).where(DocumentTemplate.org_id == current_user.org_id)
    if active_only:
        stmt = stmt.where(DocumentTemplate.is_active.is_(True))
    if category:
        stmt = stmt.where(DocumentTemplate.category == category)
    stmt = stmt.order_by(DocumentTemplate.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/templates", response_model=TemplateRead, status_code=201)
async def create_template(
    payload: TemplateCreate,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_WRITE)),
):
    tmpl = DocumentTemplate(
        name=payload.name,
        description=payload.description,
        category=payload.category,
        content=payload.content,
        variables=payload.variables,
        style_config=payload.style_config,
        org_id=current_user.org_id,
        created_by=current_user.id,
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    await write_audit(
        db,
        action="document_template.created",
        actor_user_id=current_user.id,
        resource_id=str(tmpl.id),
    )
    return tmpl


@router.get("/templates/{template_id}", response_model=TemplateRead)
async def get_template(
    template_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_READ)),
):
    result = await db.execute(
        select(DocumentTemplate).where(
            DocumentTemplate.id == template_id,
            DocumentTemplate.org_id == current_user.org_id,
        )
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise not_found("Template not found")
    return tmpl


@router.patch("/templates/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_WRITE)),
):
    result = await db.execute(
        select(DocumentTemplate).where(
            DocumentTemplate.id == template_id,
            DocumentTemplate.org_id == current_user.org_id,
        )
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise not_found("Template not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(tmpl, key, val)
    tmpl.version += 1
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_WRITE)),
):
    result = await db.execute(
        select(DocumentTemplate).where(
            DocumentTemplate.id == template_id,
            DocumentTemplate.org_id == current_user.org_id,
        )
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise not_found("Template not found")
    tmpl.is_active = False
    await db.commit()


#  ---------------------------------------------------------------------------
#  Document generation
#  ---------------------------------------------------------------------------


@router.post("/generate", response_model=GenerateResponse, status_code=201)
async def generate(
    payload: GenerateRequest,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_READ)),
):
    if payload.model not in MODELS:
        raise bad_request(f"Unknown model: {payload.model}")
    if payload.format not in _FORMAT_INSTRUCTIONS:
        raise bad_request(f"Unknown format: {payload.format}")

    # Fetch template if specified
    template_content = None
    rendered = None
    if payload.template_id:
        result = await db.execute(
            select(DocumentTemplate).where(
                DocumentTemplate.id == payload.template_id,
                DocumentTemplate.org_id == current_user.org_id,
            )
        )
        tmpl = result.scalar_one_or_none()
        if not tmpl:
            raise not_found("Template not found")
        template_content = tmpl.content
        if payload.fill_values and tmpl.variables:
            rendered = render_template(tmpl.content, payload.fill_values)

    # Fetch KB context
    kb_context = ""
    if payload.source_kb_ids:
        kb_context = await _gather_kb_context(db, payload.source_kb_ids, current_user.org_id)

    # Generate
    content, usage = await generate_document(
        payload.prompt,
        template_content=template_content,
        rendered_template=rendered,
        kb_context=kb_context,
        model=payload.model,
    )

    # Persist as draft
    doc = GeneratedDocument(
        template_id=payload.template_id,
        title=payload.title or _extract_title(content),
        status=DOCGEN_STATUS_DRAFT,
        org_id=current_user.org_id,
        created_by=current_user.id,
        content=content,
        prompt=payload.prompt,
        fill_values=payload.fill_values,
        source_kb_ids=[str(k) for k in payload.source_kb_ids] if payload.source_kb_ids else None,
        model=payload.model,
        usage=usage,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    await write_audit(
        db,
        action="document.generated",
        actor_user_id=current_user.id,
        resource_id=str(doc.id),
    )
    logger.info("Document generated: %s by user %s", doc.id, current_user.id)

    return GenerateResponse(
        id=doc.id,
        title=doc.title,
        content=content,
        status=doc.status,
        model=payload.model,
        usage=usage,
        created_at=doc.created_at,
    )


@router.post("/gen-documents/{doc_id}/revise", response_model=GenerateResponse)
async def revise(
    doc_id: uuid.UUID,
    payload: ReviseRequest,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_READ)),
):
    result = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == doc_id,
            GeneratedDocument.org_id == current_user.org_id,
            GeneratedDocument.created_by == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise not_found("Document not found")
    if doc.status not in (DOCGEN_STATUS_DRAFT, DOCGEN_STATUS_REJECTED):
        raise bad_request("Only draft or rejected documents can be revised")

    content, usage = await revise_document(doc.content, payload.prompt)

    doc.content = content
    doc.status = DOCGEN_STATUS_DRAFT
    doc.prompt = payload.prompt
    doc.usage = usage
    doc.version += 1
    doc.docx_path = None
    doc.pdf_path = None
    await db.commit()
    await db.refresh(doc)
    await write_audit(
        db,
        action="document.revised",
        actor_user_id=current_user.id,
        resource_id=str(doc.id),
    )
    logger.info("Document revised: %s", doc.id)

    return GenerateResponse(
        id=doc.id,
        title=doc.title,
        content=content,
        status=doc.status,
        model=doc.model,
        usage=usage,
        created_at=doc.created_at,
    )


#  ---------------------------------------------------------------------------
#  Approval workflow (lite)
#  ---------------------------------------------------------------------------


@router.post("/gen-documents/{doc_id}/submit", response_model=DocumentRead)
async def submit_for_approval(
    doc_id: uuid.UUID,
    payload: SubmitRequest | None = None,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_READ)),
):
    result = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == doc_id,
            GeneratedDocument.org_id == current_user.org_id,
            GeneratedDocument.created_by == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise not_found("Document not found")
    if doc.status != DOCGEN_STATUS_DRAFT:
        raise bad_request("Only draft documents can be submitted for approval")
    doc.status = DOCGEN_STATUS_SUBMITTED
    await db.commit()
    await db.refresh(doc)
    await write_audit(
        db,
        action="document.submitted",
        actor_user_id=current_user.id,
        resource_id=str(doc.id),
    )
    return doc


@router.post("/gen-documents/{doc_id}/approve", response_model=DocumentRead)
async def approve(
    doc_id: uuid.UUID,
    payload: ReviewRequest | None = None,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_WRITE)),
):
    result = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == doc_id,
            GeneratedDocument.org_id == current_user.org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise not_found("Document not found")
    if doc.status != DOCGEN_STATUS_SUBMITTED:
        raise bad_request("Only submitted documents can be approved")
    # DEV: allow self-approval for single-user demos
    # if doc.created_by == current_user.id:
    #     raise bad_request("Cannot approve your own document")

    doc.status = DOCGEN_STATUS_APPROVED
    doc.reviewed_by = current_user.id
    doc.review_comment = (payload.comment if payload else None)
    await db.commit()
    await db.refresh(doc)
    await write_audit(
        db,
        action="document.approved",
        actor_user_id=current_user.id,
        resource_id=str(doc.id),
    )
    return doc


@router.post("/gen-documents/{doc_id}/reject", response_model=DocumentRead)
async def reject(
    doc_id: uuid.UUID,
    payload: ReviewRequest,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_WRITE)),
):
    result = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == doc_id,
            GeneratedDocument.org_id == current_user.org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise not_found("Document not found")
    if doc.status != DOCGEN_STATUS_SUBMITTED:
        raise bad_request("Only submitted documents can be rejected")
    doc.status = DOCGEN_STATUS_REJECTED
    doc.reviewed_by = current_user.id
    doc.review_comment = payload.comment or ""
    await db.commit()
    await db.refresh(doc)
    await write_audit(
        db,
        action="document.rejected",
        actor_user_id=current_user.id,
        resource_id=str(doc.id),
    )
    return doc


#  ---------------------------------------------------------------------------
#  Export
#  ---------------------------------------------------------------------------


@router.post("/gen-documents/{doc_id}/export")
async def export(
    doc_id: uuid.UUID,
    fmt: str = Query("both", pattern="^(docx|pdf|both)$"),
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_READ)),
):
    result = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == doc_id,
            GeneratedDocument.org_id == current_user.org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise not_found("Document not found")
    if doc.status != DOCGEN_STATUS_APPROVED:
        raise bad_request("Only approved documents can be exported")

    paths = await export_document(doc.id, doc.content, fmt)

    # Persist paths
    doc.docx_path = paths.get("docx")
    doc.pdf_path = paths.get("pdf")
    await db.commit()

    await write_audit(
        db,
        action="document.exported",
        actor_user_id=current_user.id,
        resource_id=str(doc.id),
    )
    return {"docx": paths.get("docx"), "pdf": paths.get("pdf")}


@router.get("/gen-documents/{doc_id}/download/{file_type}")
async def download(
    doc_id: uuid.UUID,
    file_type: str,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_READ)),
):
    if file_type not in ("docx", "pdf"):
        raise bad_request("File type must be 'docx' or 'pdf'")

    result = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == doc_id,
            GeneratedDocument.org_id == current_user.org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise not_found("Document not found")

    path_attr = f"{file_type}_path"
    path = getattr(doc, path_attr, None)
    if not path:
        raise not_found(f"No {file_type.upper()} export exists. Export the document first.")

    filename = f"{doc.title or doc_id}.{file_type}"
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=filename,
    )


#  ---------------------------------------------------------------------------
#  Document history & retrieval
#  ---------------------------------------------------------------------------


@router.get("/gen-documents", response_model=list[DocumentListItem])
async def list_documents(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_READ)),
):
    stmt = (
        select(GeneratedDocument)
        .where(GeneratedDocument.org_id == current_user.org_id)
        .order_by(GeneratedDocument.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if status:
        stmt = stmt.where(GeneratedDocument.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/gen-documents/{doc_id}", response_model=DocumentRead)
async def get_document(
    doc_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_READ)),
):
    result = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == doc_id,
            GeneratedDocument.org_id == current_user.org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise not_found("Document not found")
    return doc


@router.delete("/gen-documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(KB_WRITE)),
):
    result = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == doc_id,
            GeneratedDocument.org_id == current_user.org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise not_found("Document not found")
    await db.delete(doc)
    await db.commit()
    await write_audit(
        db,
        action="document.deleted",
        actor_user_id=current_user.id,
        resource_id=str(doc_id),
    )


#  ---------------------------------------------------------------------------
#  Helpers
#  ---------------------------------------------------------------------------


async def _gather_kb_context(
    db: AsyncSession,
    kb_ids: list[uuid.UUID],
    org_id: uuid.UUID,
    max_chunks: int = 10,
) -> str:
    """Fetch top chunks from specified knowledge bases for document context."""
    from app.services.retrieval import hybrid_search

    all_chunks: list[str] = []
    for kb_id in kb_ids:
        results = await hybrid_search(
            db,
            query="",  # will be refined; for now get top content
            kb_id=kb_id,
            org_id=org_id,
            top_k=max_chunks,
        )
        for r in results:
            all_chunks.append(r.content)

    return "\n\n---\n\n".join(all_chunks[:max_chunks * 3])


def _extract_title(content: str) -> str:
    """Extract a title from the first # heading, or use first line."""
    for line in content.strip().split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:][:200]
        if line:
            return line[:200]
    return "Untitled"
