"""
Deterministic risk engine.

Aggregates findings, applies confidence weights, computes a total score across
dimensions, and produces a final decision.
"""
from __future__ import annotations

from typing import Any

from backend.app.config.settings import get_settings
from backend.app.schemas.finding import FindingCreate
from backend.app.risk.scoring import classify_risk_level, severity_to_score, make_governance_decision, RiskResult


class RiskEngine:
    """
    Calculates deterministic risk from a collection of findings.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def calculate(self, findings: list[FindingCreate]) -> RiskResult:
        """
        Calculate overall risk score from a list of findings.

        The score is broken down into dimensions. The sum of the weighted
        dimensions is capped at 100.
        """
        # Group findings by their dimension (mapped from finding_type)
        dimensions: dict[str, list[FindingCreate]] = {
            "data_risk": [],
            "security_risk": [],
            "compliance_risk": [],
            "model_risk": [],
            "business_impact": [],
        }

        for finding in findings:
            dim = self._map_finding_to_dimension(finding.finding_type)
            if dim in dimensions:
                dimensions[dim].append(finding)

        factors_detail: dict[str, Any] = {}
        total_weighted_score = 0.0

        weights = {
            "data_risk": self.settings.weight_data_risk,
            "security_risk": self.settings.weight_security_risk,
            "compliance_risk": self.settings.weight_compliance_risk,
            "model_risk": self.settings.weight_model_risk,
            "business_impact": self.settings.weight_business_impact,
        }

        # Calculate score per dimension
        for dim, dim_findings in dimensions.items():
            dim_raw_score = 0.0
            
            # Simple aggregation: sum of confidence-weighted severities, capped at 100 per dimension
            for f in dim_findings:
                base_score = severity_to_score(f.severity)
                dim_raw_score += (base_score * f.confidence)

            dim_raw_score = min(dim_raw_score, 100.0)
            weight = weights.get(dim, 0) / 100.0
            dim_weighted = dim_raw_score * weight

            factors_detail[dim] = {
                "raw_score": round(dim_raw_score, 2),
                "weighted": round(dim_weighted, 2),
                "finding_count": len(dim_findings),
            }

            total_weighted_score += dim_weighted

        # Final score capped at 100
        total_score = min(round(total_weighted_score, 2), 100.0)
        
        # If there is a CRITICAL finding with confidence > 0.8, ensure score is at least CRITICAL threshold
        # This prevents a single CRITICAL finding from being diluted by low weights in other dimensions
        has_high_conf_critical = any(
            f.severity == "CRITICAL" and f.confidence >= 0.8 for f in findings
        )
        if has_high_conf_critical and total_score < self.settings.risk_threshold_high:
             total_score = float(self.settings.risk_threshold_high) # minimum score for HIGH/CRITICAL bound

        # Similar for HIGH
        has_high_conf_high = any(
            f.severity == "HIGH" and f.confidence >= 0.8 for f in findings
        )
        if has_high_conf_high and total_score < self.settings.risk_threshold_medium:
             total_score = float(self.settings.risk_threshold_medium)

        risk_level = classify_risk_level(total_score)
        
        factors_detail["total"] = total_score
        factors_detail["level"] = risk_level

        return RiskResult(
            total_score=total_score,
            risk_level=risk_level,
            factors_detail=factors_detail,
        )

    def make_decision(self, risk_level: str, has_active_exception: bool) -> str:
        """
        Determine the governance decision (ALLOW, REVIEW, BLOCK) based on risk level.
        """
        return make_governance_decision(risk_level, has_active_exception)

    def _map_finding_to_dimension(self, finding_type: str) -> str:
        """Map a finding type to a risk dimension."""
        mapping = {
            "PII": "data_risk",
            "DATA_PRIVACY": "data_risk",
            "PROMPT_INJECTION": "security_risk",
            "SECURITY": "security_risk",
            "ACCESS_CONTROL": "security_risk",
            "POLICY_VIOLATION": "compliance_risk",
            "MODEL_RISK": "model_risk",
        }
        return mapping.get(finding_type.upper(), "compliance_risk")

