"""PostgreSQL-backed tests for authenticated conversation history and ownership."""

import os
import uuid

import pytest
import pytest_asyncio
from app.api.deps import get_current_user
from app.api.v1.sessions import router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.db.session import get_db
from app.models.user import User
from app.repositories import conversations as conv_repo
from app.repositories import users as users_repo
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)
ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)


def _phone() -> str:
    return f"+989{str(uuid.uuid4().int)[:9]}"


@pytest_asyncio.fixture
async def history_client():
    async with SESSION_FACTORY() as session:
        owner = await users_repo.create(session, phone=_phone(), role="user")
        other = await users_repo.create(session, phone=_phone(), role="user")
        conversation = await conv_repo.create_conversation(session, user_id=owner.id, title="History")
        await conv_repo.create_message(session, conversation_id=conversation.id, user_id=owner.id, role="user", content="one", status="completed")
        await conv_repo.create_message(session, conversation_id=conversation.id, user_id=owner.id, role="assistant", content="two", status="completed")
        await session.commit()
        owner_id, other_id, conversation_id = owner.id, other.id, conversation.id

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router, prefix="/api/v1")
    current_user: User | None = None

    async def override_user():
        return current_user

    async def override_db():
        async with SESSION_FACTORY() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    async with SESSION_FACTORY() as session:
        owner_user = await session.get(User, owner_id)
        other_user = await session.get(User, other_id)
    assert owner_user is not None and other_user is not None

    async def make_client(user: User):
        nonlocal current_user
        current_user = user
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield make_client, owner_user, other_user, conversation_id


@pytest.mark.asyncio
async def test_history_messages_are_paginated_and_internal_ids_are_not_exposed(history_client) -> None:
    make_client, owner, _, conversation_id = history_client
    async with await make_client(owner) as client:
        first = await client.get(f"/api/v1/conversations/{conversation_id}/messages?limit=1")
        second = await client.get(
            f"/api/v1/conversations/{conversation_id}/messages?limit=1&after_sequence=1"
        )
    assert first.status_code == 200
    assert [m["content"] for m in first.json()["items"]] == ["one"]
    assert first.json()["next_after_sequence"] == 1
    assert "provider_request_id" not in first.json()["items"][0]
    assert second.status_code == 200
    assert [m["content"] for m in second.json()["items"]] == ["two"]


@pytest.mark.asyncio
async def test_history_conversation_and_messages_are_owner_scoped(history_client) -> None:
    make_client, _, other, conversation_id = history_client
    async with await make_client(other) as client:
        convs = await client.get("/api/v1/conversations")
        messages = await client.get(f"/api/v1/conversations/{conversation_id}/messages")
    assert convs.status_code == 200
    assert convs.json()["total"] == 0
    assert messages.status_code == 404
    assert messages.json()["code"] == "conversation_not_found"


@pytest.mark.asyncio
async def test_conversation_history_offset_pagination(history_client) -> None:
    make_client, owner, _, _ = history_client
    async with SESSION_FACTORY() as session:
        await conv_repo.create_conversation(session, user_id=owner.id, title="Second")
        await session.commit()
    async with await make_client(owner) as client:
        page = await client.get("/api/v1/conversations?limit=1&offset=0")
        next_page = await client.get("/api/v1/conversations?limit=1&offset=1")
    assert page.status_code == 200 and next_page.status_code == 200
    assert len(page.json()["items"]) == len(next_page.json()["items"]) == 1
    assert page.json()["total"] == next_page.json()["total"] == 2
    async with await make_client(owner) as client:
        searched = await client.get("/api/v1/conversations?q=Second")
    assert searched.status_code == 200
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["title"] == "Second"
    assert page.json()["items"][0]["id"] != next_page.json()["items"][0]["id"]
