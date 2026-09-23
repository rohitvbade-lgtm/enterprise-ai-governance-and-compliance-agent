"""
RiskAssessment model — the deterministic risk calculation output.

Stores all contributing factors so the decision is fully reconstructible.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, generate_uuid


class RiskAssessment(Base):
    """
    Deterministic risk calculation result for one GovernanceAssessment.

    The risk engine populates this — no LLM involvement in the numbers.

    Example factors_detail:
    {
        "data_risk": {"raw_score": 25, "weighted": 7.5, "contributing_findings": [...]},
        "security_risk": {"raw_score": 80, "weighted": 24.0, ...},
        ...
        "total": 58.0,
        "level": "MEDIUM"
    }
    """

    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_assessments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one-to-one with GovernanceAssessment
        index=True,
    )

    # Per-dimension raw scores (0–100 each)
    data_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    security_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    compliance_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    business_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Weighted total (0–100)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # LOW | MEDIUM | HIGH | CRITICAL

    # Full breakdown for auditability
    factors_detail: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    assessment: Mapped["GovernanceAssessment"] = relationship(  # noqa: F821
        back_populates="risk_assessment"
    )

    def __repr__(self) -> str:
        return (
            f"<RiskAssessment total={self.total_score:.1f} "
            f"level={self.risk_level}>"
        )

