"""
GovernanceAssessment and Finding models.

One GovernanceAssessment = one audit cycle for ONE piece of text.
  - phase="INPUT"  → auditing the user's prompt before it reaches the AI
  - phase="OUTPUT" → auditing the AI's response after the AI has replied
Output assessments link back to their corresponding input assessment
via input_assessment_id so you can trace the full interaction.
Finding — a specific violation found by an agent during an assessment.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, generate_uuid


class GovernanceAssessment(Base):
    """
    One governance evaluation run against an AI application.

    INPUT phase:  Created when the user submits a prompt. The system audits
                  the prompt for PII, prompt injection, and policy violations
                  BEFORE it reaches the AI application.
    OUTPUT phase: Created when the AI application responds. The system audits
                  the AI's response for PII leakage, credential leakage,
                  harmful advice, and system prompt disclosure.
    Two separate rows, two separate risk scores, two separate decisions.
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

    # Which phase of the interaction this assessment covers
    assessment_phase: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # INPUT | OUTPUT

    # What triggered this assessment
    assessment_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="REAL_TIME"
    )  # REAL_TIME | SCHEDULED | MANUAL

    # For OUTPUT assessments: links back to the INPUT assessment of the same interaction.
    # NULL for INPUT assessments.
    input_assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_assessments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # The text being evaluated (user prompt for INPUT, AI response for OUTPUT).
    # Stored post-redaction — raw PII is never persisted.
    evaluated_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # True when PII was found and masked before storage
    evaluated_text_redacted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
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

    # For INPUT assessments: all output assessments that followed this input
    output_assessments: Mapped[list["GovernanceAssessment"]] = relationship(
        "GovernanceAssessment",
        foreign_keys=[input_assessment_id],
        back_populates="input_assessment",
    )
    # For OUTPUT assessments: the input assessment this was triggered by
    input_assessment: Mapped[Optional["GovernanceAssessment"]] = relationship(
        "GovernanceAssessment",
        foreign_keys=[input_assessment_id],
        back_populates="output_assessments",
        remote_side=[id],
    )

    def __repr__(self) -> str:
        return (
            f"<GovernanceAssessment id={self.id} phase={self.assessment_phase} "
            f"decision={self.decision} risk={self.risk_level}>"
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
