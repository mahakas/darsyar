"""Link chat assistant messages to reservations (Phase 3 Slice C/D).

Revision ID: 0016_chat_reservation_link
Revises: 0015_chat_and_rate_limit
Create Date: 2026-11-07

Adds `messages.reservation_id` so a logical chat request maps 1:1 to a financial
reservation. A partial unique index guarantees at most one assistant message per
reservation, which serializes concurrent/duplicate requests and prevents a second
provider invocation or a second settlement for the same request.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_chat_reservation_link"
down_revision: str | None = "0015_chat_and_rate_limit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("reservation_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_messages_reservation_id",
        "messages",
        "reservations",
        ["reservation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_messages_reservation",
        "messages",
        ["reservation_id"],
        unique=True,
        postgresql_where=sa.text("reservation_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_messages_reservation", table_name="messages")
    op.drop_constraint("fk_messages_reservation_id", "messages", type_="foreignkey")
    op.drop_column("messages", "reservation_id")
