"""Integration API key schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., min_length=1, max_length=200)
    permissions: list[str] | None = None
    expires_at: datetime | None = None


class ApiKeyRead(BaseModel):
    """Public representation of an API key (never includes the raw key)."""

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    permissions: list[str] | None
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(BaseModel):
    """Response after creating an API key — includes the raw key ONCE."""

    id: uuid.UUID
    name: str
    key_prefix: str
    raw_key: str
    is_active: bool
    permissions: list[str] | None
    expires_at: datetime | None
    created_at: datetime
    message: str = "Store this key securely. It will not be shown again."
