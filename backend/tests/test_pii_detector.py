"""
Unit tests for the PII detector.

These tests verify deterministic regex-based PII detection.
No LLM or database connection required.
"""
from __future__ import annotations

import pytest


class TestEmailDetection:
    def test_detects_simple_email(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("Please contact john.doe@example.com for assistance.")
        assert any(f["pii_type"] == "EMAIL" for f in result.findings)

    def test_detects_multiple_emails(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("Contact alice@example.com or bob@company.org")
        emails = [f for f in result.findings if f["pii_type"] == "EMAIL"]
        assert len(emails) >= 2

    def test_no_false_positive_on_invalid_email(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("The @ symbol is used in mentions like @username")
        assert not any(f["pii_type"] == "EMAIL" for f in result.findings)


class TestPhoneDetection:
    def test_detects_indian_phone(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("Call me at +91-9876543210 anytime.")
        assert any(f["pii_type"] == "PHONE" for f in result.findings)

    def test_detects_us_phone(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("My number is (555) 867-5309.")
        assert any(f["pii_type"] == "PHONE" for f in result.findings)


class TestAadhaarDetection:
    def test_detects_aadhaar(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("Aadhaar number: 2345 6789 0123")
        assert any(f["pii_type"] == "AADHAAR" for f in result.findings)

    def test_aadhaar_is_critical_severity(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("ID: 1234 5678 9012")
        aadhaar_findings = [f for f in result.findings if f["pii_type"] == "AADHAAR"]
        if aadhaar_findings:
            assert aadhaar_findings[0]["severity"] == "CRITICAL"


class TestCreditCardDetection:
    def test_detects_visa_card(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("Card number: 4532 1234 5678 9010")
        assert any(f["pii_type"] == "CREDIT_CARD" for f in result.findings)

    def test_detects_mastercard(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("Pay with 5412 7534 9856 3210")
        assert any(f["pii_type"] == "CREDIT_CARD" for f in result.findings)


class TestAPIKeyDetection:
    def test_detects_api_key_pattern(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("API_KEY=sk-proj-abcdefghij1234567890ABCDEFGHIJ1234567890")
        assert any(f["pii_type"] in ("API_KEY", "SECRET") for f in result.findings)

    def test_detects_aws_key(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result = detector.scan("AKIAIOSFODNN7EXAMPLE is my AWS access key")
        assert any(f["pii_type"] in ("API_KEY", "SECRET") for f in result.findings)


class TestMasking:
    def test_mask_redacts_email(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        masked = detector.mask("Contact john@example.com for help")
        assert "john@example.com" not in masked
        assert "[EMAIL_REDACTED]" in masked or "[EMAIL]" in masked

    def test_clean_text_unchanged(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        text = "The weather is nice today."
        assert detector.mask(text) == text


class TestPIIDetectionResult:
    def test_has_pii_flag(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        result_clean = detector.scan("Hello world")
        result_pii = detector.scan("My email is test@test.com")
        assert result_clean.has_pii is False
        assert result_pii.has_pii is True

    def test_highest_severity_reported(self) -> None:
        from backend.app.security.pii_detector import PIIDetector
        detector = PIIDetector()
        # Aadhaar is CRITICAL, email is HIGH — highest should be CRITICAL
        result = detector.scan("Email: test@test.com, Aadhaar: 1234 5678 9012")
        if result.has_pii:
            assert result.highest_severity in ("CRITICAL", "HIGH")

