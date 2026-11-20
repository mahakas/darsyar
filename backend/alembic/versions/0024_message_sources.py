"""Persist safe citation strings on assistant messages for SSE replay.

Revision ID: 0024_message_sources
Revises: 0023_admin_audit_append_only
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_message_sources"
down_revision: str | None = "0023_admin_audit_append_only"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "sources_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "sources_json")
