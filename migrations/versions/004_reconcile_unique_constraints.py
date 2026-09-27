"""Migration 004 - Reconcile unique constraints to match ORM index declarations.
Converts standalone PostgreSQL UNIQUE CONSTRAINT objects on
policies.policy_code and risk_assessments.assessment_id into named unique
indexes so alembic check reports a clean diff.
Revision ID: 004
Revises: 003
Create Date: 2026-09-27
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    # policies.policy_code
    op.drop_constraint("policies_policy_code_key", "policies", type_="unique")
    op.drop_index("ix_policies_policy_code", table_name="policies")
    op.create_index("ix_policies_policy_code", "policies", ["policy_code"], unique=True)
    # risk_assessments.assessment_id
    op.drop_constraint("risk_assessments_assessment_id_key", "risk_assessments", type_="unique")
    op.create_index(
        "ix_risk_assessments_assessment_id",
        "risk_assessments",
        ["assessment_id"],
        unique=True,
    )
def downgrade() -> None:
    op.drop_index("ix_risk_assessments_assessment_id", table_name="risk_assessments")
    op.create_unique_constraint(
        "risk_assessments_assessment_id_key", "risk_assessments", ["assessment_id"]
    )
    op.drop_index("ix_policies_policy_code", table_name="policies")
    op.create_index("ix_policies_policy_code", "policies", ["policy_code"], unique=False)
    op.create_unique_constraint("policies_policy_code_key", "policies", ["policy_code"])