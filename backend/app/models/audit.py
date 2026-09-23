"""
AuditEvent model — immutable governance event log.

IMPORTANT: Audit records are NEVER deleted or modified.
This table is append-only by design and convention.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, generate_uuid


# All valid event types — fixed vocabulary, not LLM-generated
AUDIT_EVENT_TYPES = frozenset(
    {
        "APPLICATION_REGISTERED",
        "APPLICATION_UPDATED",
        "ASSESSMENT_STARTED",
        "ASSESSMENT_COMPLETED",
        "POLICY_RETRIEVED",
        "PII_DETECTED",
        "INJECTION_DETECTED",
        "POLICY_VIOLATION",
        "RISK_CALCULATED",
        "EXCEPTION_CHECKED",
        "DECISION_MADE",
        "APPROVAL_REQUESTED",
        "APPROVAL_GRANTED",
        "APPROVAL_REJECTED",
        "APPROVAL_EXPIRED",
        "EXCEPTION_CREATED",
        "EXCEPTION_EXPIRED",
        "EXCEPTION_REVOKED",
        "AUDIT_REPORT_GENERATED",
        "POLICY_INGESTED",
        "SYSTEM_ERROR",
    }
)


class AuditEvent(Base):
    """
    An immutable record of a significant governance action.

    Every governance decision, PII detection, approval, and exception
    must produce an AuditEvent. This table must never be modified
    or deleted from — it is the system's compliance trail.

    PII and sensitive data must be REDACTED before storage in `details`.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )

    # What happened
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # Must be one of AUDIT_EVENT_TYPES

    # Context references (nullable — not all events relate to both)
    application_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_assessments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Who or what triggered this event
    actor: Mapped[str] = mapped_column(
        String(255), nullable=False, default="system"
    )  # "system" | agent name | user identifier

    # Event-specific payload (PII must be redacted before storage)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Human-readable summary
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Immutable timestamp — set at creation, never updated
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships (read-only references)
    application: Mapped[Optional["AIApplication"]] = relationship(  # noqa: F821
        back_populates="audit_events"
    )
    assessment: Mapped[Optional["GovernanceAssessment"]] = relationship(  # noqa: F821
        back_populates="audit_events"
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEvent type={self.event_type!r} "
            f"actor={self.actor!r} at={self.created_at}>"
        )

