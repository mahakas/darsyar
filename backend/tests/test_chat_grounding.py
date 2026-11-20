"""Grounding admission: no evidence -> no billable provider call."""

import os
import uuid
from types import SimpleNamespace

import pytest
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories import credit_accounts as accounts_repo
from app.repositories import users as users_repo
from app.schemas.conversation import ChatStreamRequest
from app.services.chat_service import ChatStreamService
from app.services.grounding import NO_EVIDENCE, GroundingContext, GroundingService
from app.services.ingestion.retrieval import RetrievalResult, RetrievedChunk
from app.services.llm import ChatChunk
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


class FakeRetrieval:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks

    async def retrieve(self, session, *, query: str, selected_grade: int, top_k: int) -> RetrievalResult:
        return RetrievalResult(chunks=self.chunks, grade_ceiling_applied=True, k=60.0)


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="c1",
        document_id="d1",
        chunk_index=3,
        is_parent=False,
        grade_level=5,
        subject="math",
        page_number=12,
        title="کتاب ریاضی",
        content="متن شاهد",
        dense_score=0.9,
        lexical_score=None,
        rrf_score=0.8,
    )


@pytest.mark.asyncio
async def test_grounding_builds_prompt_and_citations() -> None:
    service = GroundingService(FakeRetrieval([_chunk()]))  # type: ignore[arg-type]
    context = await service.build(None, query="سوال", grade=7)  # type: ignore[arg-type]
    assert "متن شاهد" in context.system_prompt
    assert context.citations == ("[کتاب: کتاب ریاضی | پایه 5 | صفحه 12 | قطعه 3]",)


@pytest.mark.asyncio
async def test_grounding_fails_closed_without_evidence() -> None:
    service = GroundingService(FakeRetrieval([]))  # type: ignore[arg-type]
    with pytest.raises(AppError) as excinfo:
        await service.build(None, query="سوال", grade=7)  # type: ignore[arg-type]
    assert excinfo.value is NO_EVIDENCE


class FakeGrounding:
    async def build(self, session, *, query: str, grade: int) -> GroundingContext:
        assert grade == 7
        return GroundingContext(system_prompt="SYSTEM EVIDENCE", citations=("citation-1",))


class CapturingProvider:
    def __init__(self) -> None:
        self.requests: list[object] = []

    async def stream_chat(self, req):
        self.requests.append(req)
        yield ChatChunk(delta="پاسخ")
        yield ChatChunk(delta="", done=True)


pytestmark_db = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)
TEST_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


@pytestmark_db
@pytest.mark.asyncio
async def test_grounded_turn_emits_sources_and_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_GROUNDING_REQUIRED", "true")
    get_settings.cache_clear()
    try:
        async with TEST_SESSION_FACTORY() as session:
            user = await users_repo.create(session, phone=f"+989{uuid.uuid4().int % 10**9}", role="user")
            user.selected_grade = 7
            await accounts_repo.create(session, user_id=user.id, available_balance=5)
            await session.commit()
            uid = user.id

        provider = CapturingProvider()
        service = ChatStreamService(
            provider=provider,
            session_factory=TEST_SESSION_FACTORY,
            grounding=FakeGrounding(),  # type: ignore[arg-type]
        )
        req = ChatStreamRequest(content="سوال", client_request_id=f"grounding-{uuid.uuid4().hex}")
        user_obj = SimpleNamespace(id=uid, role="user", selected_grade=7)
        await service.preflight(req, user_obj)  # type: ignore[arg-type]
        events = [event async for event in service.stream_chat(req, user_obj)]  # type: ignore[arg-type]

        assert any("event:sources" in event and "citation-1" in event for event in events)
        async with TEST_SESSION_FACTORY() as session:
            persisted = (await session.execute(select(Message.sources_json).where(Message.user_id == uid))).scalars().all()
        assert ["citation-1"] in persisted
        assert provider.requests
        assert provider.requests[0].messages[0] == {  # type: ignore[attr-defined]
            "role": "system",
            "content": "SYSTEM EVIDENCE",
        }

        async with TEST_SESSION_FACTORY() as session:
            # Ledger and reservation rows are immutable/orphan-safe test residue;
            # only rows that can block user deletion are removed here.
            for model in (Message, Conversation):
                await session.execute(delete(model).where(model.user_id == uid))
            # Users with immutable ledger rows are intentionally left as test residue.
            await session.commit()
    finally:
        get_settings.cache_clear()
