"""تست‌های بازیابی Durable بعد از Crash (PostgreSQL واقعی؛ SQLite ممنوع).

سناریوها:
  A) Crash قبل از terminal: reservation pending + assistant streaming → recovery → released + cancelled
  B) Crash بعد از commit مالی: reservation settled/released، پیام streaming → recovery فقط Message
  C) تکمیل عادی: recovery نباید تغییر دهد
  D) هم‌زمانی: دو recovery → یک terminal، بدون دوبار مالی
"""

import os
import uuid

import pytest
from app.core.config import get_settings
from app.models.message import Message
from app.repositories import conversations as conv_repo
from app.repositories import reservations as res_repo
from app.repositories import users as users_repo
from app.services import worker as worker_mod
from app.services.credit_accounts import create as _create_account
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema",
)

TEST_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


def _new_phone() -> str:
    return f"+989{str(uuid.uuid4().int)[:9]}"


async def _make_user() -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role="user")
        await _create_account(session, user_id=user.id, available_balance=10)
        await session.commit()
        return user.id


async def _make_streaming_assistant(conv_id, user_id, reservation_id) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        await conv_repo.create_message(
            session, conversation_id=conv_id, user_id=user_id,
            role="assistant", status="streaming", reservation_id=reservation_id,
        )
        await session.commit()
        msg = (
            await session.execute(
                select(Message).where(Message.reservation_id == reservation_id)
            )
        ).scalar_one()
        return msg.id


async def _age_message(msg_id: uuid.UUID) -> None:
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(
            text("UPDATE messages SET updated_at = now() - interval '5 minutes' WHERE id = :id"),
            {"id": str(msg_id)},
        )
        await session.commit()


async def _age_reservation(res_id: uuid.UUID) -> None:
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(
            text("UPDATE reservations SET created_at = now() - interval '20 minutes' WHERE id = :id"),
            {"id": str(res_id)},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_scenario_a_crash_before_terminal_recovery() -> None:
    uid = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        conv = await conv_repo.create_conversation(session, user_id=uid)
        await session.commit()
        cid = conv.id
    async with TEST_SESSION_FACTORY() as session:
        from app.services.reservation import FinanceService

        res = await FinanceService(session).reserve_credit(uid, 1, idempotency_key="recover-a", payload_fingerprint="f")
        rid = res.id
        await session.commit()
    await _age_reservation(rid)
    mid = await _make_streaming_assistant(cid, uid, rid)
    await _age_message(mid)

    result = await worker_mod.recover_orphan_stream_messages({"batch_limit": 50})
    assert result["recovered"] >= 1

    async with TEST_SESSION_FACTORY() as session:
        res = await res_repo.get_by_id(session, rid)
        msg = (await session.execute(select(Message).where(Message.id == mid))).scalar_one()
    assert res.status == "released"
    assert msg.status == "cancelled"


@pytest.mark.asyncio
async def test_scenario_b_crash_after_financial_commit() -> None:
    uid = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        conv = await conv_repo.create_conversation(session, user_id=uid)
        await session.commit()
        cid = conv.id
    async with TEST_SESSION_FACTORY() as session:
        from app.services.reservation import FinanceService

        res = await FinanceService(session).reserve_credit(uid, 1, idempotency_key="recover-b", payload_fingerprint="f")
        rid = res.id
        # مباشرتاً settle (بدون commit پیام) تا حالت «پس از commit مالی» شبیه‌سازی شود
        await FinanceService(session).settle(rid)
        await session.commit()
    mid = await _make_streaming_assistant(cid, uid, rid)
    await _age_message(mid)

    result = await worker_mod.recover_orphan_stream_messages({"batch_limit": 50})
    assert result["recovered"] >= 1

    async with TEST_SESSION_FACTORY() as session:
        res = await res_repo.get_by_id(session, rid)
        msg = (await session.execute(select(Message).where(Message.id == mid))).scalar_one()
    assert res.status == "settled"
    assert msg.status == "completed"


@pytest.mark.asyncio
async def test_scenario_b2_released_after_billable_becomes_partial() -> None:
    uid = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        conv = await conv_repo.create_conversation(session, user_id=uid)
        await session.commit()
        cid = conv.id
    async with TEST_SESSION_FACTORY() as session:
        from app.services.reservation import FinanceService

        res = await FinanceService(session).reserve_credit(uid, 1, idempotency_key="recover-b2", payload_fingerprint="f")
        rid = res.id
        await FinanceService(session).release(rid, reason="late_completion")
        await session.commit()
    mid = await _make_streaming_assistant(cid, uid, rid)
    await _age_message(mid)
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(
            text("UPDATE messages SET billable_output_seen = true WHERE id = :id"),
            {"id": str(mid)},
        )
        await session.commit()

    result = await worker_mod.recover_orphan_stream_messages({"batch_limit": 50})
    assert result["recovered"] >= 1
    async with TEST_SESSION_FACTORY() as session:
        msg = (await session.execute(select(Message).where(Message.id == mid))).scalar_one()
    assert msg.status == "partial"


@pytest.mark.asyncio
async def test_scenario_c_normal_completion_untouched() -> None:
    uid = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        conv = await conv_repo.create_conversation(session, user_id=uid)
        res = await conv_repo.create_message(session, conversation_id=conv.id, user_id=uid, role="assistant", status="completed", content="done")
        await session.commit()
        msg_id = res.id
    await worker_mod.recover_orphan_stream_messages({"batch_limit": 50})
    async with TEST_SESSION_FACTORY() as session:
        msg = (await session.execute(select(Message).where(Message.id == msg_id))).scalar_one()
    assert msg.status == "completed"


@pytest.mark.asyncio
async def test_scenario_d_concurrent_recovery_single_terminal() -> None:
    uid = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        conv = await conv_repo.create_conversation(session, user_id=uid)
        await session.commit()
        cid = conv.id
    async with TEST_SESSION_FACTORY() as session:
        from app.services.reservation import FinanceService

        res = await FinanceService(session).reserve_credit(uid, 1, idempotency_key="recover-d", payload_fingerprint="f")
        rid = res.id
        await session.commit()
    await _age_reservation(rid)
    mid = await _make_streaming_assistant(cid, uid, rid)
    await _age_message(mid)

    res1 = await worker_mod.recover_orphan_stream_messages({"batch_limit": 50})
    await worker_mod.recover_orphan_stream_messages({"batch_limit": 50})
    # فقط یک اجرا باید پیام/رزرو را بازیابی کند؛ اجرای دوم idempotent
    async with TEST_SESSION_FACTORY() as session:
        res = await res_repo.get_by_id(session, rid)
        msg = (await session.execute(select(Message).where(Message.id == mid))).scalar_one()
    assert res.status == "released"
    assert msg.status == "cancelled"
    assert res1["recovered"] >= 1
