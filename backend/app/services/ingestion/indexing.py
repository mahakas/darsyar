"""Phase 4: registry-bound, idempotent chunk indexing (R-087/R-088/R-157/R-079).

The active index_meta row is mandatory and locked for share while chunks are
written. Embedding model/dimension, vector values and parent-child ranges are
validated before existing chunks are deleted, so a rejected replacement leaves
the previous indexed representation intact when the caller rolls back normally.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.ingestion_chunk import IngestionChunk
from app.models.ingestion_document import IngestionDocument
from app.services.ingestion.chunking import ChunkingResult
from app.services.ingestion.index_registry import require_active_index_meta, validate_embedding_provider
from app.services.ingestion.normalize import normalize_persian


@dataclass(frozen=True)
class IndexResult:
    document_id: uuid.UUID
    children_indexed: int
    parents_indexed: int
    replaced: bool


def _validate_chunk_ranges(chunking: ChunkingResult) -> None:
    if not chunking.children or not chunking.parents:
        raise AppError("empty_extraction", 422, "متن کافی برای ساخت chunk وجود ندارد.")
    covered: list[int] = []
    for parent in chunking.parents:
        if (
            parent.child_start < 0
            or parent.child_end < parent.child_start
            or parent.child_end >= len(chunking.children)
        ):
            raise AppError("invalid_parent_child_range", 422, "بازهٔ chunk والد/فرزند نامعتبر است.")
        covered.extend(range(parent.child_start, parent.child_end + 1))
    if sorted(covered) != list(range(len(chunking.children))):
        raise AppError(
            "invalid_parent_child_coverage",
            422,
            "تمام chunkهای فرزند باید دقیقاً زیر یک والد قرار بگیرند.",
        )


def _validate_vectors(vectors: list[list[float]], *, expected_count: int, dimension: int) -> None:
    if len(vectors) != expected_count:
        raise AppError("embedding_vector_count_mismatch", 422, "تعداد بردارهای embedding با chunkها برابر نیست.")
    for vector in vectors:
        if len(vector) != dimension:
            raise AppError("embedding_dim_mismatch", 422, "ابعاد بردار با رجیستری ایندکس فعال ناسازگار است.")
        if any(not math.isfinite(value) for value in vector):
            raise AppError("embedding_non_finite", 422, "بردار embedding حاوی NaN/Inf است.")


async def index_document_chunks(
    session: AsyncSession,
    *,
    document: IngestionDocument,
    chunking: ChunkingResult,
    child_vectors: list[list[float]],
    parent_vectors: list[list[float]],
    embedding_model: str,
    title: str | None = None,
    source_origin: str | None = None,
    source_type: str = "textbook",
    chapter: str | None = None,
) -> IndexResult:
    """Replace a document's child/parent chunks under the active registry contract."""
    active_index = await require_active_index_meta(session, lock_for_share=True)
    validate_embedding_provider(
        active_index,
        model=embedding_model,
        dimension=active_index.embedding_dim,
    )
    _validate_chunk_ranges(chunking)
    _validate_vectors(
        child_vectors,
        expected_count=len(chunking.children),
        dimension=active_index.embedding_dim,
    )
    _validate_vectors(
        parent_vectors,
        expected_count=len(chunking.parents),
        dimension=active_index.embedding_dim,
    )

    existing = (
        await session.execute(
            select(IngestionChunk.id).where(IngestionChunk.document_id == document.id)
        )
    ).all()
    replaced = len(existing) > 0

    # All policy/contract checks are complete before deleting the old representation.
    if replaced:
        await session.execute(delete(IngestionChunk).where(IngestionChunk.document_id == document.id))
        await session.flush()

    parent_ids: dict[int, uuid.UUID] = {}
    for idx, parent in enumerate(chunking.parents):
        chunk = IngestionChunk(
            document_id=document.id,
            parent_id=None,
            chunk_index=idx,
            is_parent=True,
            content=parent.text,
            content_normalized=normalize_persian(parent.text),
            embedding=parent_vectors[idx],
            grade_level=document.grade_level,
            subject=document.subject,
            edition_year=document.edition_year,
            chapter=chapter,
            page_number=parent.page_number,
            title=title,
            source_type=source_type,
            source_origin=source_origin,
            is_valid=True,
        )
        session.add(chunk)
        await session.flush()
        for child_index in range(parent.child_start, parent.child_end + 1):
            parent_ids[child_index] = chunk.id

    child_base = len(chunking.parents)
    for idx, child in enumerate(chunking.children):
        chunk = IngestionChunk(
            document_id=document.id,
            parent_id=parent_ids[child.order_index],
            chunk_index=child_base + idx,
            is_parent=False,
            content=child.text,
            content_normalized=normalize_persian(child.text),
            embedding=child_vectors[idx],
            grade_level=document.grade_level,
            subject=document.subject,
            edition_year=document.edition_year,
            chapter=chapter,
            page_number=child.page_number,
            title=title,
            source_type=source_type,
            source_origin=source_origin,
            is_valid=True,
        )
        session.add(chunk)

    await session.flush()
    return IndexResult(
        document_id=document.id,
        children_indexed=len(chunking.children),
        parents_indexed=len(chunking.parents),
        replaced=replaced,
    )
