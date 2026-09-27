"""
Pydantic schemas for the two-phase AI governance API.
Phase 1 — Input Audit:  POST /governance/evaluate/input
Phase 2 — Output Audit: POST /governance/evaluate/output
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class AssessmentResponse(BaseModel):
    """API response for a single governance assessment (either INPUT or OUTPUT phase)."""
    model_config = {"from_attributes": True}

    id: uuid.UUID
    application_id: uuid.UUID
    assessment_phase: str
    input_assessment_id: Optional[uuid.UUID] = None   # Only set for OUTPUT assessments
    evaluated_text: Optional[str] = None              # Stored post-redaction
    evaluated_text_redacted: bool = False
    overall_risk_score: Optional[float]
    risk_level: Optional[str]
    decision: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]


class InputEvaluateRequest(BaseModel):
    """
    Request body to audit a user's prompt BEFORE it reaches the AI application.
    Submit this when a user sends a message to your AI app.
    """
    application_id: uuid.UUID
    input_text: str = Field(..., min_length=1, description="The user's prompt to audit")
    assessment_type: str = Field(default="REAL_TIME")
    context: Optional[dict[str, Any]] = None


class InputEvaluateResponse(BaseModel):
    """
    Result of the input audit.
    If decision == ALLOW, pass the prompt to the AI application.
    If decision == BLOCK or REVIEW, do not forward the prompt.
    """
    assessment_id: uuid.UUID
    application_id: uuid.UUID
    assessment_phase: str = "INPUT"
    decision: str                        # ALLOW | REVIEW | BLOCK
    risk_score: float
    risk_level: str
    findings_count: int
    findings_by_severity: dict[str, int]
    approval_required: bool
    approval_request_id: Optional[uuid.UUID]
    message: str

# ── Output Audit ──────────────────────────────────────────────────────────────
class OutputEvaluateRequest(BaseModel):
    """
    Request body to audit an AI application's response AFTER it has replied.
    Submit this once you receive the AI response, linking it to the input assessment.
    """
    application_id: uuid.UUID
    output_text: str = Field(..., min_length=1, description="The AI application's response to audit")
    input_assessment_id: Optional[uuid.UUID] = Field(
        default=None,
        description="The assessment_id from the corresponding input audit (optional but recommended)"
    )
    assessment_type: str = Field(default="REAL_TIME")
    context: Optional[dict[str, Any]] = None
class OutputEvaluateResponse(BaseModel):
    """
    Result of the output audit.
    Even if the input was ALLOW, the output may still be BLOCK (e.g. credential leakage).
    """
    assessment_id: uuid.UUID
    application_id: uuid.UUID
    assessment_phase: str = "OUTPUT"
    input_assessment_id: Optional[uuid.UUID]     # Links back to the input assessment
    decision: str                                 # ALLOW | REVIEW | BLOCK
    risk_score: float
    risk_level: str
    findings_count: int
    findings_by_severity: dict[str, int]
    approval_required: bool
    approval_request_id: Optional[uuid.UUID]
    message: str
# ── Legacy compatibility (kept for existing code that uses GovernanceEvaluateRequest) ──
# Removed: GovernanceEvaluateRequest and GovernanceEvaluateResponse
# Use InputEvaluateRequest / OutputEvaluateRequest instead.
