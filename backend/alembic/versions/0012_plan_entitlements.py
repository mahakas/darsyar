"""Plan entitlements, credit grants, cancellation & refund records (ADR-052).

Revision ID: 0012_plan_entitlements
Revises: 0011_abuse_flags
Create Date: 2026-10-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_plan_entitlements"
down_revision: str | None = "0011_abuse_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payment_transactions", sa.Column("plan_type", sa.String(length=16), server_default=sa.text("'credit'"), nullable=False))
    op.add_column("payment_transactions", sa.Column("duration_days", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_payment_transactions_plan_type_valid", "payment_transactions", "plan_type IN ('credit','unlimited')")
    op.drop_constraint("ck_payment_transactions_grant_positive", "payment_transactions")
    op.create_check_constraint(
        "ck_payment_transactions_credit_grant_valid", "payment_transactions",
        "(plan_type = 'unlimited' AND credit_grant = 0) OR (plan_type = 'credit' AND credit_grant > 0)",
    )

    op.add_column("product_catalog", sa.Column("plan_type", sa.String(length=16), server_default=sa.text("'credit'"), nullable=False))
    op.add_column("product_catalog", sa.Column("duration_days", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE product_catalog SET plan_type = 'credit', duration_days = 30 WHERE product_id IN ('basic','pro')"
        )
    )
    op.execute(sa.text("ALTER TABLE product_catalog ALTER COLUMN duration_days SET NOT NULL"))
    op.drop_constraint("ck_product_catalog_grant_positive", "product_catalog")
    op.execute(
        sa.text(
            """
            INSERT INTO product_catalog (product_id, price_toman, credit_grant, active, plan_type, duration_days)
            VALUES ('unlimited', 1500000, 0, true, 'unlimited', 30)
            ON CONFLICT (product_id) DO NOTHING;
            """
        )
    )
    op.create_check_constraint("ck_product_catalog_plan_type_valid", "product_catalog", "plan_type IN ('credit','unlimited')")
    op.create_check_constraint("ck_product_catalog_duration_positive", "product_catalog", "duration_days > 0")
    op.create_check_constraint(
        "ck_product_catalog_credit_plan_type", "product_catalog",
        "(plan_type = 'unlimited' AND credit_grant = 0) OR (plan_type = 'credit' AND credit_grant > 0)",
    )

    op.create_table(
        "plan_entitlements",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("plan_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_credits", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("remaining_credits", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Uuid(), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_plan_entitlements_user_id"),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="RESTRICT", name="fk_plan_entitlements_payment_id"),
        sa.CheckConstraint("status IN ('active','expired','cancelled')", name="ck_plan_entitlements_status_valid"),
        sa.CheckConstraint("granted_credits >= 0", name="ck_plan_entitlements_granted_nonnegative"),
        sa.CheckConstraint("remaining_credits >= 0", name="ck_plan_entitlements_remaining_nonnegative"),
        sa.CheckConstraint(
            "(plan_type = 'unlimited' AND granted_credits = 0) OR (plan_type = 'credit' AND granted_credits > 0)",
            name="ck_plan_entitlements_credit_plan_type",
        ),
        sa.UniqueConstraint("payment_id", name="uq_plan_entitlements_payment_id"),
    )
    op.create_index("ix_plan_entitlements_user_product_status", "plan_entitlements", ["user_id", "product_id", "status"])
    op.create_index("ix_plan_entitlements_expires", "plan_entitlements", ["expires_at"])

    op.create_table(
        "credit_grants",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("original_amount", sa.Integer(), nullable=False),
        sa.Column("remaining_amount", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_credit_grants_user_id"),
        sa.ForeignKeyConstraint(["entitlement_id"], ["plan_entitlements.id"], ondelete="RESTRICT", name="fk_credit_grants_entitlement_id"),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="RESTRICT", name="fk_credit_grants_payment_id"),
        sa.CheckConstraint("original_amount > 0", name="ck_credit_grants_original_positive"),
        sa.CheckConstraint("remaining_amount >= 0", name="ck_credit_grants_remaining_nonnegative"),
        sa.CheckConstraint("remaining_amount <= original_amount", name="ck_credit_grants_remaining_le_original"),
    )
    op.create_index("ix_credit_grants_user_expires", "credit_grants", ["user_id", "expires_at"])

    op.create_table(
        "cancellation_requests",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decision_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_cancellation_requests_user_id"),
        sa.ForeignKeyConstraint(["entitlement_id"], ["plan_entitlements.id"], ondelete="RESTRICT", name="fk_cancellation_requests_entitlement_id"),
        sa.CheckConstraint("status IN ('pending','withdrawn','approved','rejected')", name="ck_cancellation_requests_status_valid"),
        sa.CheckConstraint("mode IN ('preserve_until_expiry','immediate')", name="ck_cancellation_requests_mode_valid"),
    )
    op.create_index("ix_cancellation_requests_user_status", "cancellation_requests", ["user_id", "status"])

    op.create_table(
        "refund_records",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("requested_amount", sa.Integer(), nullable=False),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_by", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("approved_amount", sa.Integer(), nullable=True),
        sa.Column("credit_voided", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'requested'"), nullable=False),
        sa.Column("provider_settlement_ref", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="RESTRICT", name="fk_refund_records_payment_id"),
        sa.ForeignKeyConstraint(["entitlement_id"], ["plan_entitlements.id"], ondelete="RESTRICT", name="fk_refund_records_entitlement_id"),
        sa.CheckConstraint("requested_amount > 0", name="ck_refund_records_requested_positive"),
        sa.CheckConstraint("credit_voided >= 0", name="ck_refund_records_voided_nonnegative"),
        sa.CheckConstraint(
            "status IN ('requested','approved','rejected','completed')",
            name="ck_refund_records_status_valid",
        ),
    )
    op.create_index("ix_refund_records_payment", "refund_records", ["payment_id"])


def downgrade() -> None:
    """forward-only (Option A): هر تلاش downgrade پیش از هر DDL رد می‌شود.

    مهاجرت 0012 حاوی تاریخچهٔ مالی/تجاری است (entitlementها، grantsها، لغوها،
    بازپرداخت‌ها، snapshotهای plan/duration پرداخت‌ها و پیکربندی کاتالوگ)؛
    بازسازی مطمئن از وضعیت پیش از 0012 قابل اثبات نیست، بنابراین fail-closed انتخاب شد.
    """
    raise RuntimeError(
        "migration 0012 is forward-only (C-01): downgrade is rejected before any DDL "
        "because it would destroy financial/entitlement history and catalog snapshots."
    )
