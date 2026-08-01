"""Chat and conversation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    kb_ids: list[uuid.UUID] = Field(default_factory=list)
    conversation_id: uuid.UUID | None = None
    model: str = Field(default="deepseek-v4-flash")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=32768)
    top_k: int = Field(default=8, ge=1, le=50)
    similarity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    format: str = Field(default="default")


class ChatCitation(BaseModel):
    document_id: str
    document_title: str
    chunk_index: int
    page_number: int | None = None
    snippet: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    conversation_id: uuid.UUID
    citations: list[ChatCitation] = Field(default_factory=list)
    model: str = ""
    usage: dict[str, Any] | None = None


class MessageRead(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: dict | None = None
    model: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationRead(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
