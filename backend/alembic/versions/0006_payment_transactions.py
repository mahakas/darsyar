"""Create payment_transactions (slice B, ADR-047).

Revision ID: 0006_payment_transactions
Revises: 0005_ledger_immutability_trigger
Create Date: 2026-10-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_payment_transactions"
down_revision: str | None = "0005_ledger_immutability_trigger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("amount_toman", sa.Integer(), nullable=False),
        sa.Column("credit_grant", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default=sa.text("'zarinpal'"), nullable=False),
        sa.Column("provider_currency", sa.String(length=8), server_default=sa.text("'IRR'"), nullable=False),
        sa.Column("provider_amount", sa.Integer(), nullable=False),
        sa.Column("authority", sa.String(length=64), nullable=True),
        sa.Column("ref_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), server_default=sa.text("'created'"), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_payment_transactions_user_id"),
        sa.CheckConstraint("amount_toman > 0", name="ck_payment_transactions_amount_positive"),
        sa.CheckConstraint("credit_grant > 0", name="ck_payment_transactions_grant_positive"),
        sa.CheckConstraint("provider_amount > 0", name="ck_payment_transactions_provider_amount_positive"),
        sa.CheckConstraint(
            "status IN ('created', 'requesting', 'pending', 'succeeded', 'failed', 'unknown_outcome')",
            name="ck_payment_transactions_status_valid",
        ),
        sa.CheckConstraint(
            "(status = 'succeeded') = (succeeded_at IS NOT NULL)",
            name="ck_payment_transactions_succeeded_at_consistent",
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_payment_transactions_user_key"),
    )
    op.create_index("ix_payment_transactions_user_id", "payment_transactions", ["user_id"])
    op.create_index(
        "uq_payment_transactions_authority",
        "payment_transactions",
        ["authority"],
        unique=True,
        postgresql_where=sa.text("authority IS NOT NULL"),
    )
    op.create_index("ix_payment_transactions_status_created", "payment_transactions", ["status", "created_at"])

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION guard_payment_terminal_transitions()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.status IN ('succeeded', 'failed') AND NEW.status IS DISTINCT FROM OLD.status THEN
                    RAISE EXCEPTION 'payment_terminal_transition_blocked';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_payments_block_terminal_transition
            BEFORE UPDATE ON payment_transactions
            FOR EACH ROW
            EXECUTE FUNCTION guard_payment_terminal_transitions();
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_payments_block_terminal_transition ON payment_transactions"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS guard_payment_terminal_transitions()"))
    op.drop_table("payment_transactions")
