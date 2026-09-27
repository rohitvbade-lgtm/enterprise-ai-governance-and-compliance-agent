"""
Assessment retrieval endpoints.
The actual governance audits are triggered from:
  POST /governance/evaluate/input  — audit a user prompt
  POST /governance/evaluate/output — audit an AI response
These read-only endpoints let you fetch assessment records and their findings.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
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

@router.get("/{input_assessment_id}/linked", response_model=list[AssessmentResponse])
async def get_linked_output_assessments(
    input_assessment_id: uuid.UUID,
    db: DbSession,
) -> list[AssessmentResponse]:
    """
    Get all OUTPUT assessments that were linked to a given INPUT assessment.
    Use this to view the full interaction trace in the dashboard:
    given an input assessment ID, retrieve every output assessment that
    references it via input_assessment_id.
    Returns an empty list if the input assessment has no linked output assessments.
    """
    # First verify the input assessment actually exists
    input_check = await db.execute(
        select(GovernanceAssessment).where(GovernanceAssessment.id == input_assessment_id)
    )
    if input_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Input assessment not found")
    result = await db.execute(
        select(GovernanceAssessment)
        .where(GovernanceAssessment.input_assessment_id == input_assessment_id)
        .order_by(GovernanceAssessment.created_at)
    )
    output_assessments = result.scalars().all()
    return [AssessmentResponse.model_validate(a) for a in output_assessments]

@router.get("", response_model=list[AssessmentResponse])
async def list_assessments(
    db: DbSession,
    application_id: Optional[uuid.UUID] = None,
    phase: Optional[str] = Query(default=None, description="Filter by phase: INPUT or OUTPUT"),
) -> list[AssessmentResponse]:
    """List governance assessments, most recent first.
    Optional filters:
      - application_id: only return assessments for a specific AI application
      - phase: only return INPUT or OUTPUT assessments
    """
    query = select(GovernanceAssessment).order_by(GovernanceAssessment.created_at.desc())
    if application_id:
        query = query.where(GovernanceAssessment.application_id == application_id)
    if phase:
        phase_upper = phase.upper()
        if phase_upper not in ("INPUT", "OUTPUT"):
            raise HTTPException(
                status_code=400,
                detail="phase must be 'INPUT' or 'OUTPUT'",
            )
        query = query.where(GovernanceAssessment.assessment_phase == phase_upper)
    result = await db.execute(query)
    return [AssessmentResponse.model_validate(a) for a in result.scalars().all()]

