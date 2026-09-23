"""
Primary governance evaluation endpoint.

POST /governance/evaluate — triggers the full LangGraph workflow.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException

from backend.app.schemas.assessment import GovernanceEvaluateRequest, GovernanceEvaluateResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/evaluate", response_model=GovernanceEvaluateResponse)
async def evaluate(body: GovernanceEvaluateRequest) -> GovernanceEvaluateResponse:
    """
    Run a full governance evaluation through the LangGraph workflow.

    This endpoint:
    1. Loads the registered AI application
    2. Retrieves relevant policies via RAG
    3. Runs PII detection, injection detection, and policy compliance analysis
    4. Calculates deterministic risk score
    5. Checks active policy exceptions
    6. Makes a governance decision: ALLOW | REVIEW | BLOCK
    7. Creates an approval request if REVIEW
    8. Writes all audit events
    9. Returns the decision with full context

    Note: The LangGraph workflow (Phase 4) wires this fully.
    Phase 1-2 returns a placeholder response.
    """
    from backend.app.graph.workflow import app_workflow
    
    logger.info(
        "governance_evaluate_called",
        application_id=str(body.application_id),
        input_length=len(body.input_text),
    )
    
    try:
        # Initial state for the LangGraph workflow
        initial_state = {
            "application_id": body.application_id,
            "input_text": body.input_text,
            "assessment_type": body.assessment_type,
            "application": None,
            "retrieved_policies": [],
            "exceptions": [],
            "masked_text": "",
            "findings": [],
            "risk_result": None,
            "decision": None,
            "approval_required": False,
            "approval_request_id": None,
            "audit_events": [],
            "errors": []
        }
        
        # Execute workflow
        final_state = await app_workflow.ainvoke(initial_state)
        
        # Check for errors from workflow
        if final_state.get("errors"):
            raise HTTPException(status_code=404, detail=final_state["errors"][0])
            
        risk = final_state["risk_result"]
        findings = final_state.get("findings", [])
        
        # Aggregate finding severities
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for f in findings:
            if f.severity in severity_counts:
                severity_counts[f.severity] += 1
                
        return GovernanceEvaluateResponse(
            assessment_id=final_state.get("assessment_id", __import__("uuid").uuid4()),
            application_id=body.application_id,
            decision=final_state["decision"],
            risk_score=risk.total_score if risk else 0.0,
            risk_level=risk.risk_level if risk else "UNKNOWN",
            findings_count=len(findings),
            findings_by_severity=severity_counts,
            approval_required=final_state["approval_required"],
            approval_request_id=final_state.get("approval_request_id"),
            message="Governance evaluation completed successfully.",
        )
    except Exception as e:
        logger.exception("governance_evaluation_failed")
        raise HTTPException(status_code=500, detail=str(e))

