"""قرارداد و پیاده‌سازی Redis برای ریت‌لیمیت (R-113/R-114)."""

from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError


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
