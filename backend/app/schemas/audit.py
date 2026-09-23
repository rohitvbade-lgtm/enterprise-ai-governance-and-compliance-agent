"""
Pydantic schemas for AuditEvent.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    event_type: str
    application_id: Optional[uuid.UUID]
    assessment_id: Optional[uuid.UUID]
    actor: str
    details: Optional[dict[str, Any]]
    summary: Optional[str]
    created_at: datetime


class AuditReportRequest(BaseModel):
    assessment_id: uuid.UUID


class AuditReportResponse(BaseModel):
    """Structured governance audit report — generated from DB data, not LLM."""
    assessment_id: uuid.UUID
    application_name: str
    generated_at: datetime

    # Summary
    decision: str
    risk_score: float
    risk_level: str

    # Risk dimensions
    risk_factors: dict[str, float]

    # Findings
    total_findings: int
    findings_by_type: dict[str, int]
    findings_by_severity: dict[str, int]
    findings: list[dict[str, Any]]

    # Policies evaluated
    policies_evaluated: list[str]

    # Exceptions
    exceptions_applied: list[dict[str, Any]]

    # Approvals
    approval_history: list[dict[str, Any]]

    # Audit trail
    audit_events: list[dict[str, Any]]

    # LLM-generated summary (optional, labelled as AI-generated)
    ai_summary: Optional[str] = None

