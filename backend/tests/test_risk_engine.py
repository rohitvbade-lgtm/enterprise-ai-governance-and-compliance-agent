"""
Unit tests for the deterministic risk engine.

The risk engine must be fully testable without LLM or database connections.
"""
from __future__ import annotations

import pytest


# ── Risk engine imports (Phase 4) ─────────────────────────────────────────────
# These will be implemented in Phase 4; tests define the expected interface.


class TestRiskThresholds:
    """Verify risk level classification from score."""

    @pytest.mark.parametrize(
        "score,expected_level",
        [
            (0, "LOW"),
            (15, "LOW"),
            (29, "LOW"),
            (30, "MEDIUM"),
            (45, "MEDIUM"),
            (59, "MEDIUM"),
            (60, "HIGH"),
            (75, "HIGH"),
            (79, "HIGH"),
            (80, "CRITICAL"),
            (95, "CRITICAL"),
            (100, "CRITICAL"),
        ],
    )
    def test_classify_risk_level(self, score: int, expected_level: str) -> None:
        """Risk level classification must be deterministic and match thresholds."""
        from backend.app.risk.scoring import classify_risk_level
        assert classify_risk_level(score) == expected_level

    def test_boundary_values_are_exclusive_to_higher_tier(self) -> None:
        """Score exactly at a threshold boundary belongs to the higher tier."""
        from backend.app.risk.scoring import classify_risk_level
        # 30 is the first MEDIUM score (not LOW)
        assert classify_risk_level(30) == "MEDIUM"
        # 60 is the first HIGH score (not MEDIUM)
        assert classify_risk_level(60) == "HIGH"
        # 80 is the first CRITICAL score (not HIGH)
        assert classify_risk_level(80) == "CRITICAL"


class TestRiskScoreCalculation:
    """Verify weighted risk score calculation."""

    def test_no_findings_produces_zero_risk(self) -> None:
        from backend.app.risk.engine import RiskEngine
        engine = RiskEngine()
        result = engine.calculate(findings=[])
        assert result.total_score == 0.0
        assert result.risk_level == "LOW"

    def test_single_critical_finding_elevates_risk(self) -> None:
        """A single CRITICAL finding should push the score above MEDIUM."""
        from backend.app.risk.engine import RiskEngine
        from backend.app.schemas.finding import FindingCreate

        engine = RiskEngine()
        findings = [
            FindingCreate(
                finding_type="PROMPT_INJECTION",
                severity="CRITICAL",
                description="Injection attempt detected",
                confidence=1.0,
                source="DETERMINISTIC",
            )
        ]
        result = engine.calculate(findings=findings)
        assert result.total_score > 30, "Critical finding must push risk above LOW"

    def test_multiple_high_findings_escalate_to_high(self) -> None:
        """Multiple HIGH findings should push the total to HIGH or CRITICAL."""
        from backend.app.risk.engine import RiskEngine
        from backend.app.schemas.finding import FindingCreate

        engine = RiskEngine()
        findings = [
            FindingCreate(
                finding_type="PII",
                severity="HIGH",
                description="Email address detected",
                confidence=1.0,
                source="DETERMINISTIC",
            ),
            FindingCreate(
                finding_type="POLICY_VIOLATION",
                severity="HIGH",
                description="PII policy violated",
                confidence=0.9,
                source="LLM",
            ),
            FindingCreate(
                finding_type="SECURITY",
                severity="HIGH",
                description="Sensitive data in output",
                confidence=0.85,
                source="HYBRID",
            ),
        ]
        result = engine.calculate(findings=findings)
        assert result.risk_level in ("HIGH", "CRITICAL")

    def test_risk_score_does_not_exceed_100(self) -> None:
        """Risk score must be capped at 100."""
        from backend.app.risk.engine import RiskEngine
        from backend.app.schemas.finding import FindingCreate

        engine = RiskEngine()
        # Flood with critical findings
        findings = [
            FindingCreate(
                finding_type="PROMPT_INJECTION",
                severity="CRITICAL",
                description=f"Critical finding {i}",
                confidence=1.0,
                source="DETERMINISTIC",
            )
            for i in range(10)
        ]
        result = engine.calculate(findings=findings)
        assert result.total_score <= 100.0

    def test_low_confidence_finding_has_reduced_impact(self) -> None:
        """A low-confidence finding should contribute less to the score."""
        from backend.app.risk.engine import RiskEngine
        from backend.app.schemas.finding import FindingCreate

        engine = RiskEngine()

        high_conf = [FindingCreate(
            finding_type="PII", severity="HIGH",
            description="High confidence", confidence=1.0, source="DETERMINISTIC"
        )]
        low_conf = [FindingCreate(
            finding_type="PII", severity="HIGH",
            description="Low confidence", confidence=0.3, source="LLM"
        )]

        result_high = engine.calculate(findings=high_conf)
        result_low = engine.calculate(findings=low_conf)

        assert result_high.total_score > result_low.total_score


class TestGovernanceDecision:
    """Verify governance decision logic from risk level."""

    @pytest.mark.parametrize(
        "risk_level,expected_decision",
        [
            ("LOW", "ALLOW"),
            ("MEDIUM", "ALLOW"),
            ("HIGH", "REVIEW"),
            ("CRITICAL", "BLOCK"),
        ],
    )
    def test_decision_from_risk_level(self, risk_level: str, expected_decision: str) -> None:
        from backend.app.risk.engine import RiskEngine
        engine = RiskEngine()
        decision = engine.make_decision(risk_level=risk_level, has_active_exception=False)
        assert decision == expected_decision

    def test_active_exception_can_downgrade_block_to_review(self) -> None:
        """A valid active exception may adjust a BLOCK to REVIEW (not silently ALLOW)."""
        from backend.app.risk.engine import RiskEngine
        engine = RiskEngine()
        decision = engine.make_decision(risk_level="CRITICAL", has_active_exception=True)
        # Even with exception, CRITICAL must not become ALLOW
        assert decision in ("REVIEW", "BLOCK")
        # Finding should still be recorded — only decision is adjusted

