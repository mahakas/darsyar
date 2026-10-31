"""طھط³طھâ€Œظ‡ط§غŒ غŒع©ظ¾ط§ط±ع†ظ‡ظ” Fair-Use (ADR-050) ط±ظˆغŒ PostgreSQL ظˆط§ظ‚ط¹غŒ."""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import users as users_repo
from app.services.fair_use import COUNTABLE_EVENT_KIND, FairUseService, month_period
from app.services.usage import UsageService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

TEST_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


def _new_phone() -> str:
    return f"+989{str(uuid.uuid4().int)[:9]}"


async def _make_user(role: str = "user", balance: int = 100) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role=role)
        await accounts_repo.create(session, user_id=user.id, available_balance=balance)
        await session.commit()
        return user.id


async def _add_usage(
    user_id: uuid.UUID,
    count: int,
    *,
    kind: str = COUNTABLE_EVENT_KIND,
    estimated: bool = False,
    at: datetime | None = None,
) -> None:
    """ط¯ط±ط¬ ظ…ط³طھظ‚غŒظ… ط§ظ†ط¨ظˆظ‡ ط±ظˆغŒط¯ط§ط¯ ط¨ط§ created_at ظ‚ط§ط¨ظ„â€Œع©ظ†طھط±ظ„ (طµط±ظپط§ظ‹ ط¨ط±ط§غŒ ظپغŒع©ط³ع†ط±).

    trigger طھط؛غŒغŒط±ظ†ط§ظ¾ط°غŒط±غŒ ظپظ‚ط· UPDATE/DELETE ط±ط§ ط±ط¯ ظ…غŒâ€Œع©ظ†ط¯ط› INSERT ظ…ط¬ط§ط² ط§ط³طھ.
    """
    from app.models.usage_event import UsageEvent
    from app.services.usage import canonical_usage_fingerprint
    from sqlalchemy.dialects.postgresql import insert

    moment = at or datetime.now(UTC)
    key_prefix = f"fu:{user_id}:{int(moment.timestamp())}"
    rows = []
    for i in range(count):
        event_key = f"{key_prefix}:{i}:{kind}:{estimated}"
        rows.append(
            {
                "user_id": user_id,
                "event_key": event_key,
                "kind": kind,
                "token_count": 100,
                "estimated": estimated,
                "payload_fingerprint": canonical_usage_fingerprint(
                    user_id=user_id,
                    event_key=event_key,
                    kind=kind,
                    token_count=100,
                    estimated=estimated,
                    reservation_id=None,
                ),
                "created_at": moment,
            }
        )
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(insert(UsageEvent), rows)
        await session.commit()


async def _flag_count(user_id: uuid.UUID, period_key: str | None = None) -> int:
    async with TEST_SESSION_FACTORY() as session:
        if period_key is None:
            result = await session.execute(text("SELECT count(*) FROM abuse_flags WHERE user_id = :u"), {"u": str(user_id)})
        else:
            result = await session.execute(
                text("SELECT count(*) FROM abuse_flags WHERE user_id = :u AND period_key = :p"),
                {"u": str(user_id), "p": period_key},
            )
        return int(result.scalar_one())


@pytest.mark.asyncio
async def test_detect_below_threshold_no_flag() -> None:
    user_id = await _make_user()
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 9999)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        flag = await service.detect_and_flag(user_id)
        await session.commit()
        assert flag is None
    assert await _flag_count(user_id, period.key) == 0


@pytest.mark.asyncio
async def test_detect_exactly_threshold_no_flag() -> None:
    user_id = await _make_user()
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 10000)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        flag = await service.detect_and_flag(user_id)
        await session.commit()
        assert flag is None
    assert await _flag_count(user_id, period.key) == 0


@pytest.mark.asyncio
async def test_detect_above_threshold_creates_flag() -> None:
    user_id = await _make_user()
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 10001)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        flag = await service.detect_and_flag(user_id)
        await session.commit()
        assert flag is not None
        assert flag.status == "active"
        assert flag.period_key == period.key
        assert flag.observed_count == 10001
        assert flag.threshold == 10000
    assert await _flag_count(user_id, period.key) == 1


@pytest.mark.asyncio
async def test_repeated_detection_single_flag_original_metadata_preserved() -> None:
    user_id = await _make_user()
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 10001)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        first = await service.detect_and_flag(user_id)
        second = await service.detect_and_flag(user_id)
        await session.commit()
        assert first is not None and second is not None
        assert first.id == second.id
    assert await _flag_count(user_id, period.key) == 1


@pytest.mark.asyncio
async def test_concurrent_detection_single_flag() -> None:
    user_id = await _make_user()
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 10001)

    async def detect() -> str:
        async with TEST_SESSION_FACTORY() as session:
            service = FairUseService(session)
            flag = await service.detect_and_flag(user_id)
            await session.commit()
            return str(flag.id) if flag else "none"

    ids = await asyncio.gather(detect(), detect(), detect())
    ids = [i for i in ids if i != "none"]
    assert len(set(ids)) == 1
    assert await _flag_count(user_id, period.key) == 1


@pytest.mark.asyncio
async def test_resolved_flag_not_reactivated_by_repeated_detection() -> None:
    user_id = await _make_user(role="admin")
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 10001)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        flag = await service.detect_and_flag(user_id)
        await service.resolve_flag(flag.id, actor_user_id=user_id, reason="manual review ok")
        await session.commit()
        flag_id = flag.id
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        again = await service.detect_and_flag(user_id)
        await session.commit()
        assert again is not None
        assert again.id == flag_id
        assert again.status == "resolved"
    assert await _flag_count(user_id, period.key) == 1


@pytest.mark.asyncio
async def test_different_users_same_period_and_same_user_different_periods() -> None:
    u1 = await _make_user()
    u2 = await _make_user()
    period = month_period(datetime.now(UTC))
    await _add_usage(u1, 10001)
    await _add_usage(u2, 10001)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        await service.detect_and_flag(u1)
        await service.detect_and_flag(u2)
        await session.commit()
    assert await _flag_count(u1, period.key) == 1
    assert await _flag_count(u2, period.key) == 1
    # ع©ط§ط±ط¨ط± غŒع©ط³ط§ظ† ط¯ط± ط¯ظˆط±ظ‡ظ” ظ‚ط¨ظ„غŒ
    prev = month_period(datetime.now(UTC) - timedelta(days=40))
    await _add_usage(u1, 10001, at=prev.start_utc + timedelta(days=10))
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        await service.detect_and_flag(u1, now=prev.start_utc + timedelta(days=10))
        await session.commit()
    assert await _flag_count(u1, prev.key) == 1


@pytest.mark.asyncio
async def test_non_countable_and_other_users_excluded() -> None:
    user_id = await _make_user()
    other = await _make_user()
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 10, kind="usage_other")
    await _add_usage(other, 10001)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        count = await service.count_for_period(user_id, period)
        assert count == 0
        flag = await service.detect_and_flag(user_id)
        await session.commit()
        assert flag is None
    assert await _flag_count(user_id, period.key) == 0


@pytest.mark.asyncio
async def test_previous_and_next_month_excluded() -> None:
    user_id = await _make_user()
    period = month_period(datetime.now(UTC))
    prev = month_period(datetime.now(UTC) - timedelta(days=35))
    nxt = month_period(datetime.now(UTC) + timedelta(days=35))
    await _add_usage(user_id, 10001, at=prev.start_utc + timedelta(days=10))
    await _add_usage(user_id, 10)
    await _add_usage(user_id, 10001, at=nxt.start_utc + timedelta(days=10))
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        assert await service.count_for_period(user_id, period) == 10
        flag = await service.detect_and_flag(user_id)
        await session.commit()
        assert flag is None
    assert await _flag_count(user_id, period.key) == 0


@pytest.mark.asyncio
async def test_duplicate_event_key_does_not_inflate_count() -> None:
    user_id = await _make_user()
    period = month_period(datetime.now(UTC))
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        first = await service.record_event(
            user_id=user_id, event_key="dup:1", kind=COUNTABLE_EVENT_KIND, token_count=100
        )
        second = await service.record_event(
            user_id=user_id, event_key="dup:1", kind=COUNTABLE_EVENT_KIND, token_count=100
        )
        assert first.id == second.id
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        assert await service.count_for_period(user_id, period) == 1


@pytest.mark.asyncio
async def test_flag_creation_does_not_alter_financial_state() -> None:
    user_id = await _make_user(balance=50)
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 10001)
    async with TEST_SESSION_FACTORY() as session:
        before_ledger = await ledger_repo.sum_balance_affecting(session, user_id)
        account = await accounts_repo.get_for_update(session, user_id)
        before_balance = account.available_balance
        service = FairUseService(session)
        await service.detect_and_flag(user_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        assert await ledger_repo.sum_balance_affecting(session, user_id) == before_ledger
        assert (await accounts_repo.get_for_update(session, user_id)).available_balance == before_balance
    assert await _flag_count(user_id, period.key) == 1


@pytest.mark.asyncio
async def test_admin_resolution_requires_admin_and_reason() -> None:
    user_id = await _make_user()
    admin_id = await _make_user(role="admin")
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 10001)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        flag = await service.detect_and_flag(user_id)
        await session.commit()
        flag_id = flag.id
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        with pytest.raises(AppError) as excinfo:
            await service.resolve_flag(flag_id, actor_user_id=user_id, reason="self resolve")
        assert excinfo.value.code == "admin_required"
        with pytest.raises(AppError) as excinfo:
            await service.resolve_flag(flag_id, actor_user_id=admin_id, reason="   ")
        assert excinfo.value.code == "resolution_reason_required"
        with pytest.raises(AppError) as excinfo:
            await service.resolve_flag(uuid.uuid4(), actor_user_id=admin_id, reason="x")
        assert excinfo.value.code == "abuse_flag_not_found"
        await session.rollback()
    assert await _flag_count(user_id, period.key) == 1


@pytest.mark.asyncio
async def test_admin_resolution_records_actor_timestamp_reason() -> None:
    user_id = await _make_user()
    admin_id = await _make_user(role="admin")
    await _add_usage(user_id, 10001)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        flag = await service.detect_and_flag(user_id)
        resolved = await service.resolve_flag(flag.id, actor_user_id=admin_id, reason="reviewed ok")
        await session.commit()
        assert resolved.status == "resolved"
        assert resolved.resolved_by == admin_id
        assert resolved.resolution_reason == "reviewed ok"
        assert resolved.resolved_at is not None
        assert resolved.observed_count == 10001
        assert resolved.threshold == 10000
    async with TEST_SESSION_FACTORY() as session:
        row = (
            await session.execute(text("SELECT status, observed_count, threshold, resolved_by, resolution_reason FROM abuse_flags WHERE id = :f"), {"f": str(flag.id)})
        ).one()
        assert row[0] == "resolved"
        assert (row[1], row[2]) == (10001, 10000)
        assert row[3] == admin_id
        assert row[4] == "reviewed ok"


@pytest.mark.asyncio
async def test_double_resolution_rejected() -> None:
    user_id = await _make_user()
    admin_id = await _make_user(role="admin")
    await _add_usage(user_id, 10001)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        flag = await service.detect_and_flag(user_id)
        await service.resolve_flag(flag.id, actor_user_id=admin_id, reason="first")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        with pytest.raises(AppError) as excinfo:
            await service.resolve_flag(flag.id, actor_user_id=admin_id, reason="second")
        assert excinfo.value.code == "abuse_flag_already_resolved"
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        row = (
            await session.execute(text("SELECT resolution_reason FROM abuse_flags WHERE id = :f"), {"f": str(flag.id)})
        ).one()
        assert row[0] == "first"


@pytest.mark.asyncio
async def test_abuse_flags_isolated_from_reconciliation_alerts() -> None:
    user_id = await _make_user()
    period = month_period(datetime.now(UTC))
    await _add_usage(user_id, 10001)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        await service.detect_and_flag(user_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        alerts = (
            await session.execute(
                text("SELECT count(*) FROM reconciliation_alerts WHERE user_id = :u"), {"u": str(user_id)}
            )
        ).scalar_one()
        assert alerts == 0
    assert await _flag_count(user_id, period.key) == 1
