"""تست‌های fallback امن ریت‌لیمیت مبتنی بر PostgreSQL (OQ-006/R-115)."""

import asyncio
import os
import uuid

import pytest
from app.core.config import get_settings
from app.core.ratelimit import PostgresRateLimiter, RateLimitRule
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

TEST_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


@pytest.mark.asyncio
async def test_fallback_limiter_atomic_bounded() -> None:
    limiter = PostgresRateLimiter(TEST_SESSION_FACTORY)
    key = f"chat:fallback:{uuid.uuid4()}"
    rule = RateLimitRule(limit=3, window_seconds=300)
    results = await asyncio.gather(*[limiter.check(key, rule) for _ in range(6)])
    assert results.count(True) == 3
    assert results.count(False) == 3


@pytest.mark.asyncio
async def test_fallback_limiter_window_resets() -> None:
    limiter = PostgresRateLimiter(TEST_SESSION_FACTORY)
    # warm up connection so the sub-second assertions are not skewed by pool creation
    await limiter.check(f"chat:fallback:warmup:{uuid.uuid4()}", RateLimitRule(limit=1000, window_seconds=300))
    key = f"chat:fallback:reset:{uuid.uuid4()}"
    rule = RateLimitRule(limit=1, window_seconds=300)
    assert await limiter.check(key, rule) is True
    assert await limiter.check(key, rule) is False
    # simulate window expiry deterministically (no wall-clock race under NullPool)
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    expired = datetime.now(UTC) - timedelta(seconds=400)
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE rate_limit_counters SET window_start = :when WHERE key = :k"), {"when": expired, "k": key})
        await session.commit()
    assert await limiter.check(key, rule) is True


@pytest.mark.asyncio
async def test_fallback_limiter_distinct_keys_independent() -> None:
    limiter = PostgresRateLimiter(TEST_SESSION_FACTORY)
    rule = RateLimitRule(limit=1, window_seconds=300)
    k1 = f"chat:fallback:k1:{uuid.uuid4()}"
    k2 = f"chat:fallback:k2:{uuid.uuid4()}"
    assert await limiter.check(k1, rule) is True
    assert await limiter.check(k1, rule) is False
    assert await limiter.check(k2, rule) is True
