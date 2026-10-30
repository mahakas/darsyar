"""Create usage_events (append-only) — Slice C-1.

Revision ID: 0008_usage_events
Revises: 0007_product_catalog
Create Date: 2026-10-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_usage_events"
down_revision: str | None = "0007_product_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=True),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("estimated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_usage_events_user_id"),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["reservations.id"], ondelete="RESTRICT", name="fk_usage_events_reservation_id"
        ),
        sa.CheckConstraint("token_count >= 0", name="ck_usage_events_token_count_nonnegative"),
        sa.UniqueConstraint("user_id", "event_key", name="uq_usage_events_user_key"),
    )
    op.create_index("ix_usage_events_user_created", "usage_events", ["user_id", "created_at"])

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION guard_usage_events_immutable()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'usage_events_immutable';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_usage_events_block_mutation
            BEFORE UPDATE OR DELETE ON usage_events
            FOR EACH ROW
            EXECUTE FUNCTION guard_usage_events_immutable();
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_usage_events_block_mutation ON usage_events"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS guard_usage_events_immutable()"))
    op.drop_table("usage_events")
