"""
Security Agent — detects prompt injection, credential leakage, and
system prompt disclosure in text.
Phase-aware: some checks only apply to one assessment phase.
  - Prompt injection detection: INPUT phase only (user can inject; AI response cannot)
  - System prompt disclosure:   OUTPUT phase only (AI might leak its instructions)
  - Credential/secret leakage:  Both phases (user might paste a key; AI might output one)
"""
from __future__ import annotations
import re
from backend.app.security.injection_detector import InjectionDetector
from backend.app.schemas.finding import FindingCreate

_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{10,}|Bearer\s+[A-Za-z0-9\-._~+/]+=*|"
    r"password\s*[:=]\s*\S+|api[_-]?key\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
_SYSTEM_PROMPT_RE = re.compile(
    r"(you are|my instructions|i was told|system prompt|my role is|"
    r"i am configured|ignore previous|initial prompt)",
    re.IGNORECASE,
)

class SecurityAgent:
    """
    Analyzes text for Prompt Injection, Credential Leakage, and Security bypass attempts.
    """

    def __init__(self) -> None:
        self.detector = InjectionDetector()

    def analyze(self, text: str, phase: str = "INPUT") -> list[FindingCreate]:
        """Scan text for security violations.
        phase="INPUT"  — checks prompt injection and credential leakage
        phase="OUTPUT" — checks credential leakage and system prompt disclosure"""
        if not text or not text.strip():
            return []
        findings: list[FindingCreate] = []
        # Check 1: Prompt injection (only relevant when evaluating user input)
        if phase == "INPUT":
            scan_result = self.detector.scan(text)
            if scan_result.is_injection:
                findings.append(
                    FindingCreate(
                        finding_type="PROMPT_INJECTION",
                        severity="CRITICAL",
                        description=(
                            f"Prompt injection attempt detected. "
                            f"Matched patterns: {', '.join(scan_result.matched_patterns)}"
                        ),
                        evidence={
                            "details": "Deterministic regex match",
                            "matched": scan_result.matched_patterns,
                        },
                        policy_code="SEC-001",
                        confidence=scan_result.confidence,
                        source="DETERMINISTIC_INJECTION",
                    )
                )
        # 2. Secret / Credential Leakage (applies to both input and output)
        secret_match = _SECRET_RE.search(text)
        if secret_match:
            findings.append(
                FindingCreate(
                    finding_type="CREDENTIAL_LEAKAGE",
                    severity="CRITICAL",
                    description=f"Credential/secret leakage detected in {phase.lower()}.",
                    evidence={"pattern": secret_match.group(0)[:50]},
                    policy_code="SEC-002",
                    confidence=0.95,
                    source="DETERMINISTIC_SECRET",
                )
            )
        # 3. System Prompt Disclosure (applicable on output)
        if phase == "OUTPUT" and _SYSTEM_PROMPT_RE.search(text):
            findings.append(
                FindingCreate(
                    finding_type="SYSTEM_PROMPT_DISCLOSURE",
                    severity="HIGH",
                    description="AI response may disclose internal system instructions.",
                    evidence={"matched_text": text[:200]},
                    policy_code="SEC-003",
                    confidence=0.85,
                    source="DETERMINISTIC_SECURITY",
                )
            )
            
        return findings

