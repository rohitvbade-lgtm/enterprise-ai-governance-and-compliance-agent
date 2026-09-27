"""Migration 003 - Sync DB to models (applied via direct SQL).
This migration was applied directly to the database. The revision markers
are preserved here so Alembic can traverse the migration chain.
Revision ID: 003
Revises: 002
Create Date: 2026-09-27
"""
from __future__ import annotations
from typing import Sequence, Union
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    pass  # Migration was applied directly; no-op here.
def downgrade() -> None:
    pass  # No automated downgrade; schema changes are additive.