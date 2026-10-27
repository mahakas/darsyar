"""Enable PostgreSQL extensions used by Darsyar.

Revision ID: 0001_enable_vector_and_trgm
Revises:
Create Date: 2026-10-27
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_vector_and_trgm"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensions are idempotent. Extension creation should be reviewed for hosted DB privileges.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    # Do not drop shared extensions during app rollback; other applications may rely on them.
    pass
