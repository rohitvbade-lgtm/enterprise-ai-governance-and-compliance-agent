"""
Approval and Policy Exception endpoints.

POST /approvals/{id}/approve  — human approves a review request
POST /approvals/{id}/reject   — human rejects a review request
GET  /approvals               — list open approvals
POST /exceptions              — create a policy exception
GET  /exceptions              — list exceptions
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_dependency
from backend.app.models.approval import ApprovalRequest
from backend.app.models.exception_model import PolicyException
from backend.app.models.audit import AuditEvent
from backend.app.schemas.approval import (
    ApprovalDecision,
    ApprovalResponse,
    ExceptionCreate,
    ExceptionResponse,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_dependency)]


# ── Approvals ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(
    db: DbSession,
    status: str | None = None,
) -> list[ApprovalResponse]:
    """List approval requests. Filter by status (PENDING, APPROVED, REJECTED, EXPIRED)."""
    query = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status:
        query = query.where(ApprovalRequest.status == status.upper())
    result = await db.execute(query)
    return [ApprovalResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(approval_id: uuid.UUID, db: DbSession) -> ApprovalResponse:
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return ApprovalResponse.model_validate(approval)


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: uuid.UUID, body: ApprovalDecision, db: DbSession
) -> ApprovalResponse:
    """Human approves an approval request."""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Request is already {approval.status}")

    approval.status = "APPROVED"
    approval.decision = "APPROVED"
    approval.comments = body.comments
    approval.assigned_to = body.reviewer
    approval.resolved_at = datetime.now(timezone.utc)

    audit = AuditEvent(
        event_type="APPROVAL_GRANTED",
        assessment_id=approval.assessment_id,
        actor=body.reviewer,
        details={"approval_id": str(approval_id), "comments": body.comments},
        summary=f"Approval granted by {body.reviewer}",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(approval)
    return ApprovalResponse.model_validate(approval)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    approval_id: uuid.UUID, body: ApprovalDecision, db: DbSession
) -> ApprovalResponse:
    """Human rejects an approval request."""
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Request is already {approval.status}")

    approval.status = "REJECTED"
    approval.decision = "REJECTED"
    approval.comments = body.comments
    approval.assigned_to = body.reviewer
    approval.resolved_at = datetime.now(timezone.utc)

    audit = AuditEvent(
        event_type="APPROVAL_REJECTED",
        assessment_id=approval.assessment_id,
        actor=body.reviewer,
        details={"approval_id": str(approval_id), "comments": body.comments},
        summary=f"Approval rejected by {body.reviewer}",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(approval)
    return ApprovalResponse.model_validate(approval)


# ── Policy Exceptions ─────────────────────────────────────────────────────────

@router.post("/exceptions", response_model=ExceptionResponse, status_code=201)
async def create_exception(body: ExceptionCreate, db: DbSession) -> ExceptionResponse:
    """Create a time-bound policy exception. Requires named approver and expiration."""
    exc = PolicyException(**body.model_dump())
    db.add(exc)

    audit = AuditEvent(
        event_type="EXCEPTION_CREATED",
        application_id=body.application_id,
        actor=body.approved_by,
        details={
            "policy_id": str(body.policy_id),
            "reason": body.reason[:200],
            "expires_at": body.expires_at.isoformat(),
        },
        summary=f"Policy exception created by {body.approved_by}",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(exc)
    return ExceptionResponse.model_validate(exc)


@router.get("/exceptions", response_model=list[ExceptionResponse])
async def list_exceptions(
    db: DbSession,
    application_id: uuid.UUID | None = None,
    active_only: bool = False,
) -> list[ExceptionResponse]:
    """List policy exceptions. Filter by application or active status."""
    query = select(PolicyException).order_by(PolicyException.created_at.desc())
    if application_id:
        query = query.where(PolicyException.application_id == application_id)
    if active_only:
        query = query.where(PolicyException.status == "ACTIVE")
    result = await db.execute(query)
    exceptions = result.scalars().all()
    return [ExceptionResponse.model_validate(e) for e in exceptions]

