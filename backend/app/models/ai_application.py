"""
AIApplication model — represents an AI system registered for governance.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin, generate_uuid


class AIApplication(Base, TimestampMixin):
    """
    An AI application registered in the governance platform.

    Examples: Customer Support Copilot, HR Assistant, Financial Advisory Bot.
    """

    __tablename__ = "ai_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Model information
    model_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Deployment context
    environment: Mapped[str] = mapped_column(
        String(50), nullable=False, default="development"
    )  # development | staging | production
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Risk classification
    data_classification: Mapped[str] = mapped_column(
        String(50), nullable=False, default="INTERNAL"
    )  # PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ACTIVE"
    )  # ACTIVE | INACTIVE | SUSPENDED | RETIRED
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # LOW | MEDIUM | HIGH | CRITICAL — set after first assessment

    last_assessment_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    assessments: Mapped[list["GovernanceAssessment"]] = relationship(  # noqa: F821
        back_populates="application", cascade="all, delete-orphan"
    )
    exceptions: Mapped[list["PolicyException"]] = relationship(  # noqa: F821
        back_populates="application", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(  # noqa: F821
        back_populates="application"
    )

    def __repr__(self) -> str:
        return f"<AIApplication id={self.id} name={self.name!r} env={self.environment}>"

