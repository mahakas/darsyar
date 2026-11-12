"""PostgreSQL tests proving admin audit rows cannot be updated, deleted or truncated."""

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.repositories import admin_audit_log as audit_repo
from app.repositories import users as users_repo


pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)
ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)


def _phone() -> str:
    return f"+989{str(uuid.uuid4().int)[:9]}"


@pytest.mark.asyncio
async def test_admin_audit_log_rejects_update_delete_and_truncate() -> None:
    async with SESSION_FACTORY() as session:
        actor = await users_repo.create(session, phone=_phone(), role="admin")
        entry = await audit_repo.create(
            session,
            actor_user_id=actor.id,
            action="test_append_only",
            entity_type="test",
            entity_id=str(uuid.uuid4()),
            reason="append-only integration test",
            after={"state": "created"},
        )
        await session.commit()
        entry_id = entry.id
        actor_id = actor.id

    async with SESSION_FACTORY() as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE admin_audit_log SET reason='tampered' WHERE id=:id"),
                {"id": str(entry_id)},
            )
        await session.rollback()

    async with SESSION_FACTORY() as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text("DELETE FROM admin_audit_log WHERE id=:id"),
                {"id": str(entry_id)},
            )
        await session.rollback()

    async with SESSION_FACTORY() as session:
        with pytest.raises(DBAPIError):
            await session.execute(text("TRUNCATE admin_audit_log"))
        await session.rollback()

    # A hard delete of the actor may not rewrite actor_user_id to NULL either.
    async with SESSION_FACTORY() as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text("DELETE FROM users WHERE id=:id"),
                {"id": str(actor_id)},
            )
        await session.rollback()

    async with SESSION_FACTORY() as session:
        row = (
            await session.execute(
                text(
                    "SELECT actor_user_id, action, reason, after "
                    "FROM admin_audit_log WHERE id=:id"
                ),
                {"id": str(entry_id)},
            )
        ).one()
        assert str(row.actor_user_id) == str(actor_id)
        assert row.action == "test_append_only"
        assert row.reason == "append-only integration test"
        assert row.after == {"state": "created"}
