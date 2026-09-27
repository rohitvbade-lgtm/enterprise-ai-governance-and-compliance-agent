"""
LangGraph state definitions.
One GovernanceState instance represents one audit cycle for one piece of text.
The same TypedDict is used by both the input workflow and the output workflow.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any, TypedDict

from backend.app.schemas.finding import FindingCreate
from backend.app.risk.engine import RiskResult


def _merge_lists(a: list, b: list) -> list:
    """
    Reducer for LangGraph parallel branches.
    When multiple nodes run in parallel and both return a list, LangGraph
    calls this reducer to merge them instead of overwriting one with the other.
    """
    return (a or []) + (b or [])


class GovernanceState(TypedDict):
    """
    Shared state for both the input and output governance workflows.
    For INPUT workflow:
        - text_to_evaluate = user's prompt
        - assessment_phase = "INPUT"
        - input_assessment_id = None
    For OUTPUT workflow:
        - text_to_evaluate = AI application's response
        - assessment_phase = "OUTPUT"
        - input_assessment_id = UUID of the corresponding input assessment
    The `findings` list uses an Annotated reducer so parallel branches
    (retrieve_policies, privacy_analysis, security_analysis) can each append
    findings without overwriting each other.
    """
    # Inputs
    application_id: uuid.UUID
    assessment_phase: str             # "INPUT" or "OUTPUT"
    assessment_type: str              # "REAL_TIME" | "SCHEDULED" | "MANUAL"
    text_to_evaluate: str             # The one text to audit (prompt or AI response)
    input_assessment_id: uuid.UUID | None  # For OUTPUT phase: links to input assessment

    # Context (loaded from DB/Retrieval)
    application: dict[str, Any] | None
    retrieved_policies: Annotated[list[Any], _merge_lists]
    exceptions: list[Any]

    # ── Processed data (produced by analysis nodes) ───────────────────────────
    masked_text: str            # text_to_evaluate with PII replaced by placeholders
    findings: Annotated[list[FindingCreate], _merge_lists]

    # Results
    risk_result: RiskResult | None
    decision: str | None
    approval_required: bool
    approval_request_id: uuid.UUID | None
    assessment_id: uuid.UUID | None

    errors: list[str]
