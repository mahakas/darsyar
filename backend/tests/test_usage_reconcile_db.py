"""تست‌های یکپارچهٔ Slice C-1 روی PostgreSQL واقعی: usage_events + reconcile read-only."""

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
from app.services.fair_use import FairUseService
from app.services.reconcile import ReconcileService
from app.services.reservation import FinanceService
from app.services.usage import UsageService, canonical_usage_fingerprint
from sqlalchemy import exc as sqlalchemy_exc
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


async def _make_user(balance: int) -> tuple[uuid.UUID, uuid.UUID]:
    phone = _new_phone()
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=phone, role="user")
        account = await accounts_repo.create(session, user_id=user.id, available_balance=balance)
        await session.commit()
        return user.id, account.id


async def _ledger_sum(user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return await ledger_repo.sum_balance_affecting(session, user_id)


async def _grant_ledger(user_id: uuid.UUID, amount: int, key: str) -> None:
    async with TEST_SESSION_FACTORY() as session:
        await ledger_repo.create(session, user_id=user_id, kind="plan_grant", amount=amount, idempotency_key=key)
        await session.commit()


async def _spend_ledger(user_id: uuid.UUID, amount: int, key: str) -> None:
    async with TEST_SESSION_FACTORY() as session:
        await ledger_repo.create(session, user_id=user_id, kind="spend", amount=-amount, idempotency_key=key)
        await session.commit()


async def _active_alert_count(user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        result = await session.execute(
            text("SELECT count(*) FROM reconciliation_alerts WHERE user_id = :u AND resolved_at IS NULL"),
            {"u": str(user_id)},
        )
        return int(result.scalar_one())


async def _alert_count(user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        result = await session.execute(
            text("SELECT count(*) FROM reconciliation_alerts WHERE user_id = :u"), {"u": str(user_id)}
        )
        return int(result.scalar_one())


# ---------------------------------------------------------------- usage_events

@pytest.mark.asyncio
async def test_usage_record_new_event() -> None:
    user_id, _ = await _make_user(0)
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        event = await service.record_event(
            user_id=user_id, event_key="reservation:{00000000-0000-0000-0000-000000000001}:usage:1",
            kind="message_usage", token_count=120, estimated=False,
        )
        assert event.id and event.token_count == 120
        assert not event.estimated
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        rows = await session.execute(text("SELECT count(*) FROM usage_events WHERE user_id = :u"), {"u": str(user_id)})
        assert rows.scalar_one() == 1


@pytest.mark.asyncio
async def test_usage_retry_same_key_same_payload_returns_existing() -> None:
    user_id, _ = await _make_user(0)
    key = "event:1"
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        first = await service.record_event(user_id=user_id, event_key=key, kind="message_usage", token_count=10)
        second = await service.record_event(user_id=user_id, event_key=key, kind="message_usage", token_count=10)
        assert first.id == second.id
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        rows = await session.execute(text("SELECT count(*) FROM usage_events WHERE user_id = :u"), {"u": str(user_id)})
        assert rows.scalar_one() == 1


@pytest.mark.asyncio
async def test_usage_same_key_different_payload_conflict() -> None:
    user_id, _ = await _make_user(0)
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        await service.record_event(user_id=user_id, event_key="k", kind="message_usage", token_count=10)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        with pytest.raises(AppError) as excinfo:
            await service.record_event(user_id=user_id, event_key="k", kind="message_usage", token_count=99)
        assert excinfo.value.code == "usage_event_conflict"
    async with TEST_SESSION_FACTORY() as session:
        rows = await session.execute(text("SELECT count(*) FROM usage_events WHERE user_id = :u"), {"u": str(user_id)})
        assert rows.scalar_one() == 1


@pytest.mark.asyncio
async def test_usage_concurrent_same_key_single_row() -> None:
    user_id, _ = await _make_user(0)
    key = "concurrent:1"

    async def writer() -> str:
        async with TEST_SESSION_FACTORY() as session:
            service = UsageService(session)
            try:
                event = await service.record_event(user_id=user_id, event_key=key, kind="message_usage", token_count=5)
                await session.commit()
                return str(event.id)
            except AppError as exc:
                await session.rollback()
                return exc.code

    ids = await asyncio.gather(writer(), writer(), writer())
    # همهٔ نویسنده‌ها به همان رکورد همگرا می‌شوند (یک برنده + بازخوانی بقیه).
    assert len(set(ids)) == 1
    async with TEST_SESSION_FACTORY() as session:
        rows = await session.execute(text("SELECT count(*) FROM usage_events WHERE user_id = :u"), {"u": str(user_id)})
        assert rows.scalar_one() == 1


@pytest.mark.asyncio
async def test_usage_new_event_same_reservation_allowed() -> None:
    user_id, _ = await _make_user(100)
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 10, idempotency_key="k-u1", payload_fingerprint="f-u1")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        first = await service.record_event(
            user_id=user_id, reservation_id=reservation_id, event_key=f"reservation:{reservation_id}:usage:1",
            kind="message_usage", token_count=10,
        )
        second = await service.record_event(
            user_id=user_id, reservation_id=reservation_id, event_key=f"reservation:{reservation_id}:usage:2",
            kind="message_usage", token_count=20,
        )
        assert first.event_key != second.event_key
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        rows = await session.execute(text("SELECT count(*) FROM usage_events WHERE user_id = :u"), {"u": str(user_id)})
        assert rows.scalar_one() == 2


@pytest.mark.asyncio
async def test_usage_reservation_ownership_mismatch() -> None:
    owner_id, _ = await _make_user(100)
    stranger_id, _ = await _make_user(0)
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(owner_id, 10, idempotency_key="k-u2", payload_fingerprint="f-u2")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        with pytest.raises(AppError) as excinfo:
            await service.record_event(
                user_id=stranger_id, reservation_id=reservation_id,
                event_key=f"reservation:{reservation_id}:usage:1", kind="message_usage", token_count=5,
            )
        assert excinfo.value.code == "reservation_ownership_mismatch"
    async with TEST_SESSION_FACTORY() as session:
        rows = await session.execute(text("SELECT count(*) FROM usage_events WHERE user_id = :u"), {"u": str(stranger_id)})
        assert rows.scalar_one() == 0


@pytest.mark.asyncio
async def test_usage_rollback_leaves_no_row() -> None:
    user_id, _ = await _make_user(0)
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        await service.record_event(user_id=user_id, event_key="rb:1", kind="message_usage", token_count=3)
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        rows = await session.execute(text("SELECT count(*) FROM usage_events WHERE user_id = :u"), {"u": str(user_id)})
        assert rows.scalar_one() == 0


@pytest.mark.asyncio
async def test_usage_immutability_trigger_blocks_update_delete() -> None:
    user_id, _ = await _make_user(0)
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        await service.record_event(user_id=user_id, event_key="imm:1", kind="message_usage", token_count=7)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(sqlalchemy_exc.SQLAlchemyError) as excinfo:
            await session.execute(text("UPDATE usage_events SET token_count = 0 WHERE user_id = :u"), {"u": str(user_id)})
        assert "usage_events_immutable" in str(excinfo.value)
        await session.rollback()
        with pytest.raises(sqlalchemy_exc.SQLAlchemyError) as excinfo:
            await session.execute(text("DELETE FROM usage_events WHERE user_id = :u"), {"u": str(user_id)})
        assert "usage_events_immutable" in str(excinfo.value)
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        rows = await session.execute(text("SELECT count(*) FROM usage_events WHERE user_id = :u"), {"u": str(user_id)})
        assert rows.scalar_one() == 1


@pytest.mark.asyncio
async def test_usage_range_count_and_validation() -> None:
    user_id, _ = await _make_user(0)
    start = datetime.now(UTC) - timedelta(minutes=10)
    async with TEST_SESSION_FACTORY() as session:
        service = UsageService(session)
        for i in range(3):
            await service.record_event(user_id=user_id, event_key=f"r:{i}", kind="message_usage", token_count=1)
        await session.commit()
    end = datetime.now(UTC) + timedelta(minutes=10)
    async with TEST_SESSION_FACTORY() as session:
        service = FairUseService(session)
        assert await service.count_events(user_id, start, end) == 3
        assert await service.count_events(user_id, end, end + timedelta(days=1)) == 0
        with pytest.raises(AppError):
            await service.count_events(user_id, end, start)
        with pytest.raises(AppError):
            await service.count_events(user_id, datetime.now(), end)


# --------------------------------------------------------------- reconciliation

@pytest.mark.asyncio
async def test_reconcile_equal_ledger_no_alert() -> None:
    user_id, _ = await _make_user(500)
    await _grant_ledger(user_id, 500, "grant-eq")
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        summary = await service.reconcile_credits(user_id=user_id)
        assert summary.scanned == 1
        assert summary.alerts_upserted == 0
        assert summary.alerts_resolved == 0
        assert summary.mismatches == 0
        await session.commit()
    assert await _active_alert_count(user_id) == 0


@pytest.mark.asyncio
async def test_reconcile_diff_within_or_equal_threshold_no_alert() -> None:
    user_id, _ = await _make_user(501)
    await _grant_ledger(user_id, 500, "grant-le")
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        summary = await service.reconcile_credits(user_id=user_id)
        assert summary.mismatches == 0
        await session.commit()
    assert await _active_alert_count(user_id) == 0
    # diff دقیقاً برابر threshold (1) → بدون هشدار
    user2, _ = await _make_user(501)
    await _grant_ledger(user2, 500, "grant-eq1")
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        summary = await service.reconcile_credits(user_id=user2)
        assert summary.mismatches == 0
        await session.commit()
    assert await _active_alert_count(user2) == 0


@pytest.mark.asyncio
async def test_reconcile_diff_above_threshold_creates_warning_no_financial_change() -> None:
    user_id, account_id = await _make_user(502)
    await _grant_ledger(user_id, 500, "grant-w")
    ledger_before = await _ledger_sum(user_id)
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        summary = await service.reconcile_credits(user_id=user_id)
        assert summary.mismatches == 1
        assert summary.alerts_upserted == 1
        await session.commit()
    assert await _active_alert_count(user_id) == 1
    assert (await _ledger_sum(user_id)) == ledger_before
    async with TEST_SESSION_FACTORY() as session:
        account = await accounts_repo.get_for_update(session, user_id)
        assert account.available_balance == 502
        row = (
            await session.execute(
                text("SELECT severity, context, occurrences FROM reconciliation_alerts WHERE user_id = :u AND resolved_at IS NULL"),
                {"u": str(user_id)},
            )
        ).one()
        assert row[0] == "warning"
        assert row[1] == {"available_balance": 502, "ledger_sum": 500, "diff": 2}
        assert row[2] == 1


@pytest.mark.asyncio
async def test_reconcile_resolves_active_after_fix_and_reoccurs() -> None:
    user_id, _ = await _make_user(502)
    await _grant_ledger(user_id, 500, "grant-r")
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        await service.reconcile_credits(user_id=user_id)
        await session.commit()
    assert await _active_alert_count(user_id) == 1
    # رفع مغایرت: ledger را به 502 می‌رسانیم
    await _grant_ledger(user_id, 2, "grant-fix")
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        summary = await service.reconcile_credits(user_id=user_id)
        assert summary.alerts_resolved == 1
        await session.commit()
    assert await _active_alert_count(user_id) == 0
    assert await _alert_count(user_id) == 1
    # وقوع مجدد همان مغایرت → هشدار جدید فعال
    await _spend_ledger(user_id, 2, "spend-reopen")
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        await service.reconcile_credits(user_id=user_id)
        await session.commit()
    assert await _active_alert_count(user_id) == 1
    assert await _alert_count(user_id) == 2


@pytest.mark.asyncio
async def test_reconcile_upsert_increments_occurrences_without_new_active() -> None:
    user_id, _ = await _make_user(502)
    await _grant_ledger(user_id, 500, "grant-o")
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        await service.reconcile_credits(user_id=user_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        await service.reconcile_credits(user_id=user_id)
        await session.commit()
    assert await _active_alert_count(user_id) == 1
    async with TEST_SESSION_FACTORY() as session:
        row = (
            await session.execute(text("SELECT occurrences FROM reconciliation_alerts WHERE user_id = :u AND resolved_at IS NULL"), {"u": str(user_id)})
        ).scalar_one()
        assert row == 2


@pytest.mark.asyncio
async def test_reconcile_concurrent_upserts_single_active() -> None:
    user_id, _ = await _make_user(502)
    await _grant_ledger(user_id, 500, "grant-c")

    async def run() -> None:
        async with TEST_SESSION_FACTORY() as session:
            service = ReconcileService(session)
            await service.reconcile_credits(user_id=user_id)
            await session.commit()

    await asyncio.gather(run(), run())
    assert await _active_alert_count(user_id) == 1
    async with TEST_SESSION_FACTORY() as session:
        row = (await session.execute(text("SELECT occurrences FROM reconciliation_alerts WHERE user_id = :u AND resolved_at IS NULL"), {"u": str(user_id)})).scalar_one()
        assert row == 2


@pytest.mark.asyncio
async def test_reconcile_batch_cursor_scans_forward() -> None:
    user_ids: list[uuid.UUID] = []
    for i in range(6):
        uid, _ = await _make_user(502)
        await _grant_ledger(uid, 500, f"grant-b-{i}")
        user_ids.append(uid)
    cursor: uuid.UUID | None = None
    seen: set[uuid.UUID] = set()
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        for _ in range(500):
            summary = await service.reconcile_credits(batch_limit=2, cursor_user_id=cursor)
            assert summary.scanned <= 2
            seen.update(summary.scanned_user_ids)
            if set(user_ids) <= seen:
                break
            if summary.next_cursor is None:
                break
            assert cursor is None or summary.next_cursor > cursor
            cursor = summary.next_cursor
        else:
            pytest.fail("target users not reached with cursor")
        await session.commit()
    assert set(user_ids) <= seen
    assert len(seen) >= 6
    async with TEST_SESSION_FACTORY() as session:
        # همهٔ شش کاربر هدف دقیقاً یک بار هشدار فعال دارند (پیمایش رو به جلو بدون تکرار).
        for uid in user_ids:
            assert await _active_alert_count(uid) == 1


@pytest.mark.asyncio
async def test_reconcile_invalid_batch_limit() -> None:
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        with pytest.raises(AppError) as excinfo:
            await service.reconcile_credits(batch_limit=0)
        assert excinfo.value.code == "invalid_batch_limit"


@pytest.mark.asyncio
async def test_reconcile_alert_context_privacy() -> None:
    user_id, _ = await _make_user(502)
    await _grant_ledger(user_id, 500, "grant-p")
    async with TEST_SESSION_FACTORY() as session:
        service = ReconcileService(session)
        await service.reconcile_credits(user_id=user_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        context_raw = (await session.execute(text("SELECT context FROM reconciliation_alerts WHERE user_id = :u AND resolved_at IS NULL"), {"u": str(user_id)})).scalar_one()
        assert set(context_raw.keys()) == {"available_balance", "ledger_sum", "diff"}
        assert "phone" not in str(context_raw)
        assert "token" not in str(context_raw).lower()


@pytest.mark.asyncio
async def test_canonical_fingerprint_stable_and_identity_scoped() -> None:
    user_id, _ = await _make_user(0)
    fp1 = canonical_usage_fingerprint(user_id=user_id, event_key="e1", kind="k", token_count=1, estimated=False, reservation_id=None)
    fp2 = canonical_usage_fingerprint(user_id=user_id, event_key="e1", kind="k", token_count=1, estimated=False, reservation_id=None)
    assert fp1 == fp2
    fp3 = canonical_usage_fingerprint(user_id=user_id, event_key="e1", kind="k", token_count=2, estimated=False, reservation_id=None)
    assert fp1 != fp3
