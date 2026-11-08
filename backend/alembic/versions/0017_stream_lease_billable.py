"""Stream lease/heartbeat + billable evidence for durable recovery (Phase 3).

Revision ID: 0017_stream_lease_billable
Revises: 0016_chat_reservation_link
Create Date: 2026-11-08

Columns on `messages`:
- `heartbeat_at`: آخرین ضربان Stream فعال (مستقل از تولید Token).
- `stream_owner_token`: نشانگر مالکیت برای fencing Stream قدیمی.
- `billable_output_seen`: آیا خروجی billable دیده شده است (برای نگاشت released→partial).
- `stream_terminated`: نشانگر پایان قطعی Stream (پس از recovery/finalize).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_stream_lease_billable"
down_revision: str | None = "0016_chat_reservation_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("messages", sa.Column("stream_owner_token", sa.String(length=64), nullable=True))
    op.add_column(
        "messages",
        sa.Column("billable_output_seen", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "messages",
        sa.Column("stream_terminated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "ix_messages_streaming_lease",
        "messages",
        ["heartbeat_at"],
        postgresql_where=sa.text("status = 'streaming' AND reservation_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_messages_streaming_lease", table_name="messages")
    op.drop_column("messages", "stream_terminated")
    op.drop_column("messages", "billable_output_seen")
    op.drop_column("messages", "stream_owner_token")
    op.drop_column("messages", "heartbeat_at")
