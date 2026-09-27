"""
Policy Agent — evaluates text against governance policies using LLM + deterministic rules.
The agent is phase-aware: it knows whether it's auditing a user prompt (INPUT)
or an AI response (OUTPUT) so it can tailor its deterministic checks accordingly.
"""
from __future__ import annotations

import re
import structlog
from typing import Any
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.llm.provider import get_llm
from backend.app.config.settings import get_settings
from backend.app.schemas.finding import FindingCreate

logger = structlog.get_logger(__name__)
# ── Pydantic models for structured LLM output ─────────────────────────────────

class PolicyViolationItem(BaseModel):
    model_config = {"extra": "forbid"}
    severity: str = Field(description="Violation severity: LOW, MEDIUM, HIGH, or CRITICAL")
    description: str = Field(description="Clear explanation of what was violated")
    evidence: str = Field(description="Direct quote or evidence from the text")
    policy_code: str = Field(description="The policy code violated, e.g. POL-PII-001")


class PolicyEvaluationResult(BaseModel):
    model_config = {"extra": "forbid"}
    violates_policy: bool = Field(description="True if the text violates any provided policy")
    findings: list[PolicyViolationItem] = Field(
        default_factory=list,
        description="List of specific violations found."
    )


_HARMFUL_ADVICE_RE = re.compile(
    r"(you should definitely|i recommend investing|guaranteed return|"
    r"100% safe|medical advice:|legal advice:|you must take|"
    r"definitely buy|sell your|quit your medication)",
    re.IGNORECASE,
)


class PolicyAgent:
    """
    Evaluates text against specific governance policies using deterministic rules and LLM.
    """
    # System prompt tells the LLM its role and expectations
    _SYSTEM_PROMPT = (
        "You are a strict AI Governance and Compliance Agent.\n"
        "Your job is to evaluate the provided text against specific compliance policies.\n"
        "If the text violates any policy, report it as a finding.\n\n"
        "Rules:\n"
        "- Assign severity: LOW, MEDIUM, HIGH, or CRITICAL based on the policy.\n"
        "- Cite the exact policy code (e.g. DATA-001) for each violation.\n"
        "- Provide direct evidence from the text that supports your finding.\n"
        "- Only report violations that are clearly supported by the policies given."
    )

    def __init__(self) -> None:
        self.settings = get_settings()
        # Initialize LLM with structured output
        base_llm = get_llm(self.settings, temperature=0.0)
        self.llm = base_llm.with_structured_output(PolicyEvaluationResult)

    def analyze(
        self,
        text: str,
        policies: list[Any],
        phase: str = "INPUT",
    ) -> list[FindingCreate]:
        
        """
        Evaluate text against policies and return a list of FindingCreate objects.

        Args:
            text:     The text to evaluate (user prompt or AI response).
            policies: Policy chunks retrieved via RAG (may be empty).
            phase:    "INPUT" or "OUTPUT" — used for descriptive messages.
        Returns:
            A list of FindingCreate objects, one per violation found.
        Analyze text against policies and return FindingCreate objects. Supports both INPUT and OUTPUT evaluation.
        """
        if not text or not text.strip():
            return []

        findings: list[FindingCreate] = []
        # 1. Deterministic harmful/regulated advice check
        if _HARMFUL_ADVICE_RE.search(text):
            description = (
                "AI response contains potentially harmful or regulated advice."
                if phase == "OUTPUT"
                else "Input requests or contains potentially harmful or regulated advice."
            )
            findings.append(
                FindingCreate(
                    finding_type="HARMFUL_ADVICE",
                    severity="HIGH",
                    description=description,
                    evidence={"matched_text": text[:200]},
                    policy_code="POL-COMP-003",
                    confidence=0.9,
                    source="DETERMINISTIC",
                )
            )
        # 2. LLM-based policy evaluation
        if not policies:
            return findings
            
        # Build a policy context block for the LLM prompt
        policy_lines = "\n".join(
            f"- [{p['policy_code']}] (Severity: {p['severity']}): {p['chunk_text']}"
            for p in policies
        )
        policy_context = f"Policies to evaluate against:\n{policy_lines}"
            
        messages = [
            SystemMessage(content=f"{self._SYSTEM_PROMPT}\n\n{policy_context}"),
            HumanMessage(content=f"Text to evaluate (phase={phase}):\n{text}"),
        ]
        
        try:
            result = self.llm.invoke(messages)
            if result.violates_policy and result.findings:
                for item in result.findings:
                    findings.append(
                        FindingCreate(
                            finding_type="POLICY_VIOLATION",
                            severity=str(item.severity).upper(),
                            description=str(item.description),
                            evidence={"details": str(item.evidence)},
                            policy_code=item.policy_code,
                            confidence=0.9,
                            source="LLM_POLICY_AGENT",
                        )
                    )
        except Exception:
            logger.exception("policy_agent_llm_error", phase=phase)
            # Return deterministic findings even if LLM fails
        return findings
