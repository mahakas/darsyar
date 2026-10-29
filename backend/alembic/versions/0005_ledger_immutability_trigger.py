"""Enforce credit_ledger append-only invariance at the database level (hardening).

Revision ID: 0005_ledger_immutability_trigger
Revises: 0004_financial_core
Create Date: 2026-10-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ledger_immutability_trigger"
down_revision: str | None = "0004_financial_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION guard_credit_ledger_immutable()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'credit_ledger_immutable';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_credit_ledger_block_mutation
            BEFORE UPDATE OR DELETE ON credit_ledger
            FOR EACH ROW
            EXECUTE FUNCTION guard_credit_ledger_immutable();
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_credit_ledger_block_mutation ON credit_ledger"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS guard_credit_ledger_immutable()"))
