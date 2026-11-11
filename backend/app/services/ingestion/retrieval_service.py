"""Phase 5: retrieval orchestration service.

Wraps `hybrid_retrieve` with the live embedding provider (embed the query) and
the rerank provider, returning typed results with citation-formatted evidence.
The grade ceiling (`chunk.grade_level <= selected_grade`) is enforced in SQL by
the retriever; this service only selects the active embedding index metadata and
delegates to it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.ingestion.embedding_service import embed_batch
from app.services.ingestion.retrieval import RetrievalResult, hybrid_retrieve

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]
RerankFn = Callable[[str, list[str]], Awaitable[list[float]]]

CITATION_TEMPLATE = "[کتاب: {title} | پایه {grade} | صفحه {page} | قطعه {chunk_index}]"


class RetrievalService:
    def __init__(
        self,
        *,
        embed: EmbedFn,
        rerank: RerankFn,
        embedding_model: str,
        embedding_dim: int,
    ) -> None:
        self._embed = embed
        self._rerank = rerank
        settings = get_settings()
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim
        # Keep the two R-163 thresholds independent and source them from validated settings.
        self._min_retrieval_score = settings.min_retrieval_score
        self._min_confidence = settings.min_confidence
        self._top_k = settings.reranker_top_k

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        query: str,
        selected_grade: int,
        edition_year: int | None = None,
        subject: str | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        if selected_grade < 1 or selected_grade > 12:
            raise AppError("invalid_selected_grade", 422, "پایهٔ دانش‌آموز نامعتبر است.")

        # embed the query with the live provider (dim validated)
        res = await embed_batch([query], embed=self._embed, model=self._embedding_model,
                                expected_dim=self._embedding_dim)
        query_vector = res.vectors[0]

        return await hybrid_retrieve(
            session,
            query=query,
            query_vector=query_vector,
            selected_grade=selected_grade,
            edition_year=edition_year,
            subject=subject,
            top_k=top_k if top_k is not None else self._top_k,
            min_retrieval_score=self._min_retrieval_score,
            min_rerank_score=self._min_confidence,
            rerank=self._rerank,
        )

    @staticmethod
    def format_citation(title: str | None, grade: int, page: int | None, chunk_index: int) -> str:
        # Guard against inventing page numbers (R-175): if unknown, render "-".
        page_str = str(page) if page is not None else "-"
        return CITATION_TEMPLATE.format(title=title or "", grade=grade, page=page_str, chunk_index=chunk_index)
