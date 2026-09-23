"""
LangGraph state definitions.
"""
from __future__ import annotations

import uuid
from typing import Any, TypedDict

from backend.app.schemas.finding import FindingCreate
from backend.app.risk.engine import RiskResult

class GovernanceState(TypedDict):
    """
    The state dictionary for the LangGraph governance workflow.
    """
    # Inputs
    application_id: uuid.UUID
    input_text: str
    assessment_type: str  # e.g., "PROMPT", "OUTPUT"
    
    # Context (loaded from DB/Retrieval)
    application: dict[str, Any] | None
    retrieved_policies: list[Any]
    exceptions: list[Any]
    
    # Processed Data
    masked_text: str
    findings: list[FindingCreate]
    
    # Results
    risk_result: RiskResult | None
    decision: str | None
    approval_required: bool
    approval_request_id: uuid.UUID | None
    assessment_id: uuid.UUID | None
    
    # Telemetry
    audit_events: list[dict[str, Any]]
    errors: list[str]

