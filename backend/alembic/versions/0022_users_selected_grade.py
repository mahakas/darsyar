"""Add nullable, explicitly selected student grade to users (R-019).

Revision ID: 0022_users_selected_grade
Revises: 0021_ingestion_chunks_indexes

Existing accounts remain unselected; no default or historical grade is inferred.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_users_selected_grade"
down_revision: str | None = "0021_ingestion_chunks_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("selected_grade", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_users_selected_grade",
        "users",
        "selected_grade IS NULL OR selected_grade BETWEEN 1 AND 12",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_selected_grade", "users", type_="check")
    op.drop_column("users", "selected_grade")
