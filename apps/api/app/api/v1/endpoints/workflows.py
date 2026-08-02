"""Workflow automation endpoints: definitions, approval queue, execution history."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, not_found
from app.models.user import User
from app.models.workflow import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    WF_RUN_COMPLETED,
    WF_RUN_PENDING,
    WF_RUN_RUNNING,
    WF_RUN_WAITING_APPROVAL,
    WF_STATUS_ACTIVE,
    ApprovalStep,
    WorkflowDefinition,
    WorkflowRun,
)
from app.schemas.workflow import (
    ApprovalDecision,
    ApprovalStepRead,
    WorkflowCreate,
    WorkflowListItem,
    WorkflowRead,
    WorkflowRunListItem,
    WorkflowRunRead,
    WorkflowTriggerRequest,
    WorkflowUpdate,
)
from app.services.audit_service import write_audit
from app.services.permissions import WORKFLOW_MANAGE

router = APIRouter(prefix="/workflows", tags=["workflows"])
logger = logging.getLogger(__name__)


# ── Workflow Definitions CRUD ─────────────────────────────────────────

@router.get("", response_model=list[WorkflowListItem])
async def list_workflows(
    status: str | None = Query(None),
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    stmt = select(WorkflowDefinition).where(WorkflowDefinition.org_id == current_user.org_id)
    if status:
        stmt = stmt.where(WorkflowDefinition.status == status)
    stmt = stmt.order_by(WorkflowDefinition.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=WorkflowRead, status_code=201)
async def create_workflow(
    payload: WorkflowCreate,
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    steps_json = [s.model_dump() for s in payload.steps]
    wf = WorkflowDefinition(
        org_id=current_user.org_id,
        name=payload.name,
        description=payload.description,
        trigger_type=payload.trigger_type,
        steps=steps_json,
        dify_workflow_id=payload.dify_workflow_id,
        version=1,
        created_by=current_user.id,
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    await write_audit(db, action="workflow.created", actor_user_id=current_user.id, resource_id=str(wf.id))
    return wf


# ── Run History (static routes before parameterized) ───────────────────

@router.get("/runs", response_model=list[WorkflowRunListItem])
async def list_runs(
    workflow_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    stmt = (
        select(WorkflowRun)
        .where(WorkflowRun.org_id == current_user.org_id)
        .order_by(WorkflowRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if workflow_id:
        stmt = stmt.where(WorkflowRun.workflow_id == uuid.UUID(workflow_id))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/runs/{run_id}", response_model=WorkflowRunRead)
async def get_run(
    run_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    run = await _load_run(db, run_id)
    if run.org_id != current_user.org_id:
        raise not_found("Workflow run not found")
    return run


# ── Approval Queue & Actions (static before parameterized) ─────────────

@router.get("/approvals/pending", response_model=list[ApprovalStepRead])
async def my_pending_approvals(
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    result = await db.execute(
        select(ApprovalStep)
        .where(
            ApprovalStep.org_id == current_user.org_id,
            ApprovalStep.approver_id == current_user.id,
            ApprovalStep.status == APPROVAL_PENDING,
        )
        .order_by(ApprovalStep.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/approvals/all", response_model=list[ApprovalStepRead])
async def all_pending_approvals(
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    result = await db.execute(
        select(ApprovalStep)
        .where(
            ApprovalStep.org_id == current_user.org_id,
            ApprovalStep.status == APPROVAL_PENDING,
        )
        .order_by(ApprovalStep.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/approvals/{step_id}/approve", response_model=ApprovalStepRead)
async def approve_step(
    step_id: uuid.UUID,
    payload: ApprovalDecision | None = None,
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    return await _decide_step(db, step_id, current_user, APPROVAL_APPROVED, (payload.comment if payload else None))


@router.post("/approvals/{step_id}/reject", response_model=ApprovalStepRead)
async def reject_step(
    step_id: uuid.UUID,
    payload: ApprovalDecision | None = None,
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    return await _decide_step(db, step_id, current_user, APPROVAL_REJECTED, (payload.comment if payload else None))


# ── Dify Integration ──────────────────────────────────────────────────

@router.post("/dify/callback/{workflow_id}")
async def dify_callback(
    workflow_id: uuid.UUID,
    db: DbSession = None,
):
    wf_result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
    )
    wf = wf_result.scalar_one_or_none()
    if not wf:
        raise not_found("Workflow not found")

    run = WorkflowRun(
        workflow_id=wf.id,
        org_id=wf.org_id,
        status=WF_RUN_COMPLETED,
        trigger_type="api",
        current_step=len(wf.steps),
        completed_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    await write_audit(
        db,
        action="workflow.dify_callback",
        actor_user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        resource_id=str(run.id),
    )
    return {"status": "ok", "run_id": str(run.id)}


# ── Workflow Detail CRUD (parameterized routes AFTER static ones) ──────

@router.get("/{workflow_id}", response_model=WorkflowRead)
async def get_workflow(
    workflow_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    return await _get_workflow(db, workflow_id, current_user.org_id)


@router.patch("/{workflow_id}", response_model=WorkflowRead)
async def update_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowUpdate,
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    wf = await _get_workflow(db, workflow_id, current_user.org_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "steps" in update_data:
        update_data["steps"] = [s.model_dump() if hasattr(s, "model_dump") else s for s in update_data["steps"]]
        wf.version += 1

    for key, val in update_data.items():
        setattr(wf, key, val)

    await db.commit()
    await db.refresh(wf)
    await write_audit(db, action="workflow.updated", actor_user_id=current_user.id, resource_id=str(wf.id))
    return wf


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    wf = await _get_workflow(db, workflow_id, current_user.org_id)
    await db.delete(wf)
    await db.commit()
    await write_audit(db, action="workflow.deleted", actor_user_id=current_user.id, resource_id=str(workflow_id))


# ── Workflow Execution ────────────────────────────────────────────────

@router.post("/{workflow_id}/trigger", response_model=WorkflowRunRead, status_code=201)
async def trigger_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowTriggerRequest | None = None,
    db: DbSession = None,
    current_user: User = Depends(require_permission(WORKFLOW_MANAGE)),
):
    wf = await _get_workflow(db, workflow_id, current_user.org_id)
    if wf.status != WF_STATUS_ACTIVE:
        raise bad_request("Only active workflows can be triggered")

    trigger_type = payload.trigger_type if payload else "manual"
    trigger_context = payload.trigger_context if payload else None

    run = WorkflowRun(
        workflow_id=wf.id,
        org_id=current_user.org_id,
        status=WF_RUN_RUNNING,
        trigger_type=trigger_type,
        trigger_context=trigger_context,
        current_step=0,
        created_by=current_user.id,
    )
    db.add(run)
    await db.flush()

    for step_def in wf.steps:
        approval = ApprovalStep(
            run_id=run.id,
            org_id=current_user.org_id,
            step_order=step_def.get("step_order", 0),
            approver_id=step_def.get("approver_user_id"),
            status=APPROVAL_PENDING,
        )
        db.add(approval)

    if wf.steps:
        run.status = WF_RUN_WAITING_APPROVAL
        run.current_step = 0
    else:
        run.status = WF_RUN_COMPLETED
        run.completed_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(run)

    await write_audit(
        db,
        action="workflow.triggered",
        actor_user_id=current_user.id,
        resource_id=str(run.id),
    )
    return await _load_run(db, run.id)


# ── Helpers ───────────────────────────────────────────────────────────

async def _get_workflow(db, workflow_id: uuid.UUID, org_id: uuid.UUID) -> WorkflowDefinition:
    result = await db.execute(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == workflow_id, WorkflowDefinition.org_id == org_id
        )
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise not_found("Workflow not found")
    return wf


async def _load_run(db, run_id: uuid.UUID) -> WorkflowRun:
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id)
        .options(selectinload(WorkflowRun.approvals))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise not_found("Workflow run not found")
    return run


async def _decide_step(
    db, step_id: uuid.UUID, current_user: User, decision: str, comment: str | None
) -> ApprovalStep:
    result = await db.execute(
        select(ApprovalStep).where(
            ApprovalStep.id == step_id,
            ApprovalStep.org_id == current_user.org_id,
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        raise not_found("Approval step not found")
    if step.status != APPROVAL_PENDING:
        raise bad_request("This step has already been decided")

    step.status = decision
    step.comment = comment
    step.decided_at = datetime.now(UTC)

    run_result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.id == step.run_id)
        .options(selectinload(WorkflowRun.approvals))
    )
    run = run_result.scalar_one()

    if decision == APPROVAL_REJECTED:
        run.status = "rejected"
        run.completed_at = datetime.now(UTC)
    else:
        all_decided = all(a.status != APPROVAL_PENDING for a in run.approvals)
        if all_decided:
            run.status = WF_RUN_COMPLETED
            run.completed_at = datetime.now(UTC)
        else:
            run.current_step = min(
                a.step_order for a in run.approvals if a.status == APPROVAL_PENDING
            )

    await db.commit()
    await db.refresh(step)

    await write_audit(
        db,
        action=f"approval.{decision}",
        actor_user_id=current_user.id,
        resource_id=str(step_id),
    )
    return step
