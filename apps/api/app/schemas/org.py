"""Organization schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.organization import ORG_TYPE_SERVICE_UNIT


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    org_type: str = Field(default=ORG_TYPE_SERVICE_UNIT, max_length=32)
    parent_id: uuid.UUID | None = None


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=16)


class OrgRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    org_type: str
    parent_id: uuid.UUID | None
    status: str
    created_at: datetime
