"""
Security Agent — wraps InjectionDetector to map results to FindingCreate objects.
"""
from __future__ import annotations

from backend.app.security.injection_detector import InjectionDetector
from backend.app.schemas.finding import FindingCreate

class SecurityAgent:
    """
    Analyzes text for Prompt Injection and Security bypass attempts.
    """

    def __init__(self) -> None:
        self.detector = InjectionDetector()

    def analyze(self, text: str) -> list[FindingCreate]:
        """Scan text and return findings."""
        scan_result = self.detector.scan(text)
        
        findings = []
        if scan_result.is_injection:
            findings.append(
                FindingCreate(
                    finding_type="PROMPT_INJECTION",
                    severity=scan_result.severity,
                    description=f"Prompt injection detected. Matches: {', '.join(scan_result.matched_patterns)}",
                    evidence={"details": "Deterministic regex match"},
                    confidence=scan_result.confidence,
                    source="DETERMINISTIC_INJECTION",
                )
            )
            
        return findings

