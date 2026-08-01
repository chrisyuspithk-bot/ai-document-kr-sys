"""Document generation models: templates and generated documents."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

DOCGEN_STATUS_DRAFT = "draft"
DOCGEN_STATUS_SUBMITTED = "submitted"
DOCGEN_STATUS_APPROVED = "approved"
DOCGEN_STATUS_REJECTED = "rejected"


class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        String(100), default="general"
    )  # proposal, report, minutes, memo, service_plan
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text, default="")  # jinja2 template with placeholders
    variables: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # {"var_name": "description"}
    style_config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # font, margins, header/footer
    version: Mapped[int] = mapped_column(default=1)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    documents: Mapped[list[GeneratedDocument]] = relationship(
        "GeneratedDocument", back_populates="template"
    )


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(
        String(30), default=DOCGEN_STATUS_DRAFT
    )  # draft, submitted, approved, rejected
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")  # final generated markdown
    prompt: Mapped[str] = mapped_column(Text, default="")  # user instructions
    fill_values: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # template variable values
    source_kb_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)  # KBs used as context
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(default=1)
    docx_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    template: Mapped[DocumentTemplate | None] = relationship(
        "DocumentTemplate", back_populates="documents"
    )
