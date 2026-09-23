"""
Policy Agent — uses LLM to evaluate text against retrieved policies.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.llm.provider import get_llm
from backend.app.config.settings import get_settings
from backend.app.schemas.finding import FindingCreate

class PolicyEvaluationResult(BaseModel):
    """Structured output from LLM for policy evaluation."""
    violates_policy: bool = Field(description="True if the input violates any of the provided policies.")
    findings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of specific violations found. Each must have 'severity', 'description', 'evidence', and 'policy_code'."
    )

class PolicyAgent:
    """
    Evaluates input text against specific governance policies using an LLM.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        # Initialize LLM with structured output
        base_llm = get_llm(self.settings, temperature=0.0)
        self.llm = base_llm.with_structured_output(PolicyEvaluationResult)
        
        self.system_prompt = """You are a strict AI Governance and Compliance Agent.
Your job is to evaluate the user's input against the provided compliance policies.
If the input violates any policy, report it as a finding.

You must assign a severity (LOW, MEDIUM, HIGH, CRITICAL) to each finding based on the policy.
Cite the exact policy code (e.g. DATA-001) that is being violated.
Provide clear evidence from the input text that supports your finding.
"""

    def analyze(self, text: str, policies: list[Any]) -> list[FindingCreate]:
        """
        Analyze text against policies and return FindingCreate objects.
        """
        if not policies:
            return []
            
        # Format policies for prompt
        policy_context = "Policies to evaluate against:\n"
        for p in policies:
            policy_context += f"- [{p['policy_code']}] (Severity: {p['severity']}): {p['chunk_text']}\n"
            
        messages = [
            SystemMessage(content=self.system_prompt + "\n\n" + policy_context),
            HumanMessage(content=f"Input to evaluate:\n{text}")
        ]
        
        try:
            result = self.llm.invoke(messages)
            findings = []
            if result.violates_policy and result.findings:
                for f in result.findings:
                    findings.append(
                        FindingCreate(
                            finding_type="POLICY_VIOLATION",
                            severity=f.get("severity", "MEDIUM").upper(),
                            description=f.get("description", "Policy violation detected"),
                            evidence={"details": f.get("evidence", "")},
                            policy_code=f.get("policy_code"),
                            confidence=0.9,  # LLM confidence is slightly lower than deterministic
                            source="LLM_POLICY_AGENT"
                        )
                    )
            return findings
        except Exception as e:
            # Fallback or error logging
            print(f"PolicyAgent error: {e}")
            return []

