"""Credit grant-to-reservation allocations (ADR-053).

Revision ID: 0013_grant_allocation
Revises: 0012_plan_entitlements
Create Date: 2026-10-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_grant_allocation"
down_revision: str | None = "0012_plan_entitlements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("credit_grants", sa.Column("reserved_amount", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.create_check_constraint("ck_credit_grants_reserved_nonnegative", "credit_grants", "reserved_amount >= 0")
    op.create_check_constraint(
        "ck_credit_grants_reserved_le_remaining", "credit_grants",
        "reserved_amount <= remaining_amount",
    )

    op.create_table(
        "reservation_credit_allocations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("allocated_amount", sa.Integer(), nullable=False),
        sa.Column("consumed_amount", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("released_amount", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("voided_amount", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="RESTRICT", name="fk_allocations_reservation_id"),
        sa.ForeignKeyConstraint(["grant_id"], ["credit_grants.id"], ondelete="RESTRICT", name="fk_allocations_grant_id"),
        sa.CheckConstraint("allocated_amount > 0", name="ck_allocations_allocated_positive"),
        sa.CheckConstraint("consumed_amount >= 0", name="ck_allocations_consumed_nonnegative"),
        sa.CheckConstraint("released_amount >= 0", name="ck_allocations_released_nonnegative"),
        sa.CheckConstraint("voided_amount >= 0", name="ck_allocations_voided_nonnegative"),
        sa.CheckConstraint(
            "consumed_amount + released_amount + voided_amount <= allocated_amount",
            name="ck_allocations_sum_le_allocated",
        ),
        sa.CheckConstraint("status IN ('active','consumed','released','voided')", name="ck_allocations_status_valid"),
        sa.UniqueConstraint("reservation_id", "grant_id", name="uq_allocations_reservation_grant"),
    )
    op.create_index("ix_allocations_grant", "reservation_credit_allocations", ["grant_id"])
    op.create_index("ix_allocations_reservation", "reservation_credit_allocations", ["reservation_id"])


def downgrade() -> None:
    """forward-only (هم‌سبک 0012): رد پیش از هر DDL.

    0013 تاریخچهٔ تخصیص (allocations) و reserved_amount را نگه می‌دارد؛
    بدون محافظت، downgrade آن‌ها را نابود می‌کند.
    """
    raise RuntimeError(
        "migration 0013 is forward-only (C2-03): downgrade is rejected before any DDL "
        "because it would destroy reservation grant-allocation history."
    )
