"""
LangGraph workflow definition for AI Governance assessment.
"""
from __future__ import annotations

import structlog
from typing import Any
from langgraph.graph import StateGraph, START, END
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.graph.state import GovernanceState
from backend.app.db.session import get_db
from backend.app.models.ai_application import AIApplication
from backend.app.models.exception_model import PolicyException
from backend.app.models.assessment import GovernanceAssessment, Finding
from backend.app.models.risk import RiskAssessment
from backend.app.models.approval import ApprovalRequest
from backend.app.models.audit import AuditEvent
from backend.app.rag.retriever import get_retriever
from backend.app.agents.privacy_agent import PrivacyAgent
from backend.app.agents.security_agent import SecurityAgent
from backend.app.agents.policy_agent import PolicyAgent
from backend.app.risk.engine import RiskEngine
from backend.app.schemas.finding import FindingCreate

logger = structlog.get_logger(__name__)


# Initialize Singletons
privacy_agent = PrivacyAgent()
security_agent = SecurityAgent()
policy_agent = PolicyAgent()
risk_engine = RiskEngine()
retriever = get_retriever()


async def load_application(state: GovernanceState) -> dict[str, Any]:
    """Node: Fetch application and active exceptions from DB."""
    logger.info("load_application", application_id=str(state["application_id"]))
    
    async with get_db() as db:
        stmt = select(AIApplication).options(
            selectinload(AIApplication.exceptions)
        ).where(AIApplication.id == state["application_id"])
        
        result = await db.execute(stmt)
        app = result.scalar_one_or_none()
        
        if not app:
            logger.error("application_not_found", application_id=str(state["application_id"]))
            return {"errors": state.get("errors", []) + ["Application not found"]}
            
        # Get active exceptions
        active_exceptions = [e for e in app.exceptions if e.is_currently_active]
        
        return {
            "application": {
                "id": str(app.id),
                "name": app.name,
                "risk_level": app.risk_level,
            },
            "exceptions": active_exceptions,
        }


async def retrieve_policies(state: GovernanceState) -> dict[str, Any]:
    """Node: Retrieve relevant policies using RAG."""
    logger.info("retrieve_policies")
    # Determine severity filter based on application risk_tier
    severity_filter = None
    if state.get("application"):
        risk_level = state["application"]["risk_level"]
        if risk_level == "LOW":
             severity_filter = ["CRITICAL", "HIGH"] # Low risk app only checked against high severity policies
        elif risk_level == "MEDIUM":
             severity_filter = ["CRITICAL", "HIGH", "MEDIUM"]
             
    policies = await retriever.retrieve(
        query=state["input_text"], 
        severity_filter=severity_filter,
        top_k=5
    )
    return {"retrieved_policies": policies}


async def privacy_analysis(state: GovernanceState) -> dict[str, Any]:
    """Node: Deterministic PII detection and masking."""
    logger.info("privacy_analysis")
    findings = privacy_agent.analyze(state["input_text"])
    masked = privacy_agent.mask(state["input_text"])
    
    existing = state.get("findings", [])
    return {
        "findings": existing + findings,
        "masked_text": masked
    }


async def security_analysis(state: GovernanceState) -> dict[str, Any]:
    """Node: Deterministic Prompt Injection detection."""
    logger.info("security_analysis")
    findings = security_agent.analyze(state["input_text"])
    
    existing = state.get("findings", [])
    return {
        "findings": existing + findings
    }


async def policy_analysis(state: GovernanceState) -> dict[str, Any]:
    """Node: LLM-based policy evaluation on MASKED text."""
    logger.info("policy_analysis")
    findings = policy_agent.analyze(state.get("masked_text", state["input_text"]), state.get("retrieved_policies", []))
    
    existing = state.get("findings", [])
    return {
        "findings": existing + findings
    }


async def calculate_risk(state: GovernanceState) -> dict[str, Any]:
    """Node: Compute deterministic risk score."""
    logger.info("calculate_risk")
    findings = state.get("findings", [])
    risk_result = risk_engine.calculate(findings)
    return {"risk_result": risk_result}


async def governance_decision(state: GovernanceState) -> dict[str, Any]:
    """Node: Final Allow/Review/Block decision."""
    logger.info("governance_decision")
    risk_result = state["risk_result"]
    exceptions = state.get("exceptions", [])
    
    has_active_exception = len(exceptions) > 0
    decision = risk_engine.make_decision(risk_result.risk_level, has_active_exception)
    
    approval_required = decision == "REVIEW"
    
    return {
        "decision": decision,
        "approval_required": approval_required
    }


async def save_assessment(state: GovernanceState) -> dict[str, Any]:
    """Node: Persist all outcomes to DB."""
    logger.info("save_assessment")
    
    async with get_db() as db:
        # 1. Save GovernanceAssessment
        assessment = GovernanceAssessment(
            application_id=state["application_id"],
            assessment_type=state["assessment_type"],
            input_text=state.get("masked_text", state["input_text"]),
            decision=state["decision"]
        )
        db.add(assessment)
        await db.flush()
        
        # 2. Save RiskAssessment
        risk = state["risk_result"]
        risk_model = RiskAssessment(
            assessment_id=assessment.id,
            total_score=risk.total_score,
            risk_level=risk.risk_level,
            factors_detail=risk.factors_detail,
        )
        db.add(risk_model)
        
        # 3. Save Findings
        for f in state.get("findings", []):
            finding_model = Finding(
                assessment_id=assessment.id,
                finding_type=f.finding_type,
                severity=f.severity,
                description=f.description,
                evidence=f.evidence,
                policy_id=f.policy_id,
                policy_code=f.policy_code,
                confidence=f.confidence,
                source=f.source,
            )
            db.add(finding_model)
            
        # 4. Create Approval Request if needed
        approval_id = None
        if state["approval_required"]:
            approval = ApprovalRequest(
                assessment_id=assessment.id,
                reason=f"Risk level {risk.risk_level} requires human review.",
            )
            db.add(approval)
            await db.flush()
            approval_id = approval.id
            
        # 5. Audit Event
        audit = AuditEvent(
            event_type="ASSESSMENT_COMPLETED",
            application_id=state["application_id"],
            assessment_id=assessment.id,
            summary=f"Assessment completed with decision: {state['decision']} (Risk: {risk.risk_level})"
        )
        db.add(audit)
        
        return {"approval_request_id": approval_id, "assessment_id": assessment.id}


# Build the Graph
workflow = StateGraph(GovernanceState)

workflow.add_node("load_application", load_application)
workflow.add_node("retrieve_policies", retrieve_policies)
workflow.add_node("privacy_analysis", privacy_analysis)
workflow.add_node("security_analysis", security_analysis)
workflow.add_node("policy_analysis", policy_analysis)
workflow.add_node("calculate_risk", calculate_risk)
workflow.add_node("governance_decision", governance_decision)
workflow.add_node("save_assessment", save_assessment)

# Define edges
workflow.add_edge(START, "load_application")
workflow.add_edge("load_application", "retrieve_policies")
workflow.add_edge("retrieve_policies", "privacy_analysis")
workflow.add_edge("privacy_analysis", "security_analysis")
workflow.add_edge("security_analysis", "policy_analysis")
workflow.add_edge("policy_analysis", "calculate_risk")
workflow.add_edge("calculate_risk", "governance_decision")
workflow.add_edge("governance_decision", "save_assessment")
workflow.add_edge("save_assessment", END)

# Compile
app_workflow = workflow.compile()

