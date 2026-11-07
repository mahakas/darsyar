"""تست‌های یکپارچهٔ گفتگو/پیام روی PostgreSQL واقعی (Slice B؛ R-121)."""

import os
import uuid

import pytest
from app.core.config import get_settings
from app.repositories import conversations as conv_repo
from app.repositories import users as users_repo
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


async def _make_user() -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role="user")
        await session.commit()
        return user.id


@pytest.mark.asyncio
async def test_ownership_isolation_conversations() -> None:
    a = await _make_user()
    b = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        conv = await conv_repo.create_conversation(session, user_id=a)
        await session.commit()
        conv_id = conv.id
    async with TEST_SESSION_FACTORY() as session:
        assert await conv_repo.get_owned(session, conv_id, a) is not None
        assert await conv_repo.get_owned(session, conv_id, b) is None
        assert await conv_repo.count_owned(session, a) == 1
        assert await conv_repo.count_owned(session, b) == 0
        listed = await conv_repo.list_owned(session, a, limit=10)
        assert [c.id for c in listed] == [conv_id]


@pytest.mark.asyncio
async def test_message_idempotent_client_request_id() -> None:
    uid = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        conv = await conv_repo.create_conversation(session, user_id=uid)
        await session.commit()
        conv_id = conv.id
    async with TEST_SESSION_FACTORY() as session:
        m1 = await conv_repo.create_message_idempotent(
            session, conversation_id=conv_id, user_id=uid, role="user", content="hi", client_request_id="crid0001"
        )
        m2 = await conv_repo.create_message_idempotent(
            session, conversation_id=conv_id, user_id=uid, role="user", content="hi", client_request_id="crid0001"
        )
        await session.commit()
        assert m1.id == m2.id
        msgs = await conv_repo.list_messages_for_user(session, conv_id, uid)
        assert len(msgs) == 1
        assert msgs[0].sequence == 1


@pytest.mark.asyncio
async def test_message_ordering_and_status_update() -> None:
    uid = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        conv = await conv_repo.create_conversation(session, user_id=uid)
        await session.commit()
        conv_id = conv.id
    async with TEST_SESSION_FACTORY() as session:
        await conv_repo.create_message(session, conversation_id=conv_id, user_id=uid, role="user", content="q1")
        await conv_repo.create_message(session, conversation_id=conv_id, user_id=uid, role="assistant", content="")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        msgs = await conv_repo.list_messages_for_user(session, conv_id, uid)
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert [m.sequence for m in msgs] == [1, 2]
        assert await conv_repo.set_message_status(session, msgs[1].id, "completed", content="final")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        after = await conv_repo.list_messages_for_user(session, conv_id, uid, after_sequence=1)
        assert after[0].status == "completed"
        assert after[0].content == "final"
