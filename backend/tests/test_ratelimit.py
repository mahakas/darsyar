import pytest
from app.core.ratelimit import RateLimitRule, RedisRateLimiter


class FakePipeline:
    def __init__(self, store: dict[str, int], ttl: dict[str, int]) -> None:
        self._store = store
        self._ttl = ttl
        self._ops: list[tuple] = []

    def incr(self, key: str) -> "FakePipeline":
        self._ops.append(("incr", key))
        return self

    def expire(self, key: str, seconds: int) -> "FakePipeline":
        self._ops.append(("expire", key, seconds))
        return self

    async def execute(self) -> list[object]:
        results: list[object] = []
        for op in self._ops:
            if op[0] == "incr":
                self._store[op[1]] = self._store.get(op[1], 0) + 1
                results.append(self._store[op[1]])
            else:
                self._ttl[op[1]] = op[2]
                results.append(True)
        return results


class FakeRedis:
    def __init__(self, store: dict[str, int] | None = None, ttl: dict[str, int] | None = None) -> None:
        self._store = store or {}
        self._ttl = ttl or {}

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self._store, self._ttl)


def test_rule_requires_positive_values() -> None:
    with pytest.raises(ValueError):
        RateLimitRule(0, 60)
    with pytest.raises(ValueError):
        RateLimitRule(5, 0)


async def test_redis_limiter_allows_until_limit() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis)
    rule = RateLimitRule(3, 60)
    for expected in (True, True, True, False):
        assert await limiter.check("k", rule) is expected


async def test_redis_limiter_sets_expiry() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis)
    await limiter.check("k", RateLimitRule(3, 60))
    assert redis._ttl["k"] == 60
