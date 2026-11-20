"""Grounding bridge between the billable chat turn and the retrieval stack.

When ``CHAT_GROUNDING_REQUIRED`` is enabled, a turn is admitted only after the
active index returned grade-bounded evidence. The resulting system prompt and
server-formatted citations are carried into the SSE stream; no model call is made
when evidence is absent.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.inference.remote import RemoteInferenceBackend
from app.services.ingestion.retrieval import RetrievalResult
from app.services.ingestion.retrieval_service import RetrievalService

NO_EVIDENCE = AppError(
    "no_evidence",
    409,
    "برای این پرسش در محدودهٔ پایهٔ شما شاهد معتبری یافت نشد؛ پاسخی تولید نمیشود.",
)

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]
RerankFn = Callable[[str, list[str]], Awaitable[list[float]]]


@dataclass(frozen=True, slots=True)
class GroundingContext:
    system_prompt: str
    citations: tuple[str, ...]


class GroundingService:
    """Build a deterministic prompt from server-side retrieval output."""

    def __init__(self, retrieval: RetrievalService) -> None:
        self._retrieval = retrieval

    async def build(self, session: AsyncSession, *, query: str, grade: int) -> GroundingContext:
        settings = get_settings()
        result: RetrievalResult = await self._retrieval.retrieve(
            session,
            query=query,
            selected_grade=grade,
            top_k=settings.chat_grounding_top_k,
        )
        if not result.chunks or not result.grade_ceiling_applied:
            raise NO_EVIDENCE

        blocks: list[str] = []
        citations: list[str] = []
        for chunk in result.chunks:
            citation = RetrievalService.format_citation(
                chunk.title,
                int(chunk.grade_level),
                chunk.page_number,
                int(chunk.chunk_index),
            )
            blocks.append(f"{chunk.content}\n{citation}")
            citations.append(citation)
        prompt = (
            "فقط از شواهد زیر پاسخ بده. اگر پاسخ در شواهد نیست، صراحتاً بگو نمیدانم. "
            "به پایهٔ تحصیلی کاربر محدود بمان و ارجاع هر جمله را حفظ کن.\n\n"
            + "\n---\n".join(blocks)
        )
        return GroundingContext(system_prompt=prompt, citations=tuple(citations))


async def build_default_grounding() -> tuple[GroundingService, Callable[[], Awaitable[None]]]:
    """Create a retrieval service backed by the configured inference endpoint."""
    settings = get_settings()
    backend = RemoteInferenceBackend(settings)
    try:
        await backend.startup()
    except BaseException:
        await backend.aclose()
        raise

    async def embed(texts: list[str]) -> list[list[float]]:
        return await backend.embed(texts)

    async def rerank(query: str, documents: list[str]) -> list[float]:
        return await backend.rerank([(query, document) for document in documents])

    retrieval = RetrievalService(
        embed=embed,
        rerank=rerank,
        embedding_model=settings.embedding_model,
        embedding_dim=settings.embedding_dim,
    )
    return GroundingService(retrieval), backend.aclose
