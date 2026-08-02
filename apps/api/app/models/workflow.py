"""Workflow automation models: definitions, approval steps, execution history."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# Workflow status constants
WF_STATUS_ACTIVE = "active"
WF_STATUS_DRAFT = "draft"
WF_STATUS_ARCHIVED = "archived"

# Workflow run status
WF_RUN_PENDING = "pending"
WF_RUN_RUNNING = "running"
WF_RUN_WAITING_APPROVAL = "waiting_approval"
WF_RUN_COMPLETED = "completed"
WF_RUN_FAILED = "failed"
WF_RUN_CANCELLED = "cancelled"

# Approval step status
APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"

# Trigger types
TRIGGER_DOCUMENT_UPLOAD = "document.upload"
TRIGGER_DOCUMENT_GENERATED = "document.generated"
TRIGGER_SCHEDULE = "schedule"
TRIGGER_API = "api"
TRIGGER_MANUAL = "manual"


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=WF_STATUS_DRAFT)
    trigger_type: Mapped[str] = mapped_column(String(50), default=TRIGGER_MANUAL)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    dify_workflow_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    runs: Mapped[list[WorkflowRun]] = relationship(
        "WorkflowRun", back_populates="workflow", order_by="WorkflowRun.created_at.desc()"
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default=WF_RUN_PENDING)
    trigger_type: Mapped[str] = mapped_column(String(50), default=TRIGGER_MANUAL)
    trigger_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow: Mapped[WorkflowDefinition] = relationship("WorkflowDefinition", back_populates="runs")
    approvals: Mapped[list[ApprovalStep]] = relationship(
        "ApprovalStep", back_populates="run", order_by="ApprovalStep.step_order"
    )


class ApprovalStep(Base):
    __tablename__ = "approval_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    step_order: Mapped[int] = mapped_column(Integer, default=0)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=APPROVAL_PENDING)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    run: Mapped[WorkflowRun] = relationship("WorkflowRun", back_populates="approvals")
