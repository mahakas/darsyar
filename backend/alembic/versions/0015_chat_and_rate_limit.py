"""Chat conversations/messages + degraded-mode rate-limit counters (Phase 3).

Revision ID: 0015_chat_and_rate_limit
Revises: 0014_grant_lifecycle_reason
Create Date: 2026-11-07

- `conversations` / `messages`: chat persistence with ownership-safe querying.
- `rate_limit_counters`: bounded PostgreSQL-backed fallback limiter used only when
  Redis is unavailable (OQ-006/R-115). It is a rate/HTTP-admission counter,
  intentionally separate from the financial ledger.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_chat_and_rate_limit"
down_revision: str | None = "0014_grant_lifecycle_reason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_conversations_user_id"),
    )
    op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'streaming'"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("sequence", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("client_request_id", sa.String(length=128), nullable=True),
        sa.Column("provider_request_id", sa.String(length=128), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="RESTRICT", name="fk_messages_conversation_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_messages_user_id"),
        sa.CheckConstraint("role IN ('user','assistant','system')", name="ck_messages_role_valid"),
        sa.CheckConstraint("status IN ('streaming','partial','completed','failed','cancelled')", name="ck_messages_status_valid"),
    )
    op.create_index("ix_messages_conv_sequence", "messages", ["conversation_id", "sequence"])
    op.create_index("ix_messages_user_created", "messages", ["user_id", "created_at"])
    op.create_index(
        "uq_messages_conv_client_request",
        "messages",
        ["conversation_id", "client_request_id"],
        unique=True,
        postgresql_where=sa.text("client_request_id IS NOT NULL"),
    )

    op.create_table(
        "rate_limit_counters",
        sa.Column("key", sa.String(length=256), nullable=False),
        sa.Column("count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_counters")
    op.drop_table("messages")
    op.drop_table("conversations")
