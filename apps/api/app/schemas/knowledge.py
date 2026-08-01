"""Knowledge base / document / retrieval schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# --- Knowledge bases ---


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    org_id: uuid.UUID | None = None
    is_active: bool = True


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID | None
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- Documents ---


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kb_id: uuid.UUID
    org_id: uuid.UUID
    title: str
    filename: str
    mime_type: str
    status: str
    version_number: int
    is_approved: bool
    effective_date: datetime | None
    approved_at: datetime | None
    chunk_count: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None
    is_approved: bool | None = None
    effective_date: datetime | None = None


class DocumentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    filename: str
    mime_type: str
    checksum: str
    size_bytes: int
    status: str
    error_message: str | None
    chunk_count: int
    created_at: datetime


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    chunk_index: int
    content: str
    # SQLAlchemy reserves `metadata` on the class (its MetaData object), so the
    # ORM attribute is `metadata_`. Validation reads that attribute; the API/JSON
    # field name stays `metadata`.
    metadata_: dict = Field(
        default_factory=dict,
        validation_alias="metadata_",
        serialization_alias="metadata",
    )


# --- Retrieval ---


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    kb_ids: list[uuid.UUID] | None = None
    top_k: int = Field(default=10, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class RetrievalResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    kb_id: uuid.UUID
    document_title: str
    content: str
    page: int | None
    score: float
    vector_score: float | None
    keyword_score: float | None


class KbGroupPermissionRequest(BaseModel):
    group_id: uuid.UUID
    permission_level: str = "read"


class KbGroupPermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    knowledge_base_id: uuid.UUID
    group_id: uuid.UUID
    permission_level: str
