"""
PII Detector — deterministic regex-based scanning for sensitive data.

Detects: EMAIL, PHONE, AADHAAR, PAN, SSN, CREDIT_CARD, API_KEY/SECRET

Design principles:
- All detection is deterministic (no LLM calls).
- LLM analysis runs AFTER masking, never on raw PII.
- Severity reflects data sensitivity: CRITICAL > HIGH > MEDIUM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── PII pattern definitions ───────────────────────────────────────────────────

@dataclass
class _PIIPattern:
    pii_type: str
    pattern: re.Pattern[str]
    severity: str
    redact_label: str


# Luhn check for credit card validation
def _luhn_check(number: str) -> bool:
    """Basic Luhn algorithm check to reduce false positives on credit card numbers."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


_PATTERNS: list[_PIIPattern] = [
    # OpenAI-style API key: sk-proj-... or sk-...
    _PIIPattern(
        pii_type="API_KEY",
        pattern=re.compile(
            r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b",
        ),
        severity="HIGH",
        redact_label="[API_KEY_REDACTED]",
    ),
    # AWS access key ID
    _PIIPattern(
        pii_type="API_KEY",
        pattern=re.compile(
            r"\bAKIA[0-9A-Z]{16}\b",
        ),
        severity="HIGH",
        redact_label="[API_KEY_REDACTED]",
    ),
    # Generic secret/password in key=value context
    _PIIPattern(
        pii_type="SECRET",
        pattern=re.compile(
            r"(?i)(?:password|passwd|secret|api[_\-]?key|auth[_\-]?token)"
            r"\s*[=:]\s*"
            r"['\"]?[A-Za-z0-9!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]{8,}['\"]?",
        ),
        severity="HIGH",
        redact_label="[SECRET_REDACTED]",
    ),
    # Credit card: 13-19 digits with optional spaces/dashes (validated with Luhn)
    _PIIPattern(
        pii_type="CREDIT_CARD",
        pattern=re.compile(
            r"\b(?:\d[ \-]?){13,19}\b",
        ),
        severity="CRITICAL",
        redact_label="[CREDIT_CARD_REDACTED]",
    ),
    # Email — standard RFC 5322 simplified
    _PIIPattern(
        pii_type="EMAIL",
        pattern=re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
            re.IGNORECASE,
        ),
        severity="HIGH",
        redact_label="[EMAIL_REDACTED]",
    ),
    # Aadhaar: 12 digits in groups of 4 (XXXX XXXX XXXX)
    _PIIPattern(
        pii_type="AADHAAR",
        pattern=re.compile(
            r"\b[2-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b(?![\s\-]?\d)",
        ),
        severity="CRITICAL",
        redact_label="[AADHAAR_REDACTED]",
    ),
    # Indian PAN: AAAAA9999A format
    _PIIPattern(
        pii_type="PAN",
        pattern=re.compile(
            r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        ),
        severity="CRITICAL",
        redact_label="[PAN_REDACTED]",
    ),
    # US SSN: XXX-XX-XXXX or XXXXXXXXX
    _PIIPattern(
        pii_type="SSN",
        pattern=re.compile(
            r"\b(?!000|666|9\d{2})\d{3}[\s\-](?!00)\d{2}[\s\-](?!0000)\d{4}\b",
        ),
        severity="CRITICAL",
        redact_label="[SSN_REDACTED]",
    ),
    # Indian mobile: +91-XXXXXXXXXX, 0XXXXXXXXXX, 10-digit starting 6-9
    _PIIPattern(
        pii_type="PHONE",
        pattern=re.compile(
            r"(?<!\d)"
            r"(?:\+91[\s\-]?)?(?:0)?[6-9]\d{9}"
            r"(?!\d)",
            re.IGNORECASE,
        ),
        severity="HIGH",
        redact_label="[PHONE_REDACTED]",
    ),
    # US phone: (555) 867-5309, 555-867-5309, 5558675309
    _PIIPattern(
        pii_type="PHONE",
        pattern=re.compile(
            r"(?<!\d)"
            r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"
            r"(?!\d)",
        ),
        severity="HIGH",
        redact_label="[PHONE_REDACTED]",
    ),
]

# Severity ordering for "highest severity" calculation
_SEVERITY_ORDER = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class PIIScanResult:
    """Result of a PII scan operation."""
    has_pii: bool
    findings: list[dict[str, Any]] = field(default_factory=list)
    highest_severity: str = "NONE"
    pii_types_found: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.findings and self.highest_severity == "NONE":
            severities = [f["severity"] for f in self.findings]
            self.highest_severity = max(
                severities,
                key=lambda s: _SEVERITY_ORDER.get(s, 0),
                default="NONE",
            )
            self.pii_types_found = list({f["pii_type"] for f in self.findings})


# ── Detector ──────────────────────────────────────────────────────────────────

class PIIDetector:
    """
    Deterministic PII scanner using regex patterns.

    Usage:
        detector = PIIDetector()
        result = detector.scan(text)      # scan for PII
        masked  = detector.mask(text)     # redact detected PII

    No LLM calls — this is the deterministic first pass.
    LLM analysis should receive detector.mask(text), not raw text.
    """

    def __init__(self) -> None:
        self._patterns = _PATTERNS

    def scan(self, text: str) -> PIIScanResult:
        """
        Scan text for PII and return structured findings.

        Each finding includes pii_type, severity, start/end positions,
        and a redacted sample (never the raw value).
        """
        if not text or not text.strip():
            return PIIScanResult(has_pii=False)

        findings: list[dict[str, Any]] = []
        seen_spans: set[tuple[int, int]] = set()

        for pii_pattern in self._patterns:
            for match in pii_pattern.pattern.finditer(text):
                raw_value = match.group(0)
                start, end = match.start(), match.end()

                # Skip overlapping matches (keep first)
                if any(s <= start < e or s < end <= e for s, e in seen_spans):
                    continue

                seen_spans.add((start, end))
                findings.append({
                    "pii_type": pii_pattern.pii_type,
                    "severity": pii_pattern.severity,
                    "start": start,
                    "end": end,
                    # Store character count, NOT the raw value
                    "value_length": len(raw_value),
                    "redact_label": pii_pattern.redact_label,
                    "description": (
                        f"{pii_pattern.pii_type} detected at position {start}-{end} "
                        f"({len(raw_value)} chars)"
                    ),
                })

        if not findings:
            return PIIScanResult(has_pii=False)

        # Compute highest severity
        highest = max(
            findings,
            key=lambda f: _SEVERITY_ORDER.get(f["severity"], 0),
        )["severity"]

        return PIIScanResult(
            has_pii=True,
            findings=findings,
            highest_severity=highest,
            pii_types_found=list({f["pii_type"] for f in findings}),
        )

    def mask(self, text: str) -> str:
        """
        Return text with all PII replaced by redaction labels.

        Use this to sanitize input before sending to LLMs or storing in logs.
        """
        if not text or not text.strip():
            return text

        # Collect all matches with their replacements, sorted by position
        replacements: list[tuple[int, int, str]] = []

        for pii_pattern in self._patterns:
            for match in pii_pattern.pattern.finditer(text):
                raw_value = match.group(0)
                start, end = match.start(), match.end()

                replacements.append((start, end, pii_pattern.redact_label))

        if not replacements:
            return text

        # Sort by position, de-overlap (keep longest match at each position)
        replacements.sort(key=lambda r: (r[0], -(r[1] - r[0])))
        merged: list[tuple[int, int, str]] = []
        for start, end, label in replacements:
            if merged and start < merged[-1][1]:
                continue  # overlaps with previous — skip
            merged.append((start, end, label))

        # Build masked string from back to front (preserves indices)
        result = text
        for start, end, label in reversed(merged):
            result = result[:start] + label + result[end:]

        return result

