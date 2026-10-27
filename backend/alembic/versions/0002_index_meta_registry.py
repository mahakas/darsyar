"""Create index_meta registry table (R-087).

Revision ID: 0002_index_meta_registry
Revises: 0001_enable_vector_and_trgm
Create Date: 2026-10-27
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_index_meta_registry"
down_revision: str | None = "0001_enable_vector_and_trgm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "index_meta",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("distance_metric", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("embedding_dim > 0", name="ck_index_meta_embedding_dim_positive"),
    )
    op.create_index(
        "uq_index_meta_active",
        "index_meta",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_index_meta_active", table_name="index_meta")
    op.drop_table("index_meta")
