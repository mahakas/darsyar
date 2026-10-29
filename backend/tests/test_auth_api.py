"""تست‌های مسیر احراز هویت با سرویس جایگزین؛ بدون DB و شبکه (R-216)."""

import pytest
from app.api.v1.auth import _auth_service
from app.core.errors import AppError
from app.core.ratelimit import RateLimitRule
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class FakeLimiter:
    def __init__(self, allowed: bool = True, redis_error: bool = False) -> None:
        self._allowed = allowed
        self._redis_error = redis_error

    async def check(self, key: str, rule: RateLimitRule) -> bool:
        if self._redis_error:
            from redis.exceptions import RedisError

            raise RedisError("simulated")
        return self._allowed


class FakeUser:
    def __init__(self) -> None:
        self.id = "00000000-0000-0000-0000-000000000001"
        self.phone = "+989121234567"
        self.name = None
        self.role = "user"


class FakeSms:
    sent: list[tuple[str, str]] = []

    async def send_otp(self, phone: str, code: str) -> None:
        FakeSms.sent.append((phone, code))


class FakeAuthService:
    def __init__(self) -> None:
        self.sms = FakeSms()

    async def request_otp(self, raw_phone: str) -> None:
        return None

    async def verify_otp(self, raw_phone: str, code: str):
        if code != "123456":
            raise AppError("invalid_otp", 401, "کد واردشده نامعتبر یا منقضی است.")
        return "access-token", "refresh-token", "jti", 900, FakeUser()

    async def rotate_refresh(self, raw_token: str):
        if raw_token == "revoked-old-refresh":
            raise AppError("refresh_conflict_retry", 409, "نشست در حال چرخش است؛ کمی بعد دوباره تلاش کنید.")
        if raw_token != "refresh-token":
            raise AppError("invalid_refresh_token", 401, "نشست نامعتبر یا منقضی است.")
        return "access-token-2", "refresh-token-2", "jti-2", 900, FakeUser()

    async def logout_family(self, raw_token: str) -> None:
        return None


@pytest.fixture()
def app() -> FastAPI:
    from app.main import app as real_app

    real_app.dependency_overrides[_auth_service] = lambda: FakeAuthService()
    real_app.state.rate_limiter = FakeLimiter()
    yield real_app
    real_app.dependency_overrides.clear()


async def _client(app: FastAPI, cookies: dict[str, str] | None = None) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost", cookies=cookies)


async def test_otp_request_returns_identical_202(app: FastAPI) -> None:
    async with await _client(app) as client:
        response = await client.post("/api/v1/auth/otp/request", json={"phone": "09121234567"})
    assert response.status_code == 202
    assert response.json() == {"status": "sent"}


async def test_otp_verify_success_sets_httponly_cookie(app: FastAPI) -> None:
    async with await _client(app) as client:
        response = await client.post("/api/v1/auth/otp/verify", json={"phone": "09121234567", "code": "123456"})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "access-token"
    assert body["user"]["phone"] == "+989121234567"
    assert body["token_type"] == "bearer"
    assert "refresh_token" not in body
    cookies = response.cookies
    assert cookies.get("darsyar_refresh") == "refresh-token"
    assert cookies.get("darsyar_csrf")


async def test_otp_verify_wrong_code_401(app: FastAPI) -> None:
    async with await _client(app) as client:
        response = await client.post("/api/v1/auth/otp/verify", json={"phone": "09121234567", "code": "000000"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_otp"


async def test_refresh_requires_csrf(app: FastAPI) -> None:
    async with await _client(app, {"darsyar_refresh": "refresh-token"}) as client:
        response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_token_mismatch"


async def test_refresh_origin_mismatch_rejected(app: FastAPI) -> None:
    cookies = {"darsyar_refresh": "refresh-token", "darsyar_csrf": "csrf"}
    async with await _client(app, cookies) as client:
        response = await client.post(
            "/api/v1/auth/refresh",
            headers={"x-csrf-token": "csrf", "origin": "https://evil.example"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_origin_rejected"


async def test_refresh_rotates_with_valid_csrf(app: FastAPI) -> None:
    cookies = {"darsyar_refresh": "refresh-token", "darsyar_csrf": "csrf"}
    async with await _client(app, cookies) as client:
        response = await client.post(
            "/api/v1/auth/refresh",
            headers={"x-csrf-token": "csrf", "origin": "http://localhost:5173"},
        )
    assert response.status_code == 200
    assert response.json()["access_token"] == "access-token-2"
    assert response.cookies.get("darsyar_refresh") == "refresh-token-2"


async def test_grace_conflict_returns_409_without_set_cookie(app: FastAPI) -> None:
    """بازندهٔ چرخش (replay در grace): 409 و بدون Set-Cookie تا کوکی جدیدتر بازنویسی نشود."""
    cookies = {"darsyar_refresh": "revoked-old-refresh", "darsyar_csrf": "csrf"}
    async with await _client(app, cookies) as client:
        response = await client.post(
            "/api/v1/auth/refresh",
            headers={"x-csrf-token": "csrf", "origin": "http://localhost:5173"},
        )
    assert response.status_code == 409
    assert response.json()["code"] == "refresh_conflict_retry"
    assert "set-cookie" not in {k.lower() for k in response.headers.keys()}
    assert client.cookies.get("darsyar_refresh") == "revoked-old-refresh"


async def test_reordered_responses_cannot_overwrite_newer_cookie(app: FastAPI) -> None:
    """پاسخ برنده کوکی جدید می‌دهد؛ پاسخ 409 بازنده بدون Set-Cookie نمی‌تواند آن را بازنویسی کند."""
    winner_cookies = {"darsyar_refresh": "refresh-token", "darsyar_csrf": "csrf"}
    loser_cookies = {"darsyar_refresh": "revoked-old-refresh", "darsyar_csrf": "csrf"}
    headers = {"x-csrf-token": "csrf", "origin": "http://localhost:5173"}

    async with await _client(app, winner_cookies) as winner_client:
        winner = await winner_client.post("/api/v1/auth/refresh", headers=headers)
        assert winner.status_code == 200
        set_cookie = winner.headers.get("set-cookie") or ""
        assert "darsyar_refresh=refresh-token-2" in set_cookie

        async with await _client(app, loser_cookies) as loser_client:
            loser = await loser_client.post("/api/v1/auth/refresh", headers=headers)
            assert loser.status_code == 409
            # بازنده هیچ Set-Cookie صادر نمی‌کند؛ پس حتی اگر پاسخش دیرتر برسد،
            # نمی‌تواند کوکی جدیدتر (برنده) را بازنویسی کند.
            assert "set-cookie" not in {k.lower() for k in loser.headers.keys()}


async def test_rate_limit_unavailable_fails_closed(app: FastAPI) -> None:
    app.state.rate_limiter = FakeLimiter(redis_error=True)
    async with await _client(app) as client:
        response = await client.post("/api/v1/auth/otp/request", json={"phone": "09121234567"})
    assert response.status_code == 503
    assert response.json()["code"] == "rate_limit_unavailable"


async def test_rate_limit_exceeded_429(app: FastAPI) -> None:
    app.state.rate_limiter = FakeLimiter(allowed=False)
    async with await _client(app) as client:
        response = await client.post("/api/v1/auth/otp/request", json={"phone": "09121234567"})
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"


async def test_validation_error_has_standard_shape(app: FastAPI) -> None:
    async with await _client(app) as client:
        response = await client.post("/api/v1/auth/otp/request", json={"phone": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert "issues" in response.json()
