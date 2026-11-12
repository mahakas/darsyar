"""PostgreSQL integration tests for the Phase 7 admin authorization primitive."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.api.deps import require_admin
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_token
from app.repositories import users as users_repo
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)
ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)


def _phone() -> str:
    return f"+989{str(uuid.uuid4().int)[:9]}"


def _request_with_token(token: str | None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode("ascii")))
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/admin/probe",
            "raw_path": b"/admin/probe",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50123),
            "server": ("testserver", 80),
        }
    )


def _access_token(user_id: uuid.UUID, role_claim: str) -> str:
    return create_token(
        str(user_id),
        role_claim,
        "access",
        str(uuid.uuid4()),
        lifetime=timedelta(minutes=5),
    )


@pytest.mark.asyncio
async def test_require_admin_returns_503_before_auth_when_no_active_admin_is_seeded() -> None:
    async with SESSION_FACTORY() as session:
        admins = await users_repo.list_admins(session)
        now = datetime.now(UTC)
        for admin in admins:
            admin.deleted_at = now
        await session.flush()

        with pytest.raises(AppError) as exc_info:
            await require_admin(_request_with_token(None), session)

        assert exc_info.value.code == "no_admin_seeded"
        assert exc_info.value.http_status == 503
        await session.rollback()


@pytest.mark.asyncio
async def test_require_admin_uses_database_role_not_jwt_role_claim() -> None:
    async with SESSION_FACTORY() as session:
        regular_user = await users_repo.create(session, phone=_phone(), role="user")
        admin_user = await users_repo.create(session, phone=_phone(), role="admin")
        await session.flush()

        # A user cannot promote themselves by setting role=admin in a signed claim.
        forged_user_token = _access_token(regular_user.id, "admin")
        with pytest.raises(AppError) as denied:
            await require_admin(_request_with_token(forged_user_token), session)
        assert denied.value.code == "admin_required"
        assert denied.value.http_status == 403

        # Conversely, the persisted admin role is authoritative even if the token
        # carries an old/stale role claim; no privilege is granted from JWT metadata.
        admin_token = _access_token(admin_user.id, "user")
        resolved = await require_admin(_request_with_token(admin_token), session)
        assert resolved.id == admin_user.id
        assert resolved.role == "admin"
        await session.rollback()
