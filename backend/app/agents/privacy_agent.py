"""
Privacy Agent — wraps PIIDetector to map results to FindingCreate objects.
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
        """Scan text and return findings."""
        scan_result = self.detector.scan(text)
        
        findings = []
        for f in scan_result.findings:
            findings.append(
                FindingCreate(
                    finding_type="PII",
                    severity=f["severity"],
                    description=f["description"],
                    evidence={"details": f"Detected {f['pii_type']}"},
                    confidence=1.0,
                    source="DETERMINISTIC_PII",
                )
            )
            
        return findings

    def mask(self, text: str) -> str:
        """Mask PII in text."""
        return self.detector.mask(text)

