"""وابستگی‌های پایهٔ API؛ احراز هویت و ابزارهای امنیتی."""

import uuid
from collections.abc import Callable
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import RateLimitRule, RedisRateLimiter
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories import users as users_repo

__all__ = [
    "AsyncSession",
    "get_db",
    "get_redis",
    "rate_limit_dependency",
    "client_ip",
    "get_current_user",
]

UNAUTHORIZED = AppError("unauthorized", 401, "احراز هویت لازم است.")


async def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


async def check_rate_limit(request: Request, key: str, rule: RateLimitRule) -> None:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        limiter = RedisRateLimiter(request.app.state.redis)
        request.app.state.rate_limiter = limiter
    try:
        allowed = await limiter.check(key, rule)
    except RedisError:
        # R-115: مسیرهای OTP fail-closed؛ وقتی Redis در دسترس نباشد 503 برمی‌گردد.
        raise AppError("rate_limit_unavailable", 503, "سرویس محدودیت نرخ موقتاً در دسترس نیست.") from None
    if not allowed:
        raise AppError("rate_limited", 429, "تعداد درخواست‌ها از سقف مجاز گذشت.")


def rate_limit_dependency(key_builder: Callable[[Request], str], rule: RateLimitRule) -> Callable[..., Any]:
    async def dependency(request: Request) -> None:
        await check_rate_limit(request, key_builder(request), rule)

    return dependency


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise UNAUTHORIZED
    token = authorization[len("Bearer "):]
    try:
        payload = decode_token(token, "access")
        user_id = uuid.UUID(str(payload.get("sub")))
    except Exception:
        raise UNAUTHORIZED from None
    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        raise UNAUTHORIZED
    return user


def client_ip(request: Request) -> str:
    """IP کلاینت با پشتیبانی proxy قابل‌اعتماد؛ به X-Forwarded-For خام اعتماد نمی‌شود."""
    settings = get_settings()
    trusted_proxies = {ip.strip() for ip in settings.forwarded_allow_ips.split(",")} if settings.forwarded_allow_ips else set()
    if getattr(request.client, "host", None) in trusted_proxies:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return getattr(request.client, "host", "unknown") or "unknown"
