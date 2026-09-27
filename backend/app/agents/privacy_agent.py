"""
Privacy Agent — detects and masks PII in text.
Works the same way for both INPUT and OUTPUT assessment phases.
The agent doesn't need to know which phase is running — it simply
finds PII in whatever text it receives and reports findings.
"""
from __future__ import annotations

from backend.app.security.pii_detector import PIIDetector
from backend.app.schemas.finding import FindingCreate

class PrivacyAgent:
    """
    Analyzes text for Privacy & Data Protection issues.
    """

    def __init__(self) -> None:
        self.detector = PIIDetector()

    def analyze(self, text: str) -> list[FindingCreate]:
        """
        Scan text for PII patterns and return one FindingCreate per detected item.
        Returns an empty list if the text is empty or clean.
        """
        if not text or not text.strip():
            return []
        scan_result = self.detector.scan(text)
        
        findings = []
        for f in scan_result.findings:
            findings.append(
                FindingCreate(
                    finding_type="PII",
                    severity=f["severity"],
                    description=f["description"],
                    evidence={"details": f"Detected {f['pii_type']}"},
                    policy_code="POL-PII-001",
                    confidence=1.0,
                    source="DETERMINISTIC_PII",
                )
            )
            
        return findings

    def mask(self, text: str) -> str:
        """Mask PII in text."""
        if not text:
            return ""
        return self.detector.mask(text)

