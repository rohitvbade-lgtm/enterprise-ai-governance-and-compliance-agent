"""
Migration 002 — Separate input and output governance assessments.
This migration replaces the old 'one row = one interaction' schema with
a new 'one row = one audit phase' schema.
Changes:
  governance_assessments:
    - ADD   assessment_phase       VARCHAR(10)  NOT NULL  ('INPUT' | 'OUTPUT')
    - ADD   input_assessment_id    UUID         NULLABLE  (FK → self, for OUTPUT rows)
    - ADD   evaluated_text         TEXT         NULLABLE  (replaces input_text + output_text)
    - ADD   evaluated_text_redacted BOOLEAN     NOT NULL  DEFAULT false
    - DROP  input_text
    - DROP  input_text_redacted
    - DROP  output_text
    - DROP  output_text_redacted
  findings:
    - DROP  target  (was INPUT|OUTPUT — no longer needed; phase is on the assessment)
Revision ID: 002
Revises: 001
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # ── governance_assessments: add new columns ───────────────────────────────
    # assessment_phase identifies whether this row is an INPUT or OUTPUT audit
    op.add_column(
        "governance_assessments",
        sa.Column(
            "assessment_phase",
            sa.String(10),
            nullable=False,
            server_default="INPUT",   # Back-fill existing rows as INPUT assessments
        ),
    )
    # input_assessment_id links an OUTPUT assessment back to its INPUT counterpart
    op.add_column(
        "governance_assessments",
        sa.Column(
            "input_assessment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )    
    op.create_foreign_key(
        "fk_governance_assessments_input_assessment_id",
        "governance_assessments",
        "governance_assessments",
        ["input_assessment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_governance_assessments_input_assessment_id",
        "governance_assessments",
        ["input_assessment_id"],
    )
    # evaluated_text holds the text that was actually audited (post-redaction)
    op.add_column(
        "governance_assessments",
        sa.Column("evaluated_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "governance_assessments",
        sa.Column(
            "evaluated_text_redacted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )    
    # ── governance_assessments: migrate data then drop old columns ─────────────
    # Copy input_text → evaluated_text for all existing INPUT rows
    op.execute(
        """
        UPDATE governance_assessments
        SET evaluated_text = input_text,
            evaluated_text_redacted = (input_text_redacted = 'true')
        WHERE input_text IS NOT NULL
        """
    )
    # Remove the old columns
    op.drop_column("governance_assessments", "input_text")
    op.drop_column("governance_assessments", "input_text_redacted")
    op.drop_column("governance_assessments", "output_text")
    op.drop_column("governance_assessments", "output_text_redacted")
    # ── findings: drop the target column ─────────────────────────────────────
    # The phase is now encoded at the assessment level, not per-finding.
    op.drop_column("findings", "target")

def downgrade() -> None:
    # Restore findings.target
    op.add_column(
        "findings",
        sa.Column("target", sa.String(50), nullable=False, server_default="INPUT"),
    )
    # Restore old governance_assessments columns
    op.add_column(
        "governance_assessments",
        sa.Column("output_text_redacted", sa.String(5), nullable=False, server_default="false"),
    )
    op.add_column(
        "governance_assessments",
        sa.Column("output_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "governance_assessments",
        sa.Column("input_text_redacted", sa.String(5), nullable=False, server_default="false"),
    )
    op.add_column(
        "governance_assessments",
        sa.Column("input_text", sa.Text(), nullable=True),    
    )
    # Migrate data back
    op.execute(
        """
        UPDATE governance_assessments
        SET input_text = evaluated_text,
            input_text_redacted = CASE WHEN evaluated_text_redacted THEN 'true' ELSE 'false' END
        WHERE assessment_phase = 'INPUT'
        """
    )
    # Drop new columns
    op.drop_index("ix_governance_assessments_input_assessment_id", "governance_assessments")
    op.drop_constraint(
        "fk_governance_assessments_input_assessment_id",
        "governance_assessments",
        type_="foreignkey",
    )
    op.drop_column("governance_assessments", "evaluated_text_redacted")
    op.drop_column("governance_assessments", "evaluated_text")
    op.drop_column("governance_assessments", "input_assessment_id")
    op.drop_column("governance_assessments", "assessment_phase")