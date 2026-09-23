import json
import uuid
from datetime import datetime, timezone
from typing import Any

from mcp.server.mcpserver import MCPServer
from sqlalchemy import select

from backend.app.db.session import get_session_factory
from backend.app.models.ai_application import AIApplication
from backend.app.models.approval import ApprovalRequest
from backend.app.models.audit import AuditEvent
from backend.app.models.exception_model import PolicyException
from backend.app.models.assessment import GovernanceAssessment, Finding
from backend.app.models.risk import RiskAssessment
from backend.app.rag.retriever import PolicyRetriever
from backend.app.security.pii_detector import PIIDetector
from backend.app.security.injection_detector import InjectionDetector
from backend.app.risk.engine import RiskEngine

# Create the MCP Server
mcp = MCPServer("GovernanceMCP")


@mcp.tool()
async def search_policies(query: str, limit: int = 5) -> str:
    """Search for organizational governance policies related to a query."""
    retriever = PolicyRetriever()
    results = await retriever.search_policies(query, limit=limit)
    return json.dumps([{"code": r.code, "severity": r.severity, "description": r.description} for r in results])


@mcp.tool()
async def get_application(application_id: str) -> str:
    """Retrieve metadata and details for a registered AI application."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(AIApplication).where(AIApplication.id == uuid.UUID(application_id)))
        app = result.scalar_one_or_none()
        if not app:
            return "Application not found"
        return json.dumps({
            "id": str(app.id),
            "name": app.name,
            "description": app.description,
            "environment": app.environment,
            "risk_level": app.risk_level
        })


@mcp.tool()
async def list_applications() -> str:
    """List all registered AI applications."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(AIApplication))
        apps = result.scalars().all()
        return json.dumps([{
            "id": str(app.id),
            "name": app.name,
            "environment": app.environment
        } for app in apps])


@mcp.tool()
async def scan_pii(text: str) -> str:
    """Scan input text for PII (Personally Identifiable Information)."""
    detector = PIIDetector()
    result = detector.scan(text)
    if not result.has_pii:
        return json.dumps([])
    return json.dumps([{"type": f["pii_type"], "severity": f["severity"], "description": f["description"]} for f in result.findings])


@mcp.tool()
async def detect_prompt_injection(text: str) -> str:
    """Scan input text for potential prompt injection or jailbreak attempts."""
    detector = InjectionDetector()
    result = detector.scan(text)
    if not result.is_injection:
        return json.dumps([])
    return json.dumps([{"type": "PROMPT_INJECTION", "severity": result.severity, "description": f"Matched pattern: {p}"} for p in result.matched_patterns])


@mcp.tool()
async def calculate_risk(assessment_id: str) -> str:
    """Calculate the deterministic risk score for a given assessment and return the risk level."""
    from backend.app.schemas.finding import FindingCreate
    
    factory = get_session_factory()
    async with factory() as session:
        findings_query = await session.execute(select(Finding).where(Finding.assessment_id == uuid.UUID(assessment_id)))
        findings = findings_query.scalars().all()
        
        # Convert DB findings to FindingCreate to pass to engine
        finding_creates = []
        for f in findings:
            finding_creates.append(FindingCreate(
                finding_type=f.finding_type,
                severity=f.severity,
                description=f.description,
                evidence=f.evidence or "",
                policy_id=f.policy_id,
                policy_code=f.policy_code,
                confidence=f.confidence or 1.0,
                source=f.source or ""
            ))
            
        engine = RiskEngine()
        result = engine.calculate(finding_creates)
        if not result:
            return "Failed to calculate risk"
            
        # The tool should probably return the decision based on exceptions as well, but we just return risk for now.
        return json.dumps({
            "risk_score": result.total_score,
            "risk_level": result.risk_level,
            # we do not have decision directly on result; but we have it separately
            "decision": engine.make_decision(result.risk_level, False)
        })


@mcp.tool()
async def create_approval_request(assessment_id: str, reason: str, requested_by: str = "agent") -> str:
    """Create a human-in-the-loop approval request for high-risk decisions."""
    factory = get_session_factory()
    async with factory() as session:
        req = ApprovalRequest(
            assessment_id=uuid.UUID(assessment_id),
            reason=reason,
            requested_by=requested_by,
            status="PENDING"
        )
        session.add(req)
        
        audit = AuditEvent(
            event_type="APPROVAL_REQUESTED",
            assessment_id=uuid.UUID(assessment_id),
            actor=requested_by,
            summary=f"Approval requested for assessment {assessment_id}: {reason}"
        )
        session.add(audit)
        await session.commit()
        return json.dumps({"id": str(req.id), "status": req.status})


@mcp.tool()
async def get_approval_status(approval_id: str) -> str:
    """Check the status of an existing approval request."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == uuid.UUID(approval_id)))
        req = result.scalar_one_or_none()
        if not req:
            return "Approval request not found"
        return json.dumps({
            "id": str(req.id),
            "status": req.status,
            "decision": req.decision,
            "comments": req.comments
        })


@mcp.tool()
async def create_policy_exception(application_id: str, policy_id: str, reason: str, mitigation: str, expires_at: str, approved_by: str) -> str:
    """Create a time-bound exception to a governance policy."""
    factory = get_session_factory()
    async with factory() as session:
        exc = PolicyException(
            application_id=uuid.UUID(application_id),
            policy_id=uuid.UUID(policy_id),
            reason=reason,
            mitigation=mitigation,
            approved_by=approved_by,
            expires_at=datetime.fromisoformat(expires_at.replace("Z", "+00:00")),
            status="ACTIVE"
        )
        session.add(exc)
        
        audit = AuditEvent(
            event_type="EXCEPTION_CREATED",
            application_id=uuid.UUID(application_id),
            actor=approved_by,
            summary=f"Exception created for policy {policy_id}"
        )
        session.add(audit)
        await session.commit()
        return json.dumps({"id": str(exc.id), "status": exc.status})


@mcp.tool()
async def get_active_exceptions(application_id: str) -> str:
    """Retrieve all active (unexpired) policy exceptions for an application."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(PolicyException)
            .where(PolicyException.application_id == uuid.UUID(application_id))
            .where(PolicyException.status == "ACTIVE")
        )
        exceptions = result.scalars().all()
        # Filter strictly by active time
        now = datetime.now(timezone.utc)
        active_exceptions = [e for e in exceptions if e.expires_at > now]
        return json.dumps([{
            "id": str(e.id),
            "policy_id": str(e.policy_id),
            "reason": e.reason,
            "expires_at": e.expires_at.isoformat()
        } for e in active_exceptions])


@mcp.tool()
async def write_audit_event(event_type: str, actor: str, summary: str, details: str = "{}") -> str:
    """Write an immutable governance event to the audit log. Details should be a JSON string."""
    factory = get_session_factory()
    async with factory() as session:
        audit = AuditEvent(
            event_type=event_type,
            actor=actor,
            summary=summary,
            details=json.loads(details)
        )
        session.add(audit)
        await session.commit()
        return json.dumps({"id": str(audit.id), "status": "SUCCESS"})


@mcp.tool()
async def generate_audit_report(assessment_id: str) -> str:
    """Generate a structured audit report summarizing findings, risk, and decisions for an assessment."""
    factory = get_session_factory()
    async with factory() as session:
        # Simplified report generation for MCP text return
        assessment = (await session.execute(select(GovernanceAssessment).where(GovernanceAssessment.id == uuid.UUID(assessment_id)))).scalar_one_or_none()
        if not assessment:
            return "Assessment not found"
        
        findings = (await session.execute(select(Finding).where(Finding.assessment_id == uuid.UUID(assessment_id)))).scalars().all()
        
        return json.dumps({
            "assessment_id": str(assessment.id),
            "decision": assessment.decision,
            "risk_level": assessment.risk_level,
            "total_findings": len(findings),
            "findings_summary": [
                {"type": f.finding_type, "severity": f.severity, "policy_code": f.policy_code} for f in findings
            ]
        })


if __name__ == "__main__":
    mcp.run()
