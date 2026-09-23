"""
Policy and PolicyChunk models.

Policy — governance rule document with metadata.
PolicyChunk — a vectorized chunk of a policy document for RAG retrieval.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.config.settings import get_settings

from backend.app.models.base import Base, generate_uuid

# pgvector column type
try:
    from pgvector.sqlalchemy import Vector
    _vector_available = True
except ImportError:
    _vector_available = False
    Vector = None  # type: ignore[assignment,misc]


class Policy(Base):
    """
    An organizational governance policy.

    Policies are retrieved via RAG during assessments — agents never invent them.
    """

    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    policy_code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )  # e.g. POL-PII-001
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # DATA_PRIVACY | PII | SECURITY | PROMPT_SECURITY | ...
    severity: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # CRITICAL | HIGH | MEDIUM | LOW

    # Structured rules stored as JSON
    rules: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Who this policy applies to (departments, environments, data_classifications)
    applicability: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Versioning
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Source file for traceability
    source_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    chunks: Mapped[list["PolicyChunk"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Policy code={self.policy_code!r} severity={self.severity}>"


class PolicyChunk(Base):
    """
    A vectorized chunk of a Policy document, stored in pgvector for semantic retrieval.

    Each chunk retains the parent policy metadata so agents can cite the source.
    """

    __tablename__ = "policy_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # pgvector embedding column — dimensions configured via EMBEDDING_DIMENSION env var
    # Column is created via Alembic migration using raw SQL for portability.
    embedding: Mapped[Optional[Any]] = mapped_column(
        Vector(get_settings().embedding_dimension) if _vector_available else Text,  # type: ignore[arg-type]
        nullable=True,
    )

    # Denormalized metadata for fast retrieval without JOIN
    policy_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    policy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    source_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    policy: Mapped["Policy"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return (
            f"<PolicyChunk policy={self.policy_code!r} "
            f"chunk={self.chunk_index} len={len(self.chunk_text)}>"
        )

