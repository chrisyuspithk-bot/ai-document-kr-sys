"""Organizations (multi-tenant service units)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

ORG_TYPE_ROOT = "root"
ORG_TYPE_SERVICE_UNIT = "service_unit"


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    org_type: Mapped[str] = mapped_column(String(32), nullable=False, default=ORG_TYPE_SERVICE_UNIT)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
