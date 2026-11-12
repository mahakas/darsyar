"""تست‌های یکپارچهٔ چت استریم + چرخه مالی روی PostgreSQL واقعی (Slice C/D؛ ADR-039).

از FakeProvider برای شبیه‌سازی استریم provider استفاده می‌شود؛ بدون تماس LLM واقعی.
"""

import asyncio
import json
import os
import uuid
from types import SimpleNamespace

import pytest
from app.core.config import get_settings
from app.models.credit_ledger import CreditLedger
from app.models.message import Message
from app.repositories import conversations as conv_repo
from app.repositories import credit_accounts as accounts_repo
from app.repositories import reservations as reservations_repo
from app.repositories import users as users_repo
from app.schemas.conversation import ChatStreamRequest
from app.services.chat_service import ChatStreamService
from app.services.reservation import FinanceService
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

TEST_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


def _new_phone() -> str:
    return f"+989{str(uuid.uuid4().int)[:9]}"


async def _make_user_with_credits(n: int = 10) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role="user")
        user.selected_grade = 7  # explicit synthetic grade for chat acceptance tests
        await accounts_repo.create(session, user_id=user.id, available_balance=n)
        await session.commit()
        return user.id


class FakeProvider:
    def __init__(self, script: list[tuple]) -> None:
        self.script = script
        self.calls = 0

    async def stream_chat(self, req):
        self.calls += 1
        from app.services.llm import ChatChunk

        for item in self.script:
            if item[0] == "delta":
                yield ChatChunk(delta=item[1])
            elif item[0] == "done":
                yield ChatChunk(delta="", done=True)
            elif item[0] == "error":
                yield ChatChunk(delta="", done=True, error=item[1])


def _user(uid: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(id=uid, role="user", selected_grade=7)


async def _collect(service: ChatStreamService, req: ChatStreamRequest, uid: uuid.UUID) -> list[str]:
    events = []
    async for ev in service.stream_chat(req, _user(uid)):
        events.append(ev)
    return events


async def _reservation(uid: uuid.UUID, key_suffix: str):
    async with TEST_SESSION_FACTORY() as session:
        return await reservations_repo.get_by_idempotency_key(session, uid, f"chat:{uid}:{key_suffix}")


async def _balance(uid: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return (await accounts_repo.get_for_update(session, uid)).available_balance


async def _ledger_kinds(uid: uuid.UUID) -> list[str]:
    async with TEST_SESSION_FACTORY() as session:
        rows = (await session.execute(select(CreditLedger.kind).where(CreditLedger.user_id == uid))).scalars().all()
        return list(rows)


@pytest.mark.asyncio
async def test_success_stream_settles_and_persists() -> None:
    uid = await _make_user_with_credits()
    provider = FakeProvider([("delta", "سلام"), ("delta", " دنیا"), ("done",)])
    service = ChatStreamService(provider=provider, session_factory=TEST_SESSION_FACTORY)
    req = ChatStreamRequest(content="hi", client_request_id="aaaaaaaaaaaa")
    events = await _collect(service, req, uid)
    assert any("event:ack" in e for e in events)
    assert any("event:done" in e for e in events)
    reservation = await _reservation(uid, "aaaaaaaaaaaa")
    assert reservation is not None
    assert reservation.status == "settled"
    async with TEST_SESSION_FACTORY() as session:
        msgs = (await session.execute(select(Message).where(Message.user_id == uid).order_by(Message.sequence))).scalars().all()
    assert len(msgs) == 2
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].status == "completed"
    assert msgs[1].reservation_id == reservation.id
    assert (await _balance(uid)) == 9


@pytest.mark.asyncio
async def test_failure_before_first_token_releases_and_refunds() -> None:
    uid = await _make_user_with_credits()
    provider = FakeProvider([("error", "boom")])
    service = ChatStreamService(provider=provider, session_factory=TEST_SESSION_FACTORY)
    req = ChatStreamRequest(content="hi", client_request_id="bbbbbbbb")
    events = await _collect(service, req, uid)
    reservation = await _reservation(uid, "bbbbbbbb")
    assert reservation.status == "released"
    kinds = await _ledger_kinds(uid)
    assert kinds.count("spend") == 1
    assert kinds.count("refund") == 1
    assert (await _balance(uid)) == 10
    assert any("event:error" in e for e in events)


@pytest.mark.asyncio
async def test_mid_stream_failure_is_partial_and_settles() -> None:
    uid = await _make_user_with_credits()
    provider = FakeProvider([("delta", "part"), ("error", "boom")])
    service = ChatStreamService(provider=provider, session_factory=TEST_SESSION_FACTORY)
    req = ChatStreamRequest(content="hi", client_request_id="cccccccc")
    await _collect(service, req, uid)
    reservation = await _reservation(uid, "cccccccc")
    assert reservation.status == "settled"
    async with TEST_SESSION_FACTORY() as session:
        msg = (await session.execute(select(Message).where(Message.user_id == uid, Message.role == "assistant"))).scalar_one()
    assert msg.status == "partial"


@pytest.mark.asyncio
async def test_duplicate_idempotency_no_second_provider_or_billing() -> None:
    uid = await _make_user_with_credits()
    provider = FakeProvider([("delta", "x"), ("done",)])
    service = ChatStreamService(provider=provider, session_factory=TEST_SESSION_FACTORY)
    req = ChatStreamRequest(content="hi", client_request_id="dddddddd")
    await _collect(service, req, uid)
    await _collect(service, req, uid)  # replay
    assert provider.calls == 1
    reservation = await _reservation(uid, "dddddddd")
    assert reservation.status == "settled"
    async with TEST_SESSION_FACTORY() as session:
        assistants = (await session.execute(select(Message).where(Message.user_id == uid, Message.role == "assistant"))).scalars().all()
    assert len(assistants) == 1
    assert (await _balance(uid)) == 9


@pytest.mark.asyncio
async def test_reservation_message_uniqueness_guard() -> None:
    """قفل DB: فقط یک پیام assistant در هر رزرو؛ درج دوم با IntegrityError رد می‌شود.

    این همان مکانیزمی است که در production از provider فراخوانی دوم و settle دوم جلوگیری می‌کند.
    """
    from sqlalchemy.exc import IntegrityError

    uid = await _make_user_with_credits()
    async with TEST_SESSION_FACTORY() as session:
        reservation = await FinanceService(session).reserve_credit(
            uid, 1, idempotency_key=f"chat:{uid}:unique", payload_fingerprint="f"
        )
        conv = await conv_repo.create_conversation(session, user_id=uid)
        await session.commit()
        rid = reservation.id
        cid = conv.id
    async with TEST_SESSION_FACTORY() as session:
        m1 = await conv_repo.create_message(
            session, conversation_id=cid, user_id=uid, role="assistant", reservation_id=rid
        )
        await session.commit()
        m1_id = m1.id
    # second message for the same reservation must be rejected
    rejected = False
    try:
        async with TEST_SESSION_FACTORY() as session:
            await conv_repo.create_message(
                session, conversation_id=cid, user_id=uid, role="assistant", reservation_id=rid
            )
            await session.commit()
    except IntegrityError:
        rejected = True
    assert rejected is True
    async with TEST_SESSION_FACTORY() as session:
        found = await conv_repo.get_message_by_reservation(session, rid)
    assert found is not None
    assert found.id == m1_id


@pytest.mark.asyncio
async def test_ownership_isolation_blocks_foreign_conversation() -> None:
    uid_a = await _make_user_with_credits()
    uid_b = await _make_user_with_credits()
    async with TEST_SESSION_FACTORY() as session:
        conv = await conv_repo.create_conversation(session, user_id=uid_a)
        await session.commit()
        conv_id = conv.id
    provider = FakeProvider([("delta", "x"), ("done",)])
    service = ChatStreamService(provider=provider, session_factory=TEST_SESSION_FACTORY)
    req = ChatStreamRequest(conversation_id=conv_id, content="hi", client_request_id="ffffffff")
    with pytest.raises(Exception) as excinfo:
        await _collect(service, req, uid_b)
    assert "conversation_not_found" in str(excinfo.value)


@pytest.mark.asyncio
async def test_late_completion_after_deadline_falls_back_to_release() -> None:
    uid = await _make_user_with_credits()
    # reserve, then age the reservation past the 15-minute deadline, then finalize as billable
    async with TEST_SESSION_FACTORY() as session:
        reservation = await FinanceService(session).reserve_credit(
            uid, 1, idempotency_key=f"chat:{uid}:late", payload_fingerprint="f"
        )
        await session.execute(
            text("UPDATE reservations SET created_at = now() - interval '16 minutes' WHERE id = :rid"),
            {"rid": str(reservation.id)},
        )
        await session.commit()
    service = ChatStreamService(provider=FakeProvider([]), session_factory=TEST_SESSION_FACTORY)
    settled, outcome = await service._finalize(reservation.id, billable=True)
    assert settled is False
    assert outcome == "released"
    async with TEST_SESSION_FACTORY() as session:
        check = await reservations_repo.get_by_id(session, reservation.id)
    assert check.status == "released"
    kinds = await _ledger_kinds(uid)
    assert kinds.count("refund") == 1
    assert (await _balance(uid)) == 10


class _HangProvider:
    """provider که هرگز terminal نمی‌شود (برای تست لغو مستقیم)."""

    def __init__(self, deltas_first: int = 0) -> None:
        self.deltas_first = deltas_first

    async def stream_chat(self, req):
        from app.services.llm import ChatChunk

        for _ in range(self.deltas_first):
            yield ChatChunk(delta="x")
        await asyncio.Future()


async def _assistant_for_reservation(uid, reservation_id):
    from app.models.message import Message
    from sqlalchemy import select

    async with TEST_SESSION_FACTORY() as session:
        msg = (
            await session.execute(
                select(Message).where(
                    Message.reservation_id == reservation_id,
                    Message.user_id == uid,
                    Message.role == "assistant",
                )
            )
        ).scalar_one_or_none()
        return msg


@pytest.mark.asyncio
async def test_cancellation_before_billable_releases() -> None:
    """لغو مستقیم (asyncio.Task.cancel) پیش از billable -> released."""
    uid = await _make_user_with_credits()
    bal_before = await _balance(uid)
    service = ChatStreamService(provider=_HangProvider(), session_factory=TEST_SESSION_FACTORY)
    req = ChatStreamRequest(content="hi", client_request_id="cancel-a-0001")

    async def drain():
        async for _ in service.stream_chat(req, _user(uid)):
            pass

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.8)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    res = await _reservation(uid, "cancel-a-0001")
    assert res is not None and res.status == "released"
    assert await _balance(uid) == bal_before
    kinds = await _ledger_kinds(uid)
    assert kinds.count("spend") == 1
    assert kinds.count("refund") == 1
    msg = await _assistant_for_reservation(uid, res.id)
    assert msg is not None and msg.status == "cancelled"


@pytest.mark.asyncio
async def test_cancellation_after_billable_settles() -> None:
    """لغو مستقیم پس از حداقل یک delta billable -> settled (ADR-039)."""
    uid = await _make_user_with_credits()
    bal_before = await _balance(uid)
    service = ChatStreamService(provider=_HangProvider(deltas_first=1), session_factory=TEST_SESSION_FACTORY)
    req = ChatStreamRequest(content="hi", client_request_id="cancel-b-0001")

    async def drain():
        async for _ in service.stream_chat(req, _user(uid)):
            pass

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.8)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    res = await _reservation(uid, "cancel-b-0001")
    assert res is not None and res.status == "settled"
    assert await _balance(uid) == bal_before - 1
    kinds = await _ledger_kinds(uid)
    assert kinds.count("spend") == 1
    msg = await _assistant_for_reservation(uid, res.id)
    assert msg is not None and msg.status == "partial"


@pytest.mark.asyncio
async def test_new_chat_retry_reuses_original_conversation_and_reservation() -> None:
    uid = await _make_user_with_credits()
    bal_before = await _balance(uid)
    provider = FakeProvider([("delta", "stable answer"), ("done",)])
    service = ChatStreamService(provider=provider, session_factory=TEST_SESSION_FACTORY)
    req = ChatStreamRequest(content="same turn", client_request_id="new-chat-retry-0001")

    first_events = await _collect(service, req, uid)
    second_events = await _collect(service, req, uid)

    def ack_conversation_id(events: list[str]) -> str:
        event = next(item for item in events if "event:ack" in item)
        payload_line = next(line for line in event.splitlines() if line.startswith("data:"))
        return json.loads(payload_line.removeprefix("data:"))["conversation_id"]

    first_conversation_id = ack_conversation_id(first_events)
    replay_conversation_id = ack_conversation_id(second_events)
    assert replay_conversation_id == first_conversation_id
    assert provider.calls == 1
    assert await _balance(uid) == bal_before - 1
    async with TEST_SESSION_FACTORY() as session:
        assert await conv_repo.count_owned(session, uid) == 1


@pytest.mark.asyncio
async def test_new_chat_preflight_does_not_create_orphan_conversation() -> None:
    uid = await _make_user_with_credits()
    service = ChatStreamService(provider=FakeProvider([("done",)]), session_factory=TEST_SESSION_FACTORY)
    req = ChatStreamRequest(content="hi", client_request_id="preflight-new-chat-01")

    async with TEST_SESSION_FACTORY() as session:
        before = await conv_repo.count_owned(session, uid)

    await service.preflight(req, _user(uid))

    async with TEST_SESSION_FACTORY() as session:
        after = await conv_repo.count_owned(session, uid)

    assert after == before


@pytest.mark.asyncio
async def test_chat_rejects_missing_selected_grade_before_reserving_credit() -> None:
    uid = await _make_user_with_credits()
    provider = FakeProvider([("delta", "must not run"), ("done",)])
    service = ChatStreamService(provider=provider, session_factory=TEST_SESSION_FACTORY)
    user = SimpleNamespace(id=uid, role="user", selected_grade=None)
    req = ChatStreamRequest(content="hi", client_request_id="grade-required-01")

    from app.core.errors import AppError

    with pytest.raises(AppError) as excinfo:
        async for _ in service.stream_chat(req, user):
            pass

    assert excinfo.value.code == "grade_required"
    assert provider.calls == 0
    assert (await _balance(uid)) == 10
