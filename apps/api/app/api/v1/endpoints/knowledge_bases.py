"""Knowledge base, document upload and document management endpoints."""

from __future__ import annotations

import io
import logging
import uuid
from datetime import UTC
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, forbidden, not_found
from app.models.knowledge import (
    DOC_STATUS_DRAFT,
    Document,
    DocumentChunk,
    DocumentVersion,
    KnowledgeBase,
    KnowledgeBaseGroupPermission,
    ProcessingJob,
)
from app.models.user import User
from app.schemas.knowledge import (
    DocumentChunkRead,
    DocumentRead,
    DocumentUpdate,
    DocumentVersionRead,
    KbGroupPermissionRead,
    KbGroupPermissionRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
)
from app.services.audit_service import write_audit
from app.services.parsers import resolve_mime_type
from app.services.permissions import DOCUMENT_READ, DOCUMENT_WRITE, KB_DELETE, KB_READ, KB_WRITE
from app.services.processing import (
    create_processing_job,
    process_document_version,
    run_processing_job_background,
)
from app.services.storage import checksum, get_storage

router = APIRouter(tags=["knowledge"])

logger = logging.getLogger(__name__)

KB_PREFIX = "/knowledge-bases"
DOC_PREFIX = "/documents"


def _visible_org_ids(user: User) -> list[uuid.UUID] | None:
    """Scope helper: superusers see everything; others are confined to their org."""
    return None if user.is_superuser else [user.org_id]


async def _user_group_ids(db: AsyncSession, user: User) -> set[uuid.UUID]:
    from app.models.rbac import UserGroup

    rows = await db.execute(select(UserGroup.group_id).where(UserGroup.user_id == user.id))
    return set(rows.scalars().all())


async def _filter_kb_ids_by_group_membership(
    db: AsyncSession, user: User, kb_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    from app.models.knowledge import KnowledgeBaseGroupPermission

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


async def _get_visible_kb(
    db: AsyncSession, user: User, kb_id: uuid.UUID, *, for_write: bool = False
) -> KnowledgeBase:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise not_found("Knowledge base not found")
    if not user.is_superuser and kb.org_id != user.org_id:
        raise forbidden("Knowledge base is outside your organisation")
    if not user.is_superuser:
        visible = await _filter_kb_ids_by_group_membership(db, user, [kb_id])
        if not visible:
            raise forbidden("Knowledge base is restricted to specific groups")
    if for_write and not kb.is_active:
        raise bad_request("Knowledge base is inactive")
    return kb


@router.get(KB_PREFIX, response_model=list[KnowledgeBaseRead])
async def list_knowledge_bases(
    db: DbSession,
    current_user: User = Depends(require_permission(KB_READ)),
) -> list[KnowledgeBase]:
    org_ids = _visible_org_ids(current_user)
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.name)
    if org_ids is not None:
        stmt = stmt.where(KnowledgeBase.org_id.in_(org_ids))
    result = await db.execute(stmt)
    kbs = list(result.scalars().all())
    if not current_user.is_superuser:
        visible_ids = set(
            await _filter_kb_ids_by_group_membership(db, current_user, [kb.id for kb in kbs])
        )
        kbs = [kb for kb in kbs if kb.id in visible_ids]
    return kbs


@router.post(KB_PREFIX, response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_WRITE)),
) -> KnowledgeBase:
    org_id = payload.org_id or current_user.org_id
    if payload.org_id and not current_user.is_superuser:
        raise forbidden("Only superusers may create knowledge bases for other organisations")
    kb = KnowledgeBase(
        name=payload.name,
        description=payload.description,
        org_id=org_id,
        is_active=payload.is_active,
    )
    db.add(kb)
    await db.flush()
    await write_audit(
        db,
        action="knowledge_base.create",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=org_id,
        resource_type="knowledge_base",
        resource_id=kb.id,
        request=request,
        after={"name": kb.name, "description": kb.description},
    )
    await db.commit()
    return kb


@router.get(f"{KB_PREFIX}/{{kb_id}}", response_model=KnowledgeBaseRead)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_READ)),
) -> KnowledgeBase:
    return await _get_visible_kb(db, current_user, kb_id)


@router.patch(f"{KB_PREFIX}/{{kb_id}}", response_model=KnowledgeBaseRead)
async def update_knowledge_base(
    kb_id: uuid.UUID,
    payload: KnowledgeBaseUpdate,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_WRITE)),
) -> KnowledgeBase:
    kb = await _get_visible_kb(db, current_user, kb_id, for_write=True)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(kb, field, value)
    await db.commit()
    await db.refresh(kb)
    await write_audit(
        db,
        action="knowledge_base.update",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=kb.org_id,
        resource_type="knowledge_base",
        resource_id=kb.id,
        request=request,
        after=data,
    )
    await db.commit()
    return kb


@router.delete(f"{KB_PREFIX}/{{kb_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_DELETE)),
) -> None:
    kb = await _get_visible_kb(db, current_user, kb_id)
    doc_ids = (await db.execute(select(Document.id).where(Document.kb_id == kb_id))).scalars().all()
    version_ids = (
        (
            await db.execute(
                select(DocumentVersion.id).where(DocumentVersion.document_id.in_(doc_ids))
            )
        )
        .scalars()
        .all()
    )
    await db.execute(DocumentChunk.__table__.delete().where(DocumentChunk.kb_id == kb_id))
    await db.execute(ProcessingJob.__table__.delete().where(ProcessingJob.document_id.in_(doc_ids)))
    await db.execute(DocumentVersion.__table__.delete().where(DocumentVersion.id.in_(version_ids)))
    await db.execute(Document.__table__.delete().where(Document.id.in_(doc_ids)))
    await db.execute(KnowledgeBase.__table__.delete().where(KnowledgeBase.id == kb_id))
    await write_audit(
        db,
        action="knowledge_base.delete",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=kb.org_id,
        resource_type="knowledge_base",
        resource_id=kb_id,
        request=request,
    )
    await db.commit()


@router.get(f"{KB_PREFIX}/{{kb_id}}/documents", response_model=list[DocumentRead])
async def list_documents(
    kb_id: uuid.UUID,
    db: DbSession,
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_permission(DOCUMENT_READ)),
) -> list[Document]:
    await _get_visible_kb(db, current_user, kb_id)
    stmt = select(Document).where(Document.kb_id == kb_id)
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)
    stmt = stmt.order_by(Document.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    f"{KB_PREFIX}/{{kb_id}}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    kb_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    document_id: uuid.UUID | None = Form(default=None),
    process_sync: bool = Form(default=False),
    current_user: User = Depends(require_permission(DOCUMENT_WRITE)),
) -> Document:
    kb = await _get_visible_kb(db, current_user, kb_id, for_write=True)

    data = await file.read()
    if not data:
        raise bad_request("Uploaded file is empty")
    if len(data) > 50 * 1024 * 1024:
        raise bad_request("File exceeds the 50 MB upload limit")

    filename = file.filename or "document.bin"
    mime_type = file.content_type or "application/octet-stream"

    if document_id is not None:
        document = await db.get(Document, document_id)
        if document is None or document.kb_id != kb_id:
            raise not_found("Document not found in this knowledge base")
        await _get_visible_kb(db, current_user, document.kb_id)
        new_version = document.version_number + 1
        document.status = DOC_STATUS_DRAFT
        document.version_number = new_version
        document.title = title or document.title
    else:
        document = Document(
            kb_id=kb_id,
            org_id=kb.org_id or current_user.org_id,
            title=title or filename,
            filename=filename,
            mime_type=mime_type,
            status=DOC_STATUS_DRAFT,
            uploaded_by=current_user.id,
        )
        db.add(document)
        new_version = 1
    await db.flush()

    storage = get_storage()
    storage_key = f"docs/{kb_id}/{uuid.uuid4().hex}_{filename}"
    await storage.put(storage_key, data)

    version = DocumentVersion(
        document_id=document.id,
        version_number=new_version,
        storage_key=storage_key,
        filename=filename,
        mime_type=mime_type,
        checksum=checksum(data),
        size_bytes=len(data),
    )
    db.add(version)
    await db.flush()

    if process_sync:
        try:
            await process_document_version(db, version.id)
        except Exception as exc:
            logger.warning("Synchronous processing failed for %s: %s", version.id, exc)
    else:
        await create_processing_job(db, document.id, version.id)
        background_tasks.add_task(run_processing_job_background, version.id)

    await write_audit(
        db,
        action="document.upload",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=document.org_id,
        resource_type="document",
        resource_id=document.id,
        request=request,
        after={
            "filename": filename,
            "kb_id": str(kb_id),
            "version": new_version,
            "storage_key": storage_key,
        },
    )
    await db.commit()
    await db.refresh(document)
    return await _document_read_model(db, document)


@router.post(
    f"{KB_PREFIX}/{{kb_id}}/documents/bulk",
    response_model=list[DocumentRead],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_upload_documents(
    kb_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission(DOCUMENT_WRITE)),
) -> list[Document]:
    """Upload a ZIP archive of documents; each file becomes a document."""
    import zipfile

    kb = await _get_visible_kb(db, current_user, kb_id, for_write=True)
    zip_data = await file.read()
    if not zip_data:
        raise bad_request("Uploaded ZIP is empty")
    if len(zip_data) > 200 * 1024 * 1024:
        raise bad_request("ZIP exceeds the 200 MB upload limit")

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_data))
    except zipfile.BadZipFile as exc:
        raise bad_request("Uploaded file is not a valid ZIP archive") from exc

    storage = get_storage()
    org_id = kb.org_id or current_user.org_id
    created: list[Document] = []

    for entry in zf.infolist():
        if entry.is_dir():
            continue
        entry_data = zf.read(entry)
        if not entry_data or len(entry_data) > 50 * 1024 * 1024:
            continue
        filename = Path(entry.filename).name or entry.filename
        mime_type = resolve_mime_type(filename, "application/octet-stream")

        document = Document(
            kb_id=kb_id,
            org_id=org_id,
            title=filename,
            filename=filename,
            mime_type=mime_type,
            status=DOC_STATUS_DRAFT,
            uploaded_by=current_user.id,
        )
        db.add(document)
        await db.flush()

        storage_key = f"docs/{kb_id}/{uuid.uuid4().hex}_{filename}"
        await storage.put(storage_key, entry_data)

        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            storage_key=storage_key,
            filename=filename,
            mime_type=mime_type,
            checksum=checksum(entry_data),
            size_bytes=len(entry_data),
        )
        db.add(version)
        await db.flush()

        background_tasks.add_task(run_processing_job_background, version.id)
        await create_processing_job(db, document.id, version.id)

        await write_audit(
            db,
            action="document.upload",
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            org_id=org_id,
            resource_type="document",
            resource_id=document.id,
            request=request,
            after={
                "filename": filename,
                "kb_id": str(kb_id),
                "version": 1,
                "storage_key": storage_key,
                "bulk": True,
            },
        )

        created.append(document)

    zf.close()
    await db.commit()
    return [await _document_read_model(db, doc) for doc in created]


async def _document_read_model(db: AsyncSession, document: Document) -> DocumentRead:
    """DocumentRead enriched with chunk_count + latest version error."""
    chunk_count = (
        await db.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.version_number == document.version_number,
            )
        )
    ).scalar_one()
    latest = (
        await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    payload = DocumentRead.model_validate(document)
    payload.chunk_count = chunk_count
    payload.error_message = latest.error_message if latest else None
    return payload


@router.get(f"{DOC_PREFIX}/{{document_id}}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    db: DbSession,
    current_user: User = Depends(require_permission(DOCUMENT_READ)),
) -> DocumentRead:
    document = await db.get(Document, document_id)
    if document is None:
        raise not_found("Document not found")
    await _get_visible_kb(db, current_user, document.kb_id)
    return await _document_read_model(db, document)


@router.patch(f"{DOC_PREFIX}/{{document_id}}", response_model=DocumentRead)
async def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(DOCUMENT_WRITE)),
) -> Document:
    document = await db.get(Document, document_id)
    if document is None:
        raise not_found("Document not found")
    await _get_visible_kb(db, current_user, document.kb_id, for_write=True)
    data = payload.model_dump(exclude_unset=True)
    if "is_approved" in data and data["is_approved"] and not document.is_approved:
        from datetime import datetime

        document.approved_at = datetime.now(UTC)
        document.approved_by = current_user.id
    for field, value in data.items():
        if value is not None and field not in ("approved_at", "approved_by"):
            setattr(document, field, value)
    await write_audit(
        db,
        action="document.update",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=document.org_id,
        resource_type="document",
        resource_id=document.id,
        request=request,
        after=data,
    )
    await db.commit()
    await db.refresh(document)
    return DocumentRead.model_validate(document)


@router.post(f"{DOC_PREFIX}/{{document_id}}/reindex", response_model=DocumentRead)
async def reindex_document(
    document_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
    process_sync: bool = Query(default=False),
    current_user: User = Depends(require_permission(DOCUMENT_WRITE)),
) -> Document:
    document = await db.get(Document, document_id)
    if document is None:
        raise not_found("Document not found")
    await _get_visible_kb(db, current_user, document.kb_id, for_write=True)
    latest = (
        await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is None:
        raise bad_request("Document has no version to re-index")
    if process_sync:
        await process_document_version(db, latest.id)
    else:
        await create_processing_job(db, document.id, latest.id)
        background_tasks.add_task(run_processing_job_background, latest.id)
    await write_audit(
        db,
        action="document.reindex",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=document.org_id,
        resource_type="document",
        resource_id=document.id,
        request=request,
        after={"version": latest.version_number},
    )
    await db.commit()
    return DocumentRead.model_validate(document)


@router.get(f"{DOC_PREFIX}/{{document_id}}/versions", response_model=list[DocumentVersionRead])
async def list_document_versions(
    document_id: uuid.UUID,
    db: DbSession,
    current_user: User = Depends(require_permission(DOCUMENT_READ)),
) -> list[DocumentVersion]:
    document = await db.get(Document, document_id)
    if document is None:
        raise not_found("Document not found")
    await _get_visible_kb(db, current_user, document.kb_id)
    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    return list(result.scalars().all())


@router.get(f"{DOC_PREFIX}/{{document_id}}/chunks", response_model=list[DocumentChunkRead])
async def list_document_chunks(
    document_id: uuid.UUID,
    db: DbSession,
    current_user: User = Depends(require_permission(DOCUMENT_READ)),
) -> list[DocumentChunk]:
    document = await db.get(Document, document_id)
    if document is None:
        raise not_found("Document not found")
    await _get_visible_kb(db, current_user, document.kb_id)
    result = await db.execute(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.version_number == document.version_number,
        )
        .order_by(DocumentChunk.chunk_index)
        .limit(1000)
    )
    return list(result.scalars().all())


# ──────────────────────────── Group permissions ────────────────────────────


@router.get(
    f"{KB_PREFIX}/{{kb_id}}/groups",
    response_model=list[KbGroupPermissionRead],
)
async def list_kb_group_permissions(
    kb_id: uuid.UUID,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_WRITE)),
) -> list[KnowledgeBaseGroupPermission]:
    await _get_visible_kb(db, current_user, kb_id)
    result = await db.execute(
        select(KnowledgeBaseGroupPermission).where(
            KnowledgeBaseGroupPermission.knowledge_base_id == kb_id
        )
    )
    return list(result.scalars().all())


@router.post(
    f"{KB_PREFIX}/{{kb_id}}/groups",
    response_model=KbGroupPermissionRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_kb_group_permission(
    kb_id: uuid.UUID,
    payload: KbGroupPermissionRequest,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_WRITE)),
) -> KnowledgeBaseGroupPermission:
    kb = await _get_visible_kb(db, current_user, kb_id, for_write=True)
    from app.models.rbac import Group

    group = await db.get(Group, payload.group_id)
    if group is None:
        raise not_found("Group not found")
    if group.org_id is not None and kb.org_id is not None and group.org_id != kb.org_id:
        raise forbidden("Group does not belong to the same organisation")

    perm = KnowledgeBaseGroupPermission(
        knowledge_base_id=kb_id,
        group_id=payload.group_id,
        permission_level=payload.permission_level,
    )
    db.add(perm)
    try:
        await db.flush()
    except Exception as exc:
        raise bad_request(
            "This group already has a permission assigned to this knowledge base"
        ) from exc
    await write_audit(
        db,
        action="kb_group_permission.add",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=kb.org_id,
        resource_type="knowledge_base_group_permission",
        resource_id=kb_id,
        request=request,
        after={
            "group_id": str(payload.group_id),
            "permission_level": payload.permission_level,
        },
    )
    await db.commit()
    return perm


@router.delete(
    f"{KB_PREFIX}/{{kb_id}}/groups/{{group_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_kb_group_permission(
    kb_id: uuid.UUID,
    group_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: User = Depends(require_permission(KB_WRITE)),
) -> None:
    kb = await _get_visible_kb(db, current_user, kb_id, for_write=True)
    result = await db.execute(
        select(KnowledgeBaseGroupPermission).where(
            KnowledgeBaseGroupPermission.knowledge_base_id == kb_id,
            KnowledgeBaseGroupPermission.group_id == group_id,
        )
    )
    perm = result.scalar_one_or_none()
    if perm is None:
        raise not_found("Group permission not found")
    await db.delete(perm)
    await write_audit(
        db,
        action="kb_group_permission.remove",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=kb.org_id,
        resource_type="knowledge_base_group_permission",
        resource_id=kb_id,
        request=request,
        after={"group_id": str(group_id)},
    )
    await db.commit()
