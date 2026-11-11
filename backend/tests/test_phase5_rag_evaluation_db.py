"""Phase 5 integration tests: retrieval service + synthetic gold evaluation.

Uses real PostgreSQL and a deterministic fake embedding/rerank provider to meet
the RAG gates on synthetic data: grade leakage == 0 and invalid citation == 0.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.models.ingestion_document import IngestionDocument
from app.services.ingestion.chunking import chunk_two_level
from app.services.ingestion.evaluation import GoldItem, evaluate_retrieval
from app.services.ingestion.indexing import index_document_chunks
from app.services.ingestion.retrieval_service import RetrievalService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)
DIM = 1024


def _vec(seed: int, dim: int = DIM) -> list[float]:
    import hashlib

    digest = hashlib.sha256(str(seed).encode()).digest()
    v = [0.0] * dim
    for i, b in enumerate(digest):
        v[i % dim] += b / 255.0
    norm = sum(x * x for x in v) ** 0.5
    return [x / norm for x in v]


@pytest_asyncio.fixture(autouse=True)
async def _clean() -> None:
    async with SESSION_FACTORY() as s:
        await s.execute(text("TRUNCATE ingestion_chunks, ingestion_documents CASCADE"))
        await s.commit()


@pytest.mark.asyncio
async def test_retrieval_service_meets_rag_gates() -> None:
    async with SESSION_FACTORY() as s:
        # one document, grade 5
        doc = IngestionDocument(checksum=uuid.uuid4().hex[:64], edition_year=1405, subject="math", grade_level=5)
        s.add(doc)
        await s.commit()

        segments = [(f"مفهوم ریاضی پایه پنجم صفحه {pg}. " * 14, pg) for pg in (1, 2, 3)]
        chunking = chunk_two_level(segments)

        async def _embed(texts: list[str]) -> list[list[float]]:
            return [_vec(len(t) + i) for i, t in enumerate(texts)]

        async def _rerank(query: str, docs: list[str]) -> list[float]:
            return [1.0] * len(docs)

        child_vecs = await _embed([c.text for c in chunking.children])
        parent_vecs = await _embed([p.text for p in chunking.parents])
        await index_document_chunks(
            s, document=doc, chunking=chunking,
            child_vectors=child_vecs, parent_vectors=parent_vecs,
            title="ریاضی پنجم", source_type="synthetic",
        )
        await s.commit()

        service = RetrievalService(embed=_embed, rerank=_rerank,
                                   embedding_model="test", embedding_dim=DIM)

        q = "مفهوم ریاضی"
        r5 = await service.retrieve(s, query=q, selected_grade=5)
        r1 = await service.retrieve(s, query=q, selected_grade=1)

        # grade leakage must be 0: all retrieved chunks <= selected grade
        assert all(c.grade_level <= 5 for c in r5.chunks)
        assert all(c.grade_level <= 1 for c in r1.chunks)
        # a grade-1 student must not retrieve grade-5 chunks
        assert len(r1.chunks) == 0

        # synthetic gold: query at grade 5 should recall the math chunks
        gold = [GoldItem(query=q, grade=5, ground_truth_chunk_keys={(5, i) for i in range(0, len(chunking.children))})]
        evalr = evaluate_retrieval(gold, [r5])
        assert evalr.grade_leakage == 0.0
        assert evalr.invalid_citation_rate == 0.0
        assert evalr.recall_at_5 > 0.0


@pytest.mark.asyncio
async def test_citation_format_guards_missing_page() -> None:
    c = RetrievalService.format_citation(title="ریاضی پنجم", grade=5, page=None, chunk_index=3)
    assert "[کتاب: ریاضی پنجم | پایه 5 | صفحه - | قطعه 3]" == c
