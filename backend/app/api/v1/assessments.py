"""
Assessment retrieval endpoints.
The actual governance evaluation is in governance.py (POST /governance/evaluate).
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_dependency
from backend.app.models.assessment import GovernanceAssessment, Finding
from backend.app.schemas.assessment import AssessmentResponse
from backend.app.schemas.finding import FindingResponse

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_dependency)]


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(assessment_id: uuid.UUID, db: DbSession) -> AssessmentResponse:
    """Get a governance assessment by ID."""
    result = await db.execute(
        select(GovernanceAssessment).where(GovernanceAssessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return AssessmentResponse.model_validate(assessment)


@router.get("/{assessment_id}/findings", response_model=list[FindingResponse])
async def get_assessment_findings(assessment_id: uuid.UUID, db: DbSession) -> list[FindingResponse]:
    """Get all findings for a governance assessment."""
    result = await db.execute(
        select(Finding)
        .where(Finding.assessment_id == assessment_id)
        .order_by(Finding.created_at)
    )
    findings = result.scalars().all()
    return [FindingResponse.model_validate(f) for f in findings]


@router.get("", response_model=list[AssessmentResponse])
async def list_assessments(
    db: DbSession,
    application_id: uuid.UUID | None = None,
) -> list[AssessmentResponse]:
    """List assessments, optionally filtered by application."""
    query = select(GovernanceAssessment).order_by(GovernanceAssessment.created_at.desc())
    if application_id:
        query = query.where(GovernanceAssessment.application_id == application_id)
    result = await db.execute(query)
    return [AssessmentResponse.model_validate(a) for a in result.scalars().all()]

