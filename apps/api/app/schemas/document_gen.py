"""Document generation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

#  ---------------------------------------------------------------------------
#  Template schemas
#  ---------------------------------------------------------------------------


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    category: str = Field(default="general")
    content: str = Field(default="")  # jinja2 template
    variables: dict[str, str] | None = None
    style_config: dict[str, Any] | None = None


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = None
    category: str | None = None
    content: str | None = None
    variables: dict[str, str] | None = None
    style_config: dict[str, Any] | None = None
    is_active: bool | None = None


class TemplateRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    category: str
    content: str
    variables: dict | None
    style_config: dict | None
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListItem(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


#  ---------------------------------------------------------------------------
#  Generation & approval schemas
#  ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    template_id: uuid.UUID | None = None
    title: str = Field(default="", max_length=500)
    prompt: str = Field(..., min_length=1, max_length=20000)
    fill_values: dict[str, str] | None = None  # template variable values
    source_kb_ids: list[uuid.UUID] = Field(default_factory=list)
    model: str = Field(default="deepseek-v4-flash")
    format: str = Field(default="formal")


class GenerateResponse(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    status: str
    model: str | None
    usage: dict[str, Any] | None
    created_at: datetime


class ReviseRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=20000)


class SubmitRequest(BaseModel):
    pass  # submit for approval


class ReviewRequest(BaseModel):
    comment: str | None = None


class DocumentRead(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID | None
    title: str
    status: str
    content: str
    prompt: str
    fill_values: dict | None
    source_kb_ids: list | None
    model: str | None
    usage: dict | None
    version: int
    docx_path: str | None
    pdf_path: str | None
    reviewed_by: uuid.UUID | None
    review_comment: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    template_id: uuid.UUID | None
    model: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
