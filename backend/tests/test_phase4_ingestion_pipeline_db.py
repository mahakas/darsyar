"""Phase 4 integration tests (real PostgreSQL + synthetic data).

Exercises the full ingestion pipeline end-to-end: manifest validation, chunking,
embedding (provider callback), idempotent indexing, hybrid retrieval with grade
ceiling, and provenance/citation integrity. Uses the disposable `darsyar_test`
database; no pilot content.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.ingestion_chunk import IngestionChunk
from app.models.ingestion_document import IngestionDocument
from app.services.ingestion.chunking import chunk_two_level
from app.services.ingestion.embedding_service import embed_batch
from app.services.ingestion.indexing import index_document_chunks
from app.services.ingestion.manifest import validate_manifest
from app.services.ingestion.retrieval import hybrid_retrieve
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)

DIM = 1024  # matches the indexed vector dimension (index_meta/pgvector column)


def _fake_embed_vec(seed: int, dim: int = DIM) -> list[float]:
    import hashlib

    digest = hashlib.sha256(str(seed).encode()).digest()
    # Sparse deterministic vector of `dim` dimensions.
    vec = [0.0] * dim
    for i, b in enumerate(digest):
        vec[i % dim] += b / 255.0
    norm = sum(x * x for x in vec) ** 0.5
    return [x / norm for x in vec]


async def _fake_embed(seed_base: int):
    async def _impl(texts: list[str]) -> list[list[float]]:
        return [_fake_embed_vec(seed_base + i) for i in range(len(texts))]
    return _impl


def _make_manifest(path: str, *, grade: int = 5, subject: str = "math", valid: bool = True) -> dict:
    if not valid:
        return {"path": path, "subject": subject, "grade": grade, "edition_year": 1405}
    return {
        "path": path,
        "subject": subject,
        "grade": grade,
        "edition_year": 1405,
        "title": "کتاب آزمایشی ریاضی",
        "publisher": "سازمان آموزش و پرورش",
        "license_note": "synthetic-test-only",
        "checksum": uuid.uuid4().hex[:64],
    }


@pytest_asyncio.fixture(autouse=True)
async def _clean_chunks() -> None:
    async with SESSION_FACTORY() as s:
        await s.execute(text("TRUNCATE ingestion_chunks, ingestion_documents CASCADE"))
        await s.commit()


async def _seed_document(session, *, grade: int = 5, subject: str = "math") -> IngestionDocument:
    doc = IngestionDocument(checksum=uuid.uuid4().hex[:64], edition_year=1405, subject=subject, grade_level=grade)
    session.add(doc)
    await session.commit()
    return doc


# --- Manifest ---
def test_manifest_valid() -> None:
    m = validate_manifest("unused", manifest=_make_manifest("res.pdf"))
    assert m.grade == 5 and m.subject == "math" and m.license_note == "synthetic-test-only"


def test_manifest_missing_field_fails() -> None:
    with pytest.raises(AppError):
        validate_manifest("unused", manifest=_make_manifest("res.pdf", valid=False))


def test_manifest_invalid_subject_fails() -> None:
    bad = _make_manifest("res.pdf")
    bad["subject"] = "not-a-subject"
    with pytest.raises(AppError):
        validate_manifest("unused", manifest=bad)


def test_manifest_invalid_grade_fails() -> None:
    bad = _make_manifest("res.pdf")
    bad["grade"] = 13
    with pytest.raises(AppError):
        validate_manifest("unused", manifest=bad)


# --- Chunking ---
def test_chunk_two_level_creates_children_and_parents() -> None:
    result = chunk_two_level([
        ("اولین پاراگراف آزمایشی. دومین جمله. " * 20, 1),
        ("پاراگراف دوم در صفحه دو. " * 30, 2),
    ])
    assert len(result.children) >= 2
    assert len(result.parents) >= 1
    assert all(c.page_number in (1, 2) for c in result.children)


def test_chunk_two_level_respects_overlap_and_parent_bounds() -> None:
    segments = [(
        "جمله اول آزمون. جمله دوم آزمون. جمله سوم آزمون. جمله چهارم آزمون. "
        "جمله پنجم آزمون. جمله ششم آزمون.",
        1,
    )]
    result = chunk_two_level(
        segments,
        child_chunk_size=34,
        child_chunk_overlap=16,
        parent_chunk_size=50,
    )

    assert len(result.children) >= 3
    assert all(len(child.text) <= 34 for child in result.children)
    assert any(
        left.text.endswith("جمله دوم آزمون.") and right.text.startswith("جمله دوم آزمون.")
        for left, right in zip(result.children, result.children[1:], strict=False)
    )
    assert result.parents
    assert all(len(parent.text) <= 50 for parent in result.parents)
    assert result.parents[0].child_start == 0
    assert result.parents[-1].child_end == len(result.children) - 1
    assert all(
        left.child_end + 1 == right.child_start
        for left, right in zip(result.parents, result.parents[1:], strict=False)
    )


def test_chunk_two_level_rejects_unsafe_size_configuration() -> None:
    with pytest.raises(ValueError):
        chunk_two_level([("متن", 1)], child_chunk_size=10, child_chunk_overlap=10)
    with pytest.raises(ValueError):
        chunk_two_level([("متن", 1)], child_chunk_size=20, parent_chunk_size=10)
    with pytest.raises(ValueError):
        chunk_two_level([("متن", 0)])


# --- Embedding service ---
@pytest.mark.asyncio
async def test_embed_batch_validates_dimensions() -> None:
    async def _embed(texts: list[str]) -> list[list[float]]:
        return [_fake_embed_vec(i) for i in range(len(texts))]
    res = await embed_batch(["a", "b"], embed=_embed, model="test", expected_dim=DIM)
    assert len(res.vectors) == 2
    assert len(res.vectors[0]) == DIM


@pytest.mark.asyncio
async def test_embed_batch_rejects_wrong_dim() -> None:
    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 2.0]] * len(texts)
    with pytest.raises(AppError):
        await embed_batch(["a"], embed=_embed, model="test", expected_dim=DIM)


# --- Indexing + Retrieval (real PostgreSQL) ---
@pytest.mark.asyncio
async def test_index_then_hybrid_retrieve_grade_ceiling() -> None:
    async with SESSION_FACTORY() as s:
        # document grade 5
        doc = await _seed_document(s, grade=5)
        segments = [(f"مفهوم ریاضی پنجم صفحه {pg}. " * 12, pg) for pg in (1, 2, 3)]
        chunking = chunk_two_level(segments)

        # embed with a stable seed (linear combination by content length/page)
        async def _embed(texts: list[str]) -> list[list[float]]:
            return [_fake_embed_vec(len(t) + i) for i, t in enumerate(texts)]
        child_vecs = await _embed([c.text for c in chunking.children])
        parent_vecs = await _embed([p.text for p in chunking.parents])

        await index_document_chunks(
            s, document=doc, chunking=chunking,
            child_vectors=child_vecs, parent_vectors=parent_vecs,
            title="ریاضی پنجم", source_type="synthetic",
        )
        await s.commit()

        # Every child chunk must reference the parent that contains its child range.
        indexed = (
            await s.execute(select(IngestionChunk).where(IngestionChunk.document_id == doc.id))
        ).scalars().all()
        parent_ids = {c.id for c in indexed if c.is_parent}
        child_chunks = [c for c in indexed if not c.is_parent]
        assert child_chunks
        assert all(c.parent_id in parent_ids for c in child_chunks)

        # grade ceiling: selected_grade=6 includes all; selected_grade=1 excludes
        q = "مفهوم ریاضی"
        qv = _fake_embed_vec(len(q) + 1)

        async def _rerank(query: str, docs: list[str]) -> list[float]:
            return [1.0] * len(docs)

        r6 = await hybrid_retrieve(s, query=q, query_vector=qv, selected_grade=6, rerank=_rerank)
        assert r6.grade_ceiling_applied
        assert len(r6.chunks) > 0
        assert all(c.grade_level <= 6 for c in r6.chunks)
        # R-158: search returns child chunks only; parent chunks are for model context.
        assert all(not c.is_parent for c in r6.chunks)

        r1 = await hybrid_retrieve(s, query=q, query_vector=qv, selected_grade=1, rerank=_rerank)
        assert len(r1.chunks) == 0  # grade 5 chunks excluded for grade-1 student


@pytest.mark.asyncio
async def test_reindex_is_idempotent() -> None:
    async with SESSION_FACTORY() as s:
        doc = await _seed_document(s, grade=4)
        segments = [(f"برگ تمرین صفحه {pg}. " * 10, pg) for pg in (1, 2)]
        chunking = chunk_two_level(segments)

        async def _embed(texts: list[str]) -> list[list[float]]:
            return [_fake_embed_vec(i) for i in range(len(texts))]

        child_vecs = await _embed([c.text for c in chunking.children])
        parent_vecs = await _embed([p.text for p in chunking.parents])

        first = await index_document_chunks(s, document=doc, chunking=chunking,
                                            child_vectors=child_vecs, parent_vectors=parent_vecs)
        await s.commit()

        count1 = (await s.execute(select(func.count()).select_from(IngestionChunk)
                                  .where(IngestionChunk.document_id == doc.id))).scalar_one()

        second = await index_document_chunks(s, document=doc, chunking=chunking,
                                             child_vectors=child_vecs, parent_vectors=parent_vecs)
        await s.commit()

        count2 = (await s.execute(select(func.count()).select_from(IngestionChunk)
                                  .where(IngestionChunk.document_id == doc.id))).scalar_one()

        assert first.replaced is False
        assert second.replaced is True
        assert count1 == count2  # idempotent: no duplicate chunks
        assert count1 > 0


@pytest.mark.asyncio
async def test_isolated_documents_do_not_pollute_each_other() -> None:
    async with SESSION_FACTORY() as s:
        doc_a = await _seed_document(s, grade=3, subject="science")
        doc_b = await _seed_document(s, grade=8, subject="physics")
        seg_a = [("علم پایه سوم. " * 12, 1)]
        seg_b = [("فیزیک پایه هشتم. " * 12, 1)]
        ca = chunk_two_level(seg_a)
        cb = chunk_two_level(seg_b)

        async def _embed_a(texts: list[str]) -> list[list[float]]:
            return [_fake_embed_vec(1)] * len(texts)
        async def _embed_b(texts: list[str]) -> list[list[float]]:
            return [_fake_embed_vec(2)] * len(texts)

        await index_document_chunks(s, document=doc_a, chunking=ca,
                                    child_vectors=await _embed_a([c.text for c in ca.children]),
                                    parent_vectors=await _embed_a([p.text for p in ca.parents]),
                                    source_type="synthetic")
        await index_document_chunks(s, document=doc_b, chunking=cb,
                                    child_vectors=await _embed_b([c.text for c in cb.children]),
                                    parent_vectors=await _embed_b([p.text for p in cb.parents]),
                                    source_type="synthetic")
        await s.commit()

        all_docs = (await s.execute(text("SELECT DISTINCT document_id FROM ingestion_chunks"))).scalars().all()
        assert set(all_docs) == {doc_a.id, doc_b.id}
