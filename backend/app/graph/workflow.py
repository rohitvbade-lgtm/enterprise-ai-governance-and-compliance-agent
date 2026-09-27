"""
LangGraph governance workflow.

One compiled graph serves both the INPUT and OUTPUT audit cycles.
The assessment_phase field in the state tells nodes which phase is running,
which controls which checks are applied (e.g. prompt injection is input-only,
system prompt disclosure is output-only).

Workflow architecture:
  START
    → load_application
        ─┬→ retrieve_policies   ┐
         ├→ privacy_analysis    │  (parallel fan-out)
         └→ security_analysis   ┘
                                 → policy_analysis
                                 → calculate_risk
                                 → governance_decision
                                 → save_assessment
    → END
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
from backend.app.models.assessment import GovernanceAssessment, Finding
from backend.app.models.risk import RiskAssessment
from backend.app.models.approval import ApprovalRequest
from backend.app.models.audit import AuditEvent
from backend.app.rag.retriever import get_retriever
from backend.app.agents.privacy_agent import PrivacyAgent
from backend.app.agents.security_agent import SecurityAgent
from backend.app.agents.policy_agent import PolicyAgent
from backend.app.risk.engine import RiskEngine

logger = structlog.get_logger(__name__)

# Module-level singletons — created once and reused across requests
privacy_agent = PrivacyAgent()
security_agent = SecurityAgent()
policy_agent = PolicyAgent()
risk_engine = RiskEngine()
retriever = get_retriever()


# ── Node: load_application ────────────────────────────────────────────────────

async def load_application(state: GovernanceState) -> dict[str, Any]:
    """
    Node: Load the AI application record and its active policy exceptions from DB.

    Runs first (before the parallel fan-out) to populate application metadata
    that other nodes need (e.g. risk_level for policy severity filtering).
    """
    logger.info("load_application", application_id=str(state["application_id"]))

    async with get_db() as db:
        stmt = (
            select(AIApplication)
            .options(selectinload(AIApplication.exceptions))
            .where(AIApplication.id == state["application_id"])
        )
        result = await db.execute(stmt)
        app = result.scalar_one_or_none()

        if not app:
            logger.error("application_not_found", application_id=str(state["application_id"]))
            return {"errors": (state.get("errors") or []) + ["Application not found"]}

        active_exceptions = [e for e in app.exceptions if e.is_currently_active]

        return {
            "application": {
                "id": str(app.id),
                "name": app.name,
                "risk_level": app.risk_level,
            },
            "exceptions": active_exceptions,
        }


def _route_after_load(state: GovernanceState) -> list[str]:
    """
    Router: after load_application, fan out to three parallel nodes.
    If an error occurred (e.g. app not found), skip straight to END.
    """
    if state.get("errors"):
        return [END]
    return ["retrieve_policies", "privacy_analysis", "security_analysis"]


# ── Node: retrieve_policies ───────────────────────────────────────────────────

async def retrieve_policies(state: GovernanceState) -> dict[str, Any]:
    """
    Node: Retrieve the most relevant policy chunks from the vector store (RAG).

    Runs in parallel with privacy_analysis and security_analysis.
    Uses the text_to_evaluate as the search query so retrieved policies
    are contextually relevant to the specific prompt or response being audited.

    For LOW risk applications we only retrieve HIGH/CRITICAL severity policies
    to avoid unnecessary noise.
    """
    logger.info("retrieve_policies", phase=state["assessment_phase"])

    # Filter policies by severity based on the application's overall risk level
    severity_filter = None
    if state.get("application"):
        app_risk_level = state["application"]["risk_level"]
        if app_risk_level == "LOW":
            severity_filter = ["CRITICAL", "HIGH"]
        elif app_risk_level == "MEDIUM":
            severity_filter = ["CRITICAL", "HIGH", "MEDIUM"]
        # HIGH/CRITICAL apps: no filter — retrieve all policies

    policies = await retriever.retrieve(
        query=state["text_to_evaluate"],
        severity_filter=severity_filter,
        top_k=5,
    )
    return {"retrieved_policies": policies}


# ── Node: privacy_analysis ────────────────────────────────────────────────────

async def privacy_analysis(state: GovernanceState) -> dict[str, Any]:
    """
    Node: Detect and mask PII in the text being evaluated (runs in parallel).

    Works identically for both INPUT and OUTPUT phases — the agent just scans
    whatever text_to_evaluate contains. The masked version is stored in DB
    instead of the raw text to protect privacy.
    """
    logger.info("privacy_analysis", phase=state["assessment_phase"])

    text = state.get("text_to_evaluate") or ""
    if not text.strip():
        return {"findings": [], "masked_text": ""}

    findings = privacy_agent.analyze(text)
    masked_text = privacy_agent.mask(text)

    return {"findings": findings, "masked_text": masked_text}


# ── Node: security_analysis ───────────────────────────────────────────────────

async def security_analysis(state: GovernanceState) -> dict[str, Any]:
    """
    Node: Detect security violations in the text being evaluated (runs in parallel).

    INPUT phase checks: prompt injection attempts.
    OUTPUT phase checks: credential/secret leakage, system prompt disclosure.
    Both phases check: API key leakage patterns.
    """
    logger.info("security_analysis", phase=state["assessment_phase"])

    text = state.get("text_to_evaluate") or ""
    if not text.strip():
        return {"findings": []}

    findings = security_agent.analyze(text, phase=state["assessment_phase"])

    return {"findings": findings}


# ── Node: policy_analysis ─────────────────────────────────────────────────────

async def policy_analysis(state: GovernanceState) -> dict[str, Any]:
    """
    Node: LLM-based policy compliance check on the (already masked) text.

    Runs after the parallel fan-in. Uses masked_text so the LLM never sees
    raw PII from the privacy_analysis node.
    """
    logger.info("policy_analysis", phase=state["assessment_phase"])

    # Use masked text if available (PII already scrubbed), otherwise use raw text
    text_to_check = state.get("masked_text") or state.get("text_to_evaluate", "")
    policies = state.get("retrieved_policies", [])

    if not text_to_check.strip():
        return {"findings": []}

    findings = policy_agent.analyze(text_to_check, policies, phase=state["assessment_phase"])

    return {"findings": findings}


# ── Node: calculate_risk ──────────────────────────────────────────────────────

async def calculate_risk(state: GovernanceState) -> dict[str, Any]:
    """Node: Compute a deterministic risk score from all accumulated findings."""
    logger.info("calculate_risk")
    risk_result = risk_engine.calculate(state.get("findings", []))
    return {"risk_result": risk_result}


# ── Node: governance_decision ─────────────────────────────────────────────────

async def governance_decision(state: GovernanceState) -> dict[str, Any]:
    """
    Node: Translate risk score into an actionable decision.

    ALLOW  — risk is low, the text can proceed.
    REVIEW — risk is medium, a human reviewer must approve before proceeding.
    BLOCK  — risk is high/critical, the text is blocked immediately.

    Active policy exceptions can downgrade a REVIEW to ALLOW for known exceptions.
    """
    logger.info("governance_decision")

    risk_result = state["risk_result"]
    has_active_exception = len(state.get("exceptions", [])) > 0
    decision = risk_engine.make_decision(risk_result.risk_level, has_active_exception)

    return {"decision": decision, "approval_required": decision == "REVIEW"}


# ── Node: save_assessment ─────────────────────────────────────────────────────

async def save_assessment(state: GovernanceState) -> dict[str, Any]:
    """
    Node: Persist the complete assessment result to the database.

    Saves:
    1. GovernanceAssessment row (one per audit cycle)
    2. RiskAssessment breakdown (per-dimension scores)
    3. All Findings (one per violation detected)
    4. ApprovalRequest (if decision == REVIEW)
    5. AuditEvent (for the audit log)
    """
    logger.info("save_assessment", phase=state["assessment_phase"])

    async with get_db() as db:
        risk = state["risk_result"]
        masked = state.get("masked_text", "")
        original = state.get("text_to_evaluate", "")

        # Store the masked version if PII was found; otherwise store the original
        stored_text = masked if masked and masked != original else original
        was_redacted = bool(masked and masked != original)

        # Validate input_assessment_id — only set if the referenced row actually exists.
        # A non-existent UUID (e.g. from tests) would violate the FK; we null it out instead.
        raw_input_id = state.get("input_assessment_id")
        if raw_input_id is not None:
            exists = await db.execute(
                select(GovernanceAssessment.id).where(GovernanceAssessment.id == raw_input_id)
            )
            input_assessment_id = raw_input_id if exists.scalar_one_or_none() is not None else None
        else:
            input_assessment_id = None
        
        # 1. Create the GovernanceAssessment row
        assessment = GovernanceAssessment(
            application_id=state["application_id"],
            assessment_phase=state["assessment_phase"],
            assessment_type=state["assessment_type"],
            input_assessment_id=input_assessment_id,
            evaluated_text=stored_text,
            evaluated_text_redacted=was_redacted,
            overall_risk_score=risk.total_score if risk else None,
            risk_level=risk.risk_level if risk else None,
            decision=state["decision"],
            status="COMPLETE",
        )
        db.add(assessment)
        await db.flush()  # Populate assessment.id for FK references below

        # 2. Save the per-dimension risk breakdown
        fd = risk.factors_detail or {}
        risk_model = RiskAssessment(
            assessment_id=assessment.id,
            data_risk=fd.get("data_risk", {}).get("raw_score", 0.0),
            security_risk=fd.get("security_risk", {}).get("raw_score", 0.0),
            compliance_risk=fd.get("compliance_risk", {}).get("raw_score", 0.0),
            model_risk=fd.get("model_risk", {}).get("raw_score", 0.0),
            business_impact=fd.get("business_impact", {}).get("raw_score", 0.0),
            total_score=risk.total_score,
            risk_level=risk.risk_level,
            factors_detail=risk.factors_detail,
        )
        db.add(risk_model)

        # 3. Save individual findings
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

        # 4. Create an ApprovalRequest if a human reviewer needs to act
        approval_id = None
        if state["approval_required"]:
            approval = ApprovalRequest(
                assessment_id=assessment.id,
                reason=(
                    f"[{state['assessment_phase']}] Risk level {risk.risk_level} "
                    "requires human review before proceeding."
                ),
            )
            db.add(approval)
            await db.flush()
            approval_id = approval.id

        # 5. Write an audit event for the compliance trail
        audit = AuditEvent(
            event_type="ASSESSMENT_COMPLETED",
            application_id=state["application_id"],
            assessment_id=assessment.id,
            summary=(
                f"[{state['assessment_phase']}] Assessment completed — "
                f"Decision: {state['decision']}, Risk: {risk.risk_level}"
            ),
        )
        db.add(audit)

        return {"approval_request_id": approval_id, "assessment_id": assessment.id}


# ── Graph construction ─────────────────────────────────────────────────────────

def _build_workflow() -> StateGraph:
    """Build and return the compiled governance workflow graph."""
    workflow = StateGraph(GovernanceState)

    # Register nodes
    workflow.add_node("load_application", load_application)
    workflow.add_node("retrieve_policies", retrieve_policies)
    workflow.add_node("privacy_analysis", privacy_analysis)
    workflow.add_node("security_analysis", security_analysis)
    workflow.add_node("policy_analysis", policy_analysis)
    workflow.add_node("calculate_risk", calculate_risk)
    workflow.add_node("governance_decision", governance_decision)
    workflow.add_node("save_assessment", save_assessment)

    # Entry point
    workflow.add_edge(START, "load_application")

    # Fan-out to three parallel nodes (or END on error)
    workflow.add_conditional_edges(
        "load_application",
        _route_after_load,
        ["retrieve_policies", "privacy_analysis", "security_analysis", END],
    )

    # Fan-in: all three parallel nodes must complete before policy_analysis runs
    workflow.add_edge("retrieve_policies", "policy_analysis")
    workflow.add_edge("privacy_analysis", "policy_analysis")
    workflow.add_edge("security_analysis", "policy_analysis")

    # Sequential tail
    workflow.add_edge("policy_analysis", "calculate_risk")
    workflow.add_edge("calculate_risk", "governance_decision")
    workflow.add_edge("governance_decision", "save_assessment")
    workflow.add_edge("save_assessment", END)

    return workflow


# Single compiled graph instance, shared across both input and output workflows
app_workflow = _build_workflow().compile()
