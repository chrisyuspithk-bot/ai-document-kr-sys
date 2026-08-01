"""User, role, permission and group schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# --- Users -------------------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.\-]+$")
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    org_id: uuid.UUID | None = None
    locale: str = Field(default="zh-Hant", max_length=16)
    role_names: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    locale: str | None = Field(default=None, max_length=16)
    org_id: uuid.UUID | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID | None
    email: str
    username: str
    full_name: str
    locale: str
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None
    created_at: datetime


# --- Roles / permissions -------------------------------------------------------


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    description: str | None


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    is_system: bool
    permission_codes: list[str] = Field(default_factory=list)


class RoleAssignRequest(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID
    org_id: uuid.UUID | None = None  # None = global scope


class RoleRevokeRequest(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID
    org_id: uuid.UUID | None = None


# --- Groups -------------------------------------------------------------------


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=255)
    org_id: uuid.UUID | None = None


class GroupMemberRequest(BaseModel):
    user_id: uuid.UUID


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID | None
    name: str
    description: str | None
    member_count: int = 0
    created_at: datetime
