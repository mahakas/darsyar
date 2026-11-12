"""Active embedding-index registry enforcement (R-087/R-088/R-089).

No ingestion/indexing/query path may proceed without exactly one active registry
entry. The current physical pgvector column and HNSW operator class are fixed to
1024-dimensional cosine vectors; changing either requires a schema/index migration
and the separately governed reindex procedure.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.index_meta import IndexMeta

VECTOR_COLUMN_DIMENSION = 1024
SUPPORTED_DISTANCE_METRIC = "cosine"


async def require_active_index_meta(
    session: AsyncSession, *, lock_for_share: bool = False
) -> IndexMeta:
    """Return the single active index row or fail closed.

    Indexing can request a PostgreSQL SHARE lock so the active model cannot be
    changed by a concurrent registry update before the caller commits its chunks.
    """
    statement = select(IndexMeta).where(IndexMeta.is_active.is_(True))
    if lock_for_share:
        statement = statement.with_for_update(read=True)
    try:
        metadata = (await session.execute(statement)).scalar_one_or_none()
    except MultipleResultsFound as exc:
        raise AppError(
            "active_embedding_index_ambiguous",
            503,
            "رجیستری ایندکس فعال بیش از یک رکورد دارد.",
        ) from exc

    if metadata is None:
        raise AppError(
            "active_embedding_index_missing",
            503,
            "ایندکس embedding فعال پیکربندی نشده است.",
        )
    if not metadata.embedding_model.strip():
        raise AppError("active_embedding_model_invalid", 503, "مدل embedding فعال نامعتبر است.")
    if metadata.embedding_dim != VECTOR_COLUMN_DIMENSION:
        raise AppError(
            "active_embedding_dimension_unsupported",
            503,
            "ابعاد ایندکس فعال با ستون برداری فعلی سازگار نیست.",
        )
    if metadata.distance_metric.lower() != SUPPORTED_DISTANCE_METRIC:
        raise AppError(
            "active_embedding_metric_unsupported",
            503,
            "معیار فاصلهٔ ایندکس فعال با ایندکس فیزیکی سازگار نیست.",
        )
    return metadata


def validate_embedding_provider(
    metadata: IndexMeta, *, model: str, dimension: int
) -> None:
    """Ensure the configured provider exactly matches the active index contract."""
    if model != metadata.embedding_model:
        raise AppError(
            "embedding_model_registry_mismatch",
            503,
            "مدل embedding provider با رجیستری ایندکس فعال یکسان نیست.",
        )
    if dimension != metadata.embedding_dim:
        raise AppError(
            "embedding_dimension_registry_mismatch",
            503,
            "ابعاد embedding provider با رجیستری ایندکس فعال یکسان نیست.",
        )
