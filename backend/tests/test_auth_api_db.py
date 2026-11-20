"""Real HTTP auth flows against PostgreSQL (transaction boundary regression).

The API tests in ``test_auth_api.py`` replace the auth service with a fake, so they
cannot catch a missing commit in ``get_db``. These tests exercise the real service
through the real dependency chain.
"""

import os
import uuid

import pytest
from app.api.v1.auth import _sms_provider
from app.core.config import get_settings
from app.core.ratelimit import RateLimitRule
from app.main import app
from app.models.credit_account import CreditAccount
from app.models.otp_challenge import OtpChallenge
from app.models.refresh_token import RefreshToken
from app.models.user import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

TEST_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


class RecordingSms:
    def __init__(self) -> None:
        self.sent: dict[str, str] = {}

    async def send_otp(self, phone: str, code: str) -> None:
        self.sent[phone] = code


class AllowAllLimiter:
    async def check(self, key: str, rule: RateLimitRule) -> bool:
        return True


def _phone() -> str:
    return "+989" + str(uuid.uuid4().int % 1_000_000_000).zfill(9)


async def _cleanup(phone: str) -> None:
    async with TEST_SESSION_FACTORY() as session:
        result = await session.execute(select(User.id).where(User.phone == phone))
        user_id = result.scalar_one_or_none()
        if user_id is not None:
            await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
            await session.execute(delete(CreditAccount).where(CreditAccount.user_id == user_id))
            # Users with immutable ledger rows are intentionally left as test residue.
        await session.execute(delete(OtpChallenge).where(OtpChallenge.phone == phone))
        await session.commit()


@pytest.fixture()
async def auth_client():
    phone = _phone()
    sms = RecordingSms()

    app.dependency_overrides[_sms_provider] = lambda: sms
    app.state.rate_limiter = AllowAllLimiter()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost", cookies={"darsyar_csrf": "csrf"}
    ) as client:
        yield client, phone, sms

    app.dependency_overrides.pop(_sms_provider, None)
    app.state.rate_limiter = None
    await _cleanup(phone)


@pytest.mark.asyncio
async def test_otp_roundtrip_persists_and_logout_clears_cookie(auth_client) -> None:
    client, phone, sms = auth_client

    requested = await client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert requested.status_code == 202

    async with TEST_SESSION_FACTORY() as session:
        challenges = (
            await session.execute(select(OtpChallenge).where(OtpChallenge.phone == phone))
        ).scalars().all()
    assert len(challenges) == 1
    assert challenges[0].code_digest != sms.sent[phone]

    verified = await client.post(
        "/api/v1/auth/otp/verify", json={"phone": phone, "code": sms.sent[phone]}
    )
    assert verified.status_code == 200
    assert verified.json()["access_token"]

    async with TEST_SESSION_FACTORY() as session:
        users = (await session.execute(select(User).where(User.phone == phone))).scalars().all()
        tokens = (await session.execute(select(RefreshToken))).scalars().all()
    assert len(users) == 1
    assert any(token.user_id == users[0].id and token.revoked_at is None for token in tokens)

    logged_out = await client.post("/api/v1/auth/logout")
    assert logged_out.status_code == 204
    set_cookie = logged_out.headers.get("set-cookie", "")
    assert 'darsyar_refresh=""' in set_cookie
    assert "Path=/api/v1/auth" in set_cookie

    async with TEST_SESSION_FACTORY() as session:
        revoked = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.user_id == users[0].id)
            )
        ).scalars().all()
    assert revoked and all(token.revoked_at is not None for token in revoked)


@pytest.mark.asyncio
async def test_failed_otp_attempts_are_persisted(auth_client) -> None:
    client, phone, sms = auth_client
    await client.post("/api/v1/auth/otp/request", json={"phone": phone})

    for _ in range(get_settings().otp_max_attempts):
        response = await client.post(
            "/api/v1/auth/otp/verify", json={"phone": phone, "code": "000000"}
        )
        assert response.status_code == 401

    async with TEST_SESSION_FACTORY() as session:
        challenges = (
            await session.execute(select(OtpChallenge).where(OtpChallenge.phone == phone))
        ).scalars().all()
    assert challenges[0].attempts == get_settings().otp_max_attempts

    locked = await client.post(
        "/api/v1/auth/otp/verify", json={"phone": phone, "code": sms.sent[phone]}
    )
    assert locked.status_code == 429
    assert locked.json()["code"] == "otp_attempts_exceeded"
