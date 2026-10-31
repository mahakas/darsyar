"""Add partial unique index for one-time free grant per user (ADR-048).

Revision ID: 0010_free_grant_partial_unique
Revises: 0009_reconciliation_alerts
Create Date: 2026-10-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_free_grant_partial_unique"
down_revision: str | None = "0009_reconciliation_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_credit_ledger_free_grant_once",
        "credit_ledger",
        ["user_id", "kind"],
        unique=True,
        postgresql_where=sa.text("kind = 'free_grant'"),
    )


def downgrade() -> None:
    op.drop_index("uq_credit_ledger_free_grant_once", table_name="credit_ledger")
