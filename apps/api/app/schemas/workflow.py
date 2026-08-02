"""Pydantic schemas for workflow automation."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowStepDef(BaseModel):
    """A single step in a workflow definition."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    step_order: int = 0
    approver_role: str | None = None  # role name
    approver_user_id: uuid.UUID | None = None
    action: str = "approve"  # "approve" | "review" | "notify" | "auto"
    config: dict | None = None


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    trigger_type: str = Field("manual", pattern="^(document\\.upload|document\\.generated|schedule|api|manual)$")
    steps: list[WorkflowStepDef] = Field(default_factory=list)
    dify_workflow_id: str | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    status: str | None = Field(None, pattern="^(active|draft|archived)$")
    trigger_type: str | None = Field(None, pattern="^(document\\.upload|document\\.generated|schedule|api|manual)$")
    steps: list[WorkflowStepDef] | None = None
    dify_workflow_id: str | None = None


class ApprovalStepRead(BaseModel):
    id: uuid.UUID
    step_order: int
    approver_id: uuid.UUID | None
    status: str
    comment: str | None
    decided_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunRead(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    trigger_type: str
    trigger_context: dict | None
    current_step: int
    created_by: uuid.UUID | None
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    approvals: list[ApprovalStepRead] = []

    model_config = {"from_attributes": True}


class WorkflowRunListItem(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    trigger_type: str
    current_step: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class WorkflowRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: str | None
    status: str
    trigger_type: str
    steps: list
    dify_workflow_id: str | None
    version: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    trigger_type: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    comment: str | None = None


class WorkflowTriggerRequest(BaseModel):
    trigger_type: str = "manual"
    trigger_context: dict | None = None
