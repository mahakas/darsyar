"""Phase 4: ingestion chunks table (R-150/R-158/R-087).

Revision ID: 0020_ingestion_chunks
Revises: 0019_outbox_job_fk_restrict

Creates `ingestion_chunks` (parent/child, vector column, metadata). Heavy
CONCURRENTLY indexes (HNSW on embedding, GIN on normalized content) are created
in a follow-up revision 0021 to keep this DDL transactional and avoid long locks
(R-082).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0020_ingestion_chunks"
down_revision: str | None = "0019_outbox_job_fk_restrict"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_chunks",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("is_parent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_normalized", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("grade_level", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("edition_year", sa.Integer(), nullable=False),
        sa.Column("chapter", sa.String(length=255), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=16), server_default=sa.text("'textbook'"), nullable=False),
        sa.Column("source_origin", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("is_valid", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("grade_level BETWEEN 1 AND 12", name="ck_ingestion_chunks_grade"),
        sa.CheckConstraint("edition_year > 0", name="ck_ingestion_chunks_edition_year"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_ingestion_chunks_index_nonneg"),
        sa.CheckConstraint("source_type IN ('textbook','image','web','synthetic')", name="ck_ingestion_chunks_source_type"),
        sa.ForeignKeyConstraint(["document_id"], ["ingestion_documents.id"], ondelete="CASCADE", name="fk_ingestion_chunks_document"),
        sa.ForeignKeyConstraint(["parent_id"], ["ingestion_chunks.id"], ondelete="CASCADE", name="fk_ingestion_chunks_parent"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_ingestion_chunks_doc_index"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_chunks")
