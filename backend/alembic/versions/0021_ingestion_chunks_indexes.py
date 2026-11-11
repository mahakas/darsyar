"""Phase 4: heavy vector/lexical indexes (R-081/R-082/R-165).

Revision ID: 0021_ingestion_chunks_indexes
Revises: 0020_ingestion_chunks

Creates `ingestion_chunks` heavy indexes CONCURRENTLY in autocommit blocks:
- HNSW on `embedding` (pgvector, cosine)
- GIN on `content_normalized` (pg_trgm, trigram)
- B-tree on `(grade_level, subject, edition_year)` for the SQL grade filter
These run outside a transaction (CREATE INDEX CONCURRENTLY). Downgrade drops them.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0021_ingestion_chunks_indexes"
down_revision: str | None = "0020_ingestion_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("COMMIT")  # ensure we are outside a transaction for CONCURRENTLY
    op.execute(
        "CREATE INDEX CONCURRENTLY ix_ingestion_chunks_embedding "
        "ON ingestion_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("COMMIT")
    op.execute(
        "CREATE INDEX CONCURRENTLY ix_ingestion_chunks_trgm "
        "ON ingestion_chunks USING gin (content_normalized gin_trgm_ops)"
    )
    op.execute("COMMIT")
    op.execute(
        "CREATE INDEX CONCURRENTLY ix_ingestion_chunks_grade_filter "
        "ON ingestion_chunks (grade_level, subject, edition_year)"
    )
    op.execute("COMMIT")


def downgrade() -> None:
    op.execute("COMMIT")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_ingestion_chunks_grade_filter")
    op.execute("COMMIT")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_ingestion_chunks_trgm")
    op.execute("COMMIT")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_ingestion_chunks_embedding")
    op.execute("COMMIT")
