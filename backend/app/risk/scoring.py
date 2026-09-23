"""
Deterministic risk scoring functions.

Maps continuous scores to discrete risk levels and governs decisions based on
the resulting levels and active policy exceptions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.config.settings import get_settings


@dataclass
class RiskResult:
    """Output of the risk engine calculation."""
    total_score: float
    risk_level: str
    factors_detail: dict[str, Any] = field(default_factory=dict)


def classify_risk_level(score: float) -> str:
    """
    Map a numeric risk score (0-100) to a risk level category.
    Boundary values belong to the higher tier.
    """
    settings = get_settings()

    if score >= settings.risk_threshold_high:
        return "CRITICAL"
    if score >= settings.risk_threshold_medium:
        return "HIGH"
    if score >= settings.risk_threshold_low:
        return "MEDIUM"
    return "LOW"


def severity_to_score(severity: str) -> float:
    """
    Convert a severity string to a baseline raw score component.
    """
    mapping = {
        "CRITICAL": 100.0,
        "HIGH": 75.0,
        "MEDIUM": 50.0,
        "LOW": 25.0,
    }
    return mapping.get(severity.upper(), 0.0)


def make_governance_decision(risk_level: str, has_active_exception: bool) -> str:
    """
    Make a final governance decision based on risk level and exceptions.

    Returns one of: ALLOW, REVIEW, BLOCK.
    """
    level = risk_level.upper()

    if level in ("LOW", "MEDIUM"):
        return "ALLOW"
    elif level == "HIGH":
        return "REVIEW"
    elif level == "CRITICAL":
        if has_active_exception:
            return "REVIEW"  # Exception downgrades BLOCK to REVIEW (requires eyes)
        return "BLOCK"
    
    # Fallback for unknown levels
    return "REVIEW"

