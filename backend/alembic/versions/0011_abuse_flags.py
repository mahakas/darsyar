"""Create abuse_flags for Fair-Use policy (ADR-050) — Slice C-2B.

Revision ID: 0011_abuse_flags
Revises: 0010_free_grant_partial_unique
Create Date: 2026-10-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_abuse_flags"
down_revision: str | None = "0010_free_grant_partial_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "abuse_flags",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("period_key", sa.String(length=7), nullable=False),
        sa.Column("observed_count", sa.Integer(), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolution_reason", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_abuse_flags_user_id"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL", name="fk_abuse_flags_resolved_by"),
        sa.CheckConstraint("period_key ~ '^[0-9]{4}-[0-9]{2}$'", name="ck_abuse_flags_period_key_format"),
        sa.CheckConstraint("observed_count >= 0", name="ck_abuse_flags_observed_count_nonnegative"),
        sa.CheckConstraint("threshold > 0", name="ck_abuse_flags_threshold_positive"),
        sa.CheckConstraint("status IN ('active', 'resolved')", name="ck_abuse_flags_status_valid"),
        sa.CheckConstraint(
            "(status = 'resolved') = (resolved_at IS NOT NULL)",
            name="ck_abuse_flags_resolved_consistent",
        ),
        sa.CheckConstraint(
            "status <> 'active' OR (resolved_by IS NULL AND resolution_reason IS NULL)",
            name="ck_abuse_flags_active_no_resolution_meta",
        ),
        sa.UniqueConstraint("user_id", "period_key", name="uq_abuse_flags_user_period"),
    )
    op.create_index("ix_abuse_flags_user_period", "abuse_flags", ["user_id", "period_key"])
    op.create_index("ix_abuse_flags_status_created", "abuse_flags", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("abuse_flags")
