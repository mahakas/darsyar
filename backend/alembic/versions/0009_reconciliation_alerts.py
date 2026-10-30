"""Create reconciliation_alerts with partial-unique active identity — Slice C-1.

Revision ID: 0009_reconciliation_alerts
Revises: 0008_usage_events
Create Date: 2026-10-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_reconciliation_alerts"
down_revision: str | None = "0008_usage_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_alerts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("context", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("alert_hash", sa.String(length=64), nullable=False),
        sa.Column("occurrences", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL", name="fk_reconciliation_alerts_user_id"),
        sa.CheckConstraint("severity IN ('warning', 'critical')", name="ck_reconciliation_alerts_severity_valid"),
        sa.CheckConstraint("occurrences >= 1", name="ck_reconciliation_alerts_occurrences_positive"),
    )
    op.create_index(
        "uq_reconciliation_alerts_active",
        "reconciliation_alerts",
        ["user_id", "alert_type", "alert_hash"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    op.create_index("ix_reconciliation_alerts_type_resolved", "reconciliation_alerts", ["alert_type", "resolved_at"])


def downgrade() -> None:
    op.drop_table("reconciliation_alerts")
