"""
Pydantic schemas for GovernanceAssessment API.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class AssessmentCreate(BaseModel):
    application_id: uuid.UUID
    input_text: str = Field(..., min_length=1, description="The AI input/interaction to evaluate")
    assessment_type: str = Field(default="REAL_TIME", pattern="^(REAL_TIME|SCHEDULED|MANUAL)$")


class AssessmentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    application_id: uuid.UUID
    assessment_type: str
    overall_risk_score: Optional[float]
    risk_level: Optional[str]
    decision: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]


class GovernanceEvaluateRequest(BaseModel):
    """Primary governance evaluation endpoint request body."""
    application_id: uuid.UUID
    input_text: str = Field(..., min_length=1)
    assessment_type: str = Field(default="REAL_TIME")
    context: Optional[dict[str, Any]] = None


class GovernanceEvaluateResponse(BaseModel):
    """Full result including findings and risk breakdown."""
    assessment_id: uuid.UUID
    application_id: uuid.UUID
    decision: str  # ALLOW | REVIEW | BLOCK
    risk_score: float
    risk_level: str
    findings_count: int
    findings_by_severity: dict[str, int]
    approval_required: bool
    approval_request_id: Optional[uuid.UUID]
    message: str

