"""Phase 4: idempotent chunk indexing (R-087/R-088/R-157/R-079).

Creates/updates child+parent chunks for a document with their embeddings in one
transaction. Idempotent per (document_id, chunk_index): a rerun replaces the
document's chunks atomically rather than duplicating them. Embedding vectors are
stored via pgvector.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_chunk import IngestionChunk
from app.models.ingestion_document import IngestionDocument
from app.services.ingestion.chunking import ChunkingResult
from app.services.ingestion.normalize import normalize_persian


@dataclass(frozen=True)
class IndexResult:
    document_id: uuid.UUID
    children_indexed: int
    parents_indexed: int
    replaced: bool


async def index_document_chunks(
    session: AsyncSession,
    *,
    document: IngestionDocument,
    chunking: ChunkingResult,
    child_vectors: list[list[float]],
    parent_vectors: list[list[float]],
    title: str | None = None,
    source_origin: str | None = None,
    source_type: str = "textbook",
    chapter: str | None = None,
) -> IndexResult:
    """Atomically replace a document's chunks with new ones (idempotent)."""
    existing = (await session.execute(select(IngestionChunk.id).where(IngestionChunk.document_id == document.id))).all()
    replaced = len(existing) > 0

    if replaced:
        await session.execute(delete(IngestionChunk).where(IngestionChunk.document_id == document.id))
        await session.flush()

    if len(child_vectors) != len(chunking.children):
        raise ValueError("child vectors/chunk count mismatch")
    if len(parent_vectors) != len(chunking.parents):
        raise ValueError("parent vectors/chunk count mismatch")

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
        # Link every child covered by this parent, not only the first child.
        for child_index in range(parent.child_start, parent.child_end + 1):
            parent_ids[child_index] = chunk.id

    child_base = len(chunking.parents)
    for idx, child in enumerate(chunking.children):
        chunk = IngestionChunk(
            document_id=document.id,
            parent_id=parent_ids.get(child.order_index),
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
