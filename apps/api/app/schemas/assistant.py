"""Pydantic schemas for AI assistant CRUD and versioning."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AssistantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    system_prompt: str = Field("", max_length=10000)
    model: str = Field("deepseek-v4-flash", max_length=100)
    kb_ids: list[uuid.UUID] | None = None
    tools: list[str] | None = None
    mode: str = Field("internal", pattern="^(internal|web)$")
    is_active: bool = True


class AssistantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    system_prompt: str | None = Field(None, max_length=10000)
    model: str | None = Field(None, max_length=100)
    kb_ids: list[uuid.UUID] | None = None
    tools: list[str] | None = None
    mode: str | None = Field(None, pattern="^(internal|web)$")
    is_active: bool | None = None


class AssistantVersionRead(BaseModel):
    id: uuid.UUID
    version: int
    system_prompt: str
    model: str
    kb_ids: list | None
    tools: list | None
    mode: str
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class AssistantRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str
    model: str
    kb_ids: list | None
    tools: list | None
    mode: str
    is_active: bool
    version: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssistantListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    model: str
    mode: str
    is_active: bool
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}
