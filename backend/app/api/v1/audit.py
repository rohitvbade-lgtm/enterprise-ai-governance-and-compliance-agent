"""
Audit events and report endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_dependency
from backend.app.models.audit import AuditEvent
from backend.app.models.assessment import GovernanceAssessment, Finding
from backend.app.models.risk import RiskAssessment
from backend.app.models.approval import ApprovalRequest
from backend.app.models.exception_model import PolicyException
from backend.app.schemas.audit import AuditEventResponse, AuditReportRequest, AuditReportResponse

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_dependency)]


@router.get("/events", response_model=list[AuditEventResponse])
async def list_audit_events(
    db: DbSession,
    application_id: uuid.UUID | None = None,
    assessment_id: uuid.UUID | None = None,
    event_type: str | None = None,
    limit: int = 100,
) -> list[AuditEventResponse]:
    """List audit events with optional filters."""
    query = (
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .limit(min(limit, 500))
    )
    if application_id:
        query = query.where(AuditEvent.application_id == application_id)
    if assessment_id:
        query = query.where(AuditEvent.assessment_id == assessment_id)
    if event_type:
        query = query.where(AuditEvent.event_type == event_type.upper())

    result = await db.execute(query)
    return [AuditEventResponse.model_validate(e) for e in result.scalars().all()]


@router.post("/reports", response_model=AuditReportResponse)
async def generate_audit_report(body: AuditReportRequest, db: DbSession) -> AuditReportResponse:
    """
    Generate a structured governance audit report for an assessment.

    Report facts come from the database — an LLM may add a summary,
    but underlying data is authoritative and not LLM-generated.
    """
    # Load assessment
    result = await db.execute(
        select(GovernanceAssessment).where(GovernanceAssessment.id == body.assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Load application name
    from backend.app.models.ai_application import AIApplication
    app_result = await db.execute(
        select(AIApplication).where(AIApplication.id == assessment.application_id)
    )
    app = app_result.scalar_one_or_none()

    # Load findings
    findings_result = await db.execute(
        select(Finding).where(Finding.assessment_id == body.assessment_id)
    )
    findings = findings_result.scalars().all()

    # Load risk assessment
    risk_result = await db.execute(
        select(RiskAssessment).where(RiskAssessment.assessment_id == body.assessment_id)
    )
    risk = risk_result.scalar_one_or_none()

    # Load approvals
    approval_result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.assessment_id == body.assessment_id)
    )
    approvals = approval_result.scalars().all()

    # Load audit events for this assessment
    audit_result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.assessment_id == body.assessment_id)
        .order_by(AuditEvent.created_at)
    )
    audit_events = audit_result.scalars().all()

    # Aggregate findings
    findings_by_type: dict[str, int] = {}
    findings_by_severity: dict[str, int] = {}
    policies_evaluated: list[str] = []

    for f in findings:
        findings_by_type[f.finding_type] = findings_by_type.get(f.finding_type, 0) + 1
        findings_by_severity[f.severity] = findings_by_severity.get(f.severity, 0) + 1
        if f.policy_code and f.policy_code not in policies_evaluated:
            policies_evaluated.append(f.policy_code)

    applied_exceptions = []

    exceptions_result = await db.execute(
        select(PolicyException)
        .where(PolicyException.application_id == assessment.application_id)
        .where(PolicyException.status == "ACTIVE")
    )
    active_exceptions = [
        e for e in exceptions_result.scalars().all() 
        if e.expires_at > datetime.now(timezone.utc)
    ]
    
    for exc in active_exceptions:
        # We assume exception applies if the policy was evaluated/violated
        # (or we could fetch the policy code, but for now we just list active ones)
        applied_exceptions.append({
            "id": str(exc.id),
            "policy_id": str(exc.policy_id),
            "reason": exc.reason,
            "expires_at": exc.expires_at.isoformat(),
        })

    return AuditReportResponse(
        assessment_id=body.assessment_id,
        application_name=app.name if app else "Unknown",
        generated_at=datetime.now(timezone.utc),
        decision=assessment.decision or "UNKNOWN",
        risk_score=assessment.overall_risk_score or 0.0,
        risk_level=assessment.risk_level or "UNKNOWN",
        risk_factors={
            "data_risk": risk.data_risk if risk else 0.0,
            "security_risk": risk.security_risk if risk else 0.0,
            "compliance_risk": risk.compliance_risk if risk else 0.0,
            "model_risk": risk.model_risk if risk else 0.0,
            "business_impact": risk.business_impact if risk else 0.0,
        },
        total_findings=len(findings),
        findings_by_type=findings_by_type,
        findings_by_severity=findings_by_severity,
        findings=[
            {
                "id": str(f.id),
                "type": f.finding_type,
                "severity": f.severity,
                "description": f.description,
                "policy_code": f.policy_code,
                "confidence": f.confidence,
                "source": f.source,
            }
            for f in findings
        ],
        policies_evaluated=policies_evaluated,
        exceptions_applied=applied_exceptions,
        approval_history=[
            {
                "id": str(a.id),
                "status": a.status,
                "decision": a.decision,
                "requested_by": a.requested_by,
                "assigned_to": a.assigned_to,
                "comments": a.comments,
                "created_at": a.created_at.isoformat(),
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            }
            for a in approvals
        ],
        audit_events=[
            {
                "event_type": e.event_type,
                "actor": e.actor,
                "summary": e.summary,
                "created_at": e.created_at.isoformat(),
            }
            for e in audit_events
        ],
    )

