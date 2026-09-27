"""
AI Governance evaluation endpoints — two separate audit cycles.
POST /governance/evaluate/input
    Audit a user's prompt BEFORE it reaches the AI application.
    Returns a decision (ALLOW / REVIEW / BLOCK) for the input.
POST /governance/evaluate/output
    Audit an AI application's response AFTER it has replied.
    Returns a decision for the output, independent of the input decision.
The two endpoints are intentionally separate because they evaluate
fundamentally different things at different points in the interaction lifecycle.
"""
from __future__ import annotations
import structlog
from fastapi import APIRouter, HTTPException
from backend.app.schemas.assessment import (
    InputEvaluateRequest,
    InputEvaluateResponse,
    OutputEvaluateRequest,
    OutputEvaluateResponse,
)
logger = structlog.get_logger(__name__)
router = APIRouter()

def _build_initial_state(
    application_id,
    text: str,
    phase: str,
    assessment_type: str,
    input_assessment_id=None,
) -> dict:
    """Build the initial LangGraph state dictionary for a new audit cycle."""
    return {
        "application_id": application_id,
        "assessment_phase": phase,
        "assessment_type": assessment_type,
        "text_to_evaluate": text,
        "input_assessment_id": input_assessment_id,
        # Populated by workflow nodes:
        "application": None,
        "retrieved_policies": [],
        "exceptions": [],
        "masked_text": "",
        "findings": [],
        "risk_result": None,
        "decision": None,
        "approval_required": False,
        "approval_request_id": None,
        "assessment_id": None,
        "errors": [],
    }

def _count_findings_by_severity(findings: list) -> dict[str, int]:
    """Return a severity → count mapping from a list of FindingCreate objects."""
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        severity = getattr(f, "severity", None) or f.get("severity", "")
        if severity in counts:
            counts[severity] += 1
    return counts

@router.post("/evaluate/input", response_model=InputEvaluateResponse)
async def evaluate_input(body: InputEvaluateRequest) -> InputEvaluateResponse:
    """
    Audit a user prompt BEFORE it is forwarded to the AI application.
    Workflow steps:
    1. Load the registered AI application and its active policy exceptions.
    2. Retrieve relevant policies via RAG (semantic search).
    3. In parallel: detect PII, detect prompt injection/security issues.
    4. Run LLM-based policy compliance check on the masked prompt.
    5. Calculate deterministic risk score from all findings.
    6. Make a governance decision: ALLOW | REVIEW | BLOCK.
    7. Persist the assessment, findings, risk breakdown, and audit event.
    8. Return the decision so the calling system can act on it immediately.
    If decision == ALLOW → forward the prompt to the AI application.
    If decision == BLOCK → reject the prompt and inform the user.
    If decision == REVIEW → hold the prompt for human review.
    """
    from backend.app.graph.workflow import app_workflow
    logger.info(
        "input_audit_requested",
        application_id=str(body.application_id),
        text_length=len(body.input_text),
    )
    try:
        initial_state = _build_initial_state(
            application_id=body.application_id,
            text=body.input_text,
            phase="INPUT",
            assessment_type=body.assessment_type,
        )
        final_state = await app_workflow.ainvoke(initial_state)
        if final_state.get("errors"):
            raise HTTPException(status_code=404, detail=final_state["errors"][0])
        risk = final_state["risk_result"]
        findings = final_state.get("findings", [])
        return InputEvaluateResponse(
            assessment_id=final_state["assessment_id"],
            application_id=body.application_id,
            decision=final_state["decision"],
            risk_score=risk.total_score if risk else 0.0,
            risk_level=risk.risk_level if risk else "UNKNOWN",
            findings_count=len(findings),
            findings_by_severity=_count_findings_by_severity(findings),
            approval_required=final_state["approval_required"],
            approval_request_id=final_state.get("approval_request_id"),
            message="Input audit completed.",
        )    
    except HTTPException:
        raise
    except Exception:
        logger.exception("input_audit_failed")
        raise HTTPException(status_code=500, detail="Input audit failed unexpectedly.")
@router.post("/evaluate/output", response_model=OutputEvaluateResponse)
async def evaluate_output(body: OutputEvaluateRequest) -> OutputEvaluateResponse:
    """
    Audit an AI application's response AFTER it has replied to the user.
    This is a completely independent assessment from the input audit.
    It evaluates what the AI said — regardless of what the user asked.
    Workflow steps:
    1. Load the registered AI application and its active policy exceptions.
    2. Retrieve relevant policies via RAG (using the AI response as the query).
    3. In parallel: detect PII leakage, detect credential/secret leakage.
    4. Run LLM-based policy compliance check on the masked response.
    5. Calculate deterministic risk score from all findings.
    6. Make a governance decision: ALLOW | REVIEW | BLOCK.
    7. Persist the output assessment (linked to input_assessment_id if provided).
    8. Return the decision.
    Typical violations in output:
    - PII leakage (AI reveals user data in its response)
    - Credential leakage (AI outputs API keys or tokens)
    - System prompt disclosure (AI reveals its internal instructions)
    - Harmful advice (AI gives unregulated financial/medical advice)
    """
    from backend.app.graph.workflow import app_workflow
    logger.info(
        "output_audit_requested",
        application_id=str(body.application_id),
        text_length=len(body.output_text),
        input_assessment_id=str(body.input_assessment_id) if body.input_assessment_id else None,
    )
    try:
        initial_state = _build_initial_state(
            application_id=body.application_id,
            text=body.output_text,
            phase="OUTPUT",
            assessment_type=body.assessment_type,
            input_assessment_id=body.input_assessment_id,
        )        
        final_state = await app_workflow.ainvoke(initial_state)
        if final_state.get("errors"):
            raise HTTPException(status_code=404, detail=final_state["errors"][0])
        risk = final_state["risk_result"]
        findings = final_state.get("findings", [])
        return OutputEvaluateResponse(
            assessment_id=final_state["assessment_id"],
            application_id=body.application_id,
            input_assessment_id=body.input_assessment_id,
            decision=final_state["decision"],
            risk_score=risk.total_score if risk else 0.0,
            risk_level=risk.risk_level if risk else "UNKNOWN",
            findings_count=len(findings),
            findings_by_severity=_count_findings_by_severity(findings),
            approval_required=final_state["approval_required"],
            approval_request_id=final_state.get("approval_request_id"),
            message="Output audit completed.",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("output_audit_failed")
        raise HTTPException(status_code=500, detail="Output audit failed unexpectedly.")

