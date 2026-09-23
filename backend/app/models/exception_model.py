"""
PolicyException model — time-bound approved exception to a governance policy.

Expired exceptions do NOT bypass violations.
An expired exception must be re-approved to be valid.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, generate_uuid


class PolicyException(Base):
    """
    An approved, time-bound exception to a specific governance policy
    for a specific AI application.

    Critical rules:
    - expires_at is mandatory — permanent silent exceptions are not allowed.
    - The is_active property checks both status AND expiration.
    - Audit records must be created when an exception is granted or expires.
    """

    __tablename__ = "policy_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Why the exception was needed
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # What compensating control is in place
    mitigation: Mapped[str] = mapped_column(Text, nullable=False)

    # Who granted the exception (must be a named person, not "system")
    approved_by: Mapped[str] = mapped_column(String(255), nullable=False)

    # Mandatory expiration — no permanent exceptions
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Lifecycle status (separate from expiration check)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ACTIVE"
    )  # ACTIVE | EXPIRED | REVOKED

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    application: Mapped["AIApplication"] = relationship(  # noqa: F821
        back_populates="exceptions"
    )

    @property
    def is_currently_active(self) -> bool:
        """
        Returns True only if status is ACTIVE and not yet expired.

        This is the authoritative check used by the governance engine.
        An expired exception must NOT bypass a policy violation.
        """
        now = datetime.now(timezone.utc)
        return self.status == "ACTIVE" and self.expires_at > now

    def __repr__(self) -> str:
        return (
            f"<PolicyException app={self.application_id} "
            f"policy={self.policy_id} active={self.is_currently_active}>"
        )

