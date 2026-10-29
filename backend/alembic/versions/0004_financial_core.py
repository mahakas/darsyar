"""Create financial core: credit_accounts, credit_ledger, reservations (slice A, ADR-035).

Revision ID: 0004_financial_core
Revises: 0003_users_otp_refresh_audit
Create Date: 2026-10-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_financial_core"
down_revision: str | None = "0003_users_otp_refresh_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credit_accounts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("available_balance", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_credit_accounts_user_id"),
        sa.CheckConstraint("available_balance >= 0", name="ck_credit_accounts_balance_nonnegative"),
    )
    op.create_index("uq_credit_accounts_user_id", "credit_accounts", ["user_id"], unique=True)

    op.create_table(
        "reservations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_reservations_user_id"),
        sa.CheckConstraint("kind IN ('credit', 'unlimited')", name="ck_reservations_kind_valid"),
        sa.CheckConstraint(
            "(kind = 'credit' AND amount > 0) OR (kind = 'unlimited' AND amount = 0)",
            name="ck_reservations_amount_by_kind",
        ),
        sa.CheckConstraint("status IN ('pending', 'settled', 'released')", name="ck_reservations_status_valid"),
        sa.CheckConstraint(
            "(status = 'settled') = (settled_at IS NOT NULL)",
            name="ck_reservations_settled_at_consistent",
        ),
        sa.CheckConstraint(
            "(status = 'released') = (released_at IS NOT NULL)",
            name="ck_reservations_released_at_consistent",
        ),
        sa.CheckConstraint(
            "settled_at IS NULL OR released_at IS NULL",
            name="ck_reservations_terminal_exclusive",
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_reservations_user_key"),
    )
    op.create_index("ix_reservations_status_created", "reservations", ["status", "created_at"])
    op.create_index("ix_reservations_user_id", "reservations", ["user_id"])

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_credit_ledger_user_id"),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["reservations.id"], ondelete="RESTRICT", name="fk_credit_ledger_reservation_id"
        ),
        sa.CheckConstraint("kind IN ('free_grant', 'plan_grant', 'spend', 'refund', 'adjust', 'unlimited_usage')", name="ck_credit_ledger_kind_valid"),
        sa.CheckConstraint(
            "(kind = 'spend' AND amount < 0) OR (kind = 'unlimited_usage' AND amount = 0) OR (kind <> 'spend' AND kind <> 'unlimited_usage' AND amount <> 0)",
            name="ck_credit_ledger_amount_sign",
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_credit_ledger_user_key"),
    )
    op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])
    op.create_index("ix_credit_ledger_reservation_id", "credit_ledger", ["reservation_id"])

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION guard_reservation_terminal_transitions()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.status IN ('settled', 'released') AND NEW.status IS DISTINCT FROM OLD.status THEN
                    RAISE EXCEPTION 'reservation_terminal_transition_blocked';
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
            CREATE TRIGGER trg_reservations_block_terminal_transition
            BEFORE UPDATE ON reservations
            FOR EACH ROW
            EXECUTE FUNCTION guard_reservation_terminal_transitions();
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_reservations_block_terminal_transition ON reservations"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS guard_reservation_terminal_transitions()"))
    op.drop_table("credit_ledger")
    op.drop_table("reservations")
    op.drop_table("credit_accounts")
