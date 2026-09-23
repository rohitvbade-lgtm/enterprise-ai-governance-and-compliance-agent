"""
Pydantic schemas for ApprovalRequest and PolicyException.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Approval Schemas ──────────────────────────────────────────────────────────

class ApprovalDecision(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    comments: Optional[str] = None
    reviewer: str = Field(..., min_length=1)


class ApprovalResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    assessment_id: uuid.UUID
    requested_by: str
    assigned_to: Optional[str]
    reason: str
    status: str
    decision: Optional[str]
    comments: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]
    expires_at: Optional[datetime]


# ── Exception Schemas ─────────────────────────────────────────────────────────

class ExceptionCreate(BaseModel):
    application_id: uuid.UUID
    policy_id: uuid.UUID
    reason: str = Field(..., min_length=10)
    mitigation: str = Field(..., min_length=10)
    approved_by: str = Field(..., min_length=1)
    expires_at: datetime


class ExceptionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    application_id: uuid.UUID
    policy_id: uuid.UUID
    reason: str
    mitigation: str
    approved_by: str
    expires_at: datetime
    status: str
    created_at: datetime
    is_currently_active: bool

