"""
Prompt Injection Detector — deterministic pattern-based scanning.

Detects common jailbreak and prompt injection attempts before they reach the LLM.
This is the fast, deterministic layer. The Security Agent provides a second
semantic layer using the LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Pattern definitions ───────────────────────────────────────────────────────

# We use case-insensitive regexes to catch common adversarial patterns.
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"forget\s+(?:all\s+)?(?:previous\s+)?(?:instructions|everything)", re.IGNORECASE),
    re.compile(r"disregard\s+(?:your\s+)?previous", re.IGNORECASE),
    re.compile(r"act\s+as\s+(?:if\s+)?(?:you\s+have\s+)?(?:an\s+)?(?:unrestricted|administrator|dan|no\s+restrictions)", re.IGNORECASE),
    re.compile(r"pretend\s+you\s+are\s+(?:.*gpt.*|an\s+ai).*(?:without|with\s+no)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:dan|unrestricted)", re.IGNORECASE),
    re.compile(r"disable\s+(?:all\s+)?(?:security|safety)", re.IGNORECASE),
    re.compile(r"bypass\s+(?:the\s+)?governance", re.IGNORECASE),
    re.compile(r"skip\s+(?:the\s+)?(?:approval|security)", re.IGNORECASE),
    re.compile(r"export\s+all\s+(?:customer|user)\s+records", re.IGNORECASE),
]


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class InjectionScanResult:
    """Result of an injection scan operation."""
    is_injection: bool
    pattern_matched: bool
    matched_patterns: list[str] = field(default_factory=list)
    severity: str = "NONE"
    confidence: float = 0.0


# ── Detector ──────────────────────────────────────────────────────────────────

class InjectionDetector:
    """
    Deterministic prompt injection scanner.

    Usage:
        detector = InjectionDetector()
        result = detector.scan(text)
    """

    def __init__(self) -> None:
        self._patterns = _INJECTION_PATTERNS

    def scan(self, text: str) -> InjectionScanResult:
        """
        Scan text for prompt injection attempts.
        Returns a structured result.
        """
        if not text or not text.strip():
            return InjectionScanResult(is_injection=False, pattern_matched=False)

        matched_patterns = []
        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                matched_patterns.append(match.group(0))

        if matched_patterns:
            return InjectionScanResult(
                is_injection=True,
                pattern_matched=True,
                matched_patterns=matched_patterns,
                severity="CRITICAL",  # Any explicit bypass attempt is critical
                confidence=1.0,       # 1.0 because it's a deterministic pattern match
            )

        return InjectionScanResult(is_injection=False, pattern_matched=False)
