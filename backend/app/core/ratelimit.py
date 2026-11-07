"""قرارداد و پیاده‌سازی ریت‌لیمیت (R-113/R-114) + fallback امن مبتنی بر PostgreSQL (OQ-006)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """سقف و پنجرهٔ یک ریت‌لیمیت از تنظیمات را نگه می‌دارد."""

    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.limit <= 0 or self.window_seconds <= 0:
            raise ValueError("Rate limit and window must be positive")


class RateLimiter(Protocol):
    async def check(self, key: str, rule: RateLimitRule) -> bool: ...


class RedisRateLimiter:
    """پنجرهٔ ثابت با INCR/EXPIRE اتمیک؛ برای لایهٔ per phone/user و IP."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def check(self, key: str, rule: RateLimitRule) -> bool:
        try:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.expire(key, rule.window_seconds)
            count, _ = await pipe.execute()
        except RedisError:
            raise
        return int(count) <= rule.limit


class PostgresRateLimiter:
    """fallback امن برای ریت‌لیمیت هنگام ازکارافتادن Redis (OQ-006/R-115).

    از یک شمارندهٔ اتمیک مبتنی بر PostgreSQL (`rate_limit_counters`) استفاده می‌کند.
    این جدول فقط پذیرش/محدودیت نرخ است و به‌هیچ‌وجه منبع حقیقت مالی نیست (R-124).
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def check(self, key: str, rule: RateLimitRule) -> bool:
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=rule.window_seconds)
        statement = text(
            """
            INSERT INTO rate_limit_counters (key, count, window_start)
            VALUES (:key, 1, :now)
            ON CONFLICT (key) DO UPDATE SET
                count = CASE WHEN rate_limit_counters.window_start < :cutoff
                             THEN 1 ELSE rate_limit_counters.count + 1 END,
                window_start = CASE WHEN rate_limit_counters.window_start < :cutoff
                             THEN :now ELSE rate_limit_counters.window_start END
            RETURNING count
            """
        )
        async with self._session_factory() as session:
            result = await session.execute(statement, {"key": key, "now": now, "cutoff": cutoff})
            row = result.fetchone()
            await session.commit()
            if row is None:
                return False
            return int(row[0]) <= rule.limit
