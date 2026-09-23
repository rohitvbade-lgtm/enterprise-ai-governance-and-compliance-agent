"""
ApprovalRequest model — human-in-the-loop workflow for high-risk decisions.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, generate_uuid


class ApprovalRequest(Base):
    """
    A request for human review of a REVIEW-level governance decision.

    Statuses: PENDING → APPROVED | REJECTED | EXPIRED
    """

    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Who requested and who should review
    requested_by: Mapped[str] = mapped_column(
        String(255), nullable=False, default="system"
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Why approval is needed
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Workflow state
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING"
    )  # PENDING | APPROVED | REJECTED | EXPIRED

    # Resolution
    decision: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # APPROVED | REJECTED
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    assessment: Mapped["GovernanceAssessment"] = relationship(  # noqa: F821
        back_populates="approval_requests"
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalRequest id={self.id} status={self.status} "
            f"assigned_to={self.assigned_to!r}>"
        )

