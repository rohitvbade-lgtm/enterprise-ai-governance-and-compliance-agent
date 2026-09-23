"""
Pydantic schemas for Finding (agent evidence).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class FindingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    assessment_id: uuid.UUID
    finding_type: str
    severity: str
    description: str
    evidence: Optional[dict[str, Any]]
    policy_id: Optional[uuid.UUID]
    policy_code: Optional[str]
    confidence: float
    source: str
    created_at: datetime


class FindingCreate(BaseModel):
    """Internal schema used by agents to create findings."""
    finding_type: str
    severity: str
    description: str
    evidence: Optional[dict[str, Any]] = None
    policy_id: Optional[uuid.UUID] = None
    policy_code: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "DETERMINISTIC"

