"""
GovernanceAssessment and Finding models.

GovernanceAssessment — one complete evaluation of an AI application/input.
Finding — a piece of evidence produced by an agent (PII, injection, policy violation, etc.).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, generate_uuid


class GovernanceAssessment(Base):
    """
    One governance evaluation run against an AI application.

    Created when POST /assessments is called.
    The LangGraph workflow populates this record as it progresses.
    """

    __tablename__ = "governance_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What triggered this assessment
    assessment_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="REAL_TIME"
    )  # REAL_TIME | SCHEDULED | MANUAL

    # The input being evaluated (may be redacted if PII was found before storage)
    input_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_text_redacted: Mapped[bool] = mapped_column(
        # True if PII was masked in the stored input_text
        String(5),
        nullable=False,
        default="false",
    )

    # Results
    overall_risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # LOW | MEDIUM | HIGH | CRITICAL
    decision: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # ALLOW | REVIEW | BLOCK

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING"
    )  # PENDING | IN_PROGRESS | AWAITING_APPROVAL | COMPLETE | ERROR

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    application: Mapped["AIApplication"] = relationship(  # noqa: F821
        back_populates="assessments"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )
    risk_assessment: Mapped[Optional["RiskAssessment"]] = relationship(  # noqa: F821
        back_populates="assessment", uselist=False, cascade="all, delete-orphan"
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(  # noqa: F821
        back_populates="assessment", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(  # noqa: F821
        back_populates="assessment"
    )

    def __repr__(self) -> str:
        return (
            f"<GovernanceAssessment id={self.id} "
            f"decision={self.decision} risk={self.overall_risk_score}>"
        )


class Finding(Base):
    """
    Evidence produced by a governance agent during an assessment.

    Findings are the building blocks of the risk calculation.
    LLMs produce findings; the deterministic risk engine consumes them.
    """

    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Finding classification
    finding_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # PII | PROMPT_INJECTION | POLICY_VIOLATION | SECURITY | ACCESS_CONTROL | MODEL_RISK
    severity: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # CRITICAL | HIGH | MEDIUM | LOW

    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured evidence (redacted — no raw PII)
    evidence: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # The policy that was violated (if applicable)
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    policy_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # Denormalized for quick display

    # Confidence score: 0.0–1.0
    # 1.0 = deterministic pattern match, <1.0 = LLM-based analysis
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # What produced this finding
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DETERMINISTIC"
    )  # DETERMINISTIC | LLM | HYBRID

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    assessment: Mapped["GovernanceAssessment"] = relationship(back_populates="findings")

    def __repr__(self) -> str:
        return (
            f"<Finding type={self.finding_type} severity={self.severity} "
            f"confidence={self.confidence:.2f} source={self.source}>"
        )

