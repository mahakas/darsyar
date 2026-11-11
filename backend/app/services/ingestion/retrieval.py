"""Phase 4/5: hybrid retrieval (R-148/R-161/R-162/R-163/R-165/R-166).

Dense (pgvector cosine) + lexical (pg_trgm) retrieval with the grade filter
`chunk.grade_level <= selected_grade` applied in the SQL for BOTH branches
(R-148). Results are fused with Reciprocal Rank Fusion (RRF) using k=60 and a
deterministic tie-break on (document_id, chunk_index). The fused top-k is then
reranked (provider callback) and thresholded.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.services.ingestion.normalize import normalize_persian

RRF_K = 60.0
TOP_K_RERANK = 20
MIN_CONFIDENCE = 0.35
MIN_RETRIEVAL_SCORE = 0.0

RerankFn = Callable[[str, list[str]], Awaitable[list[float]]]


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    is_parent: bool
    grade_level: int
    subject: str
    page_number: int | None
    title: str | None
    content: str
    dense_score: float | None
    lexical_score: float | None
    rrf_score: float
    rerank_score: float | None = None


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(repr(x) for x in vec) + "]"


async def _dense_search(session: AsyncSession, query_vec: list[float], grade: int, edition_year: int | None, subject: str | None, limit: int) -> list[dict[str, Any]]:
    vec_lit = _vector_literal(query_vec)
    params: dict[str, Any] = {
        "vec": vec_lit,
        "grade": grade,
        "limit": limit,
    }
    # Parent chunks are context containers, never retrieval candidates (R-158).
    where = ["grade_level <= :grade", "is_parent = false", "embedding IS NOT NULL"]
    if edition_year is not None:
        where.append("edition_year = :edition_year")
        params["edition_year"] = edition_year
    if subject is not None:
        where.append("subject = :subject")
        params["subject"] = subject
    sql = (
        "SELECT id::text AS chunk_id, document_id::text AS document_id, chunk_index, is_parent, "
        "grade_level, subject, page_number, title, content, "
        "1 - (embedding <=> (:vec)::vector) AS dense_score "
        "FROM ingestion_chunks WHERE " + " AND ".join(where) +
        " ORDER BY embedding <=> (:vec)::vector LIMIT :limit"
    )
    rows = (await session.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]


async def _lexical_search(session: AsyncSession, query: str, grade: int, edition_year: int | None, subject: str | None, limit: int) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "q": query,
        "grade": grade,
        "limit": limit,
    }
    # Parent chunks are context containers, never retrieval candidates (R-158).
    where = ["grade_level <= :grade", "is_parent = false", "content_normalized % :q"]
    if edition_year is not None:
        where.append("edition_year = :edition_year")
        params["edition_year"] = edition_year
    if subject is not None:
        where.append("subject = :subject")
        params["subject"] = subject
    sql = (
        "SELECT id::text AS chunk_id, document_id::text AS document_id, chunk_index, is_parent, "
        "grade_level, subject, page_number, title, content, "
        "similarity(content_normalized, :q) AS lexical_score "
        "FROM ingestion_chunks WHERE " + " AND ".join(where) +
        " ORDER BY similarity(content_normalized, :q) DESC LIMIT :limit"
    )
    rows = (await session.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    grade_ceiling_applied: bool
    k: float


def _rrf_rank(rank: int) -> float:
    return 1.0 / (RRF_K + rank + 1)


async def hybrid_retrieve(
    session: AsyncSession,
    *,
    query: str,
    query_vector: list[float],
    selected_grade: int,
    edition_year: int | None = None,
    subject: str | None = None,
    top_k: int = TOP_K_RERANK,
    rerank: RerankFn | None = None,
    min_retrieval_score: float = MIN_RETRIEVAL_SCORE,
    min_rerank_score: float = MIN_CONFIDENCE,
    dense_limit: int = 40,
    lexical_limit: int = 40,
) -> RetrievalResult:
    """Hybrid retrieve child chunks with grade-filtered SQL, RRF and two thresholds."""
    if not 1 <= selected_grade <= 12:
        raise AppError("invalid_selected_grade", 422, "پایهٔ انتخاب‌شده باید بین ۱ و ۱۲ باشد.")
    if not query.strip():
        raise AppError("empty_retrieval_query", 422, "پرس‌وجوی بازیابی خالی است.")
    if top_k < 1 or dense_limit < 1 or lexical_limit < 1:
        raise AppError("invalid_retrieval_limit", 422, "محدودیت تعداد نتایج بازیابی نامعتبر است.")
    if not 0.0 <= min_retrieval_score <= 1.0 or not 0.0 <= min_rerank_score <= 1.0:
        raise AppError("invalid_retrieval_threshold", 422, "آستانهٔ بازیابی نامعتبر است.")
    q_norm = normalize_persian(query)
    dense = await _dense_search(session, query_vector, selected_grade, edition_year, subject, dense_limit)
    lexical = await _lexical_search(session, q_norm, selected_grade, edition_year, subject, lexical_limit)

    dense_rank: dict[str, int] = {r["chunk_id"]: i for i, r in enumerate(dense)}
    lexical_rank: dict[str, int] = {r["chunk_id"]: i for i, r in enumerate(lexical)}

    merged: dict[str, dict[str, Any]] = {}
    # insert dense first so its fields are base; merge lexical on top
    for r in dense:
        merged[r["chunk_id"]] = dict(r)
    for r in lexical:
        if r["chunk_id"] in merged:
            merged[r["chunk_id"]]["lexical_score"] = r["lexical_score"]
        else:
            merged[r["chunk_id"]] = dict(r)
            merged[r["chunk_id"]]["dense_score"] = None

    candidates: list[dict[str, Any]] = []
    for cid, row in merged.items():
        rrf = 0.0
        if cid in dense_rank:
            rrf += _rrf_rank(dense_rank[cid])
        if cid in lexical_rank:
            rrf += _rrf_rank(lexical_rank[cid])
        row["rrf_score"] = rrf
        # R-163: only candidates meeting MIN_RETRIEVAL_SCORE enter reranking.
        if rrf >= min_retrieval_score:
            candidates.append(row)

    # deterministic sort: RRF desc, then (document_id, chunk_index)
    candidates.sort(key=lambda c: (-c["rrf_score"], c["document_id"], c["chunk_index"]))
    candidates = candidates[:top_k]

    rerank_scores: dict[str, float] = {}
    if rerank is not None and candidates:
        docs = [c["content"] for c in candidates]
        try:
            scores = await rerank(q_norm, docs)
        except Exception as exc:  # noqa: BLE001 - rerank is best-effort gate
            raise AppError("rerank_provider_failure", 502,
                           f"شکست سرویس rerank: {type(exc).__name__}") from exc
        for c, score in zip(candidates, scores, strict=True):
            rerank_scores[c["chunk_id"]] = float(score)

    out: list[RetrievedChunk] = []
    for c in candidates:
        r_score = rerank_scores.get(c["chunk_id"])
        if r_score is not None and r_score < min_rerank_score:
            continue
        out.append(RetrievedChunk(
            chunk_id=c["chunk_id"],
            document_id=c["document_id"],
            chunk_index=int(c["chunk_index"]),
            is_parent=bool(c["is_parent"]),
            grade_level=int(c["grade_level"]),
            subject=str(c["subject"]),
            page_number=int(c["page_number"]) if c.get("page_number") is not None else None,
            title=c.get("title"),
            content=str(c["content"]),
            dense_score=float(c["dense_score"]) if c.get("dense_score") is not None else None,
            lexical_score=float(c["lexical_score"]) if c.get("lexical_score") is not None else None,
            rrf_score=float(c["rrf_score"]),
            rerank_score=r_score,
        ))

    return RetrievalResult(chunks=out, grade_ceiling_applied=True, k=RRF_K)
