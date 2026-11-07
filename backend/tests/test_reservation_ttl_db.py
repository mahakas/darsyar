"""تست‌های OQ-027 (مهلت ۱۵ دقیقه)، legacy، گارد 0013 و reconciliation allocations."""

import asyncio
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import entitlements as ent_repo
from app.repositories import users as users_repo
from app.services.reconcile import ReconcileService
from app.services.reservation import FinanceService
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


async def _make_user() -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role="user")
        await accounts_repo.create(session, user_id=user.id, available_balance=0)
        await session.commit()
        return user.id


async def _add_grant(user_id: uuid.UUID, *, amount: int, expires_at: datetime | None = None) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        grant = await ent_repo.create_grant(
            session, user_id=user_id, entitlement_id=None, kind="plan_grant", amount=amount,
            expires_at=expires_at, payment_id=None,
        )
        await session.execute(text("UPDATE credit_accounts SET available_balance = available_balance + :c WHERE user_id=:u"), {"c": amount, "u": str(user_id)})
        await ledger_repo.create(session, user_id=user_id, kind="plan_grant", amount=amount, idempotency_key=f"gr-{grant.id}")
        await session.commit()
        return grant.id


async def _reserve(user_id: uuid.UUID, amount: int, key: str):
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, amount, idempotency_key=key, payload_fingerprint="f")
        await session.commit()
        return reservation.id


@pytest.mark.asyncio
async def test_settle_before_deadline_after_grant_expiry_succeeds() -> None:
    """OQ-027 گزینهٔ A: grant هنگام رزرو معتبر است؛ پس از انقضای طبیعی آن، settle قبل از مهلت موفق است."""
    uid = await _make_user()
    expiry = datetime.now(UTC) + timedelta(days=30)
    grant_id = await _add_grant(uid, amount=20, expires_at=expiry)
    rid = await _reserve(uid, 10, "ttl1")
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE credit_grants SET expires_at = now() - interval '1 hour' WHERE id=:g"), {"g": str(grant_id)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(rid)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        row = (await session.execute(text("SELECT status, consumed_amount FROM reservation_credit_allocations WHERE reservation_id=:r"), {"r": str(rid)})).one()
        assert row[0] == "consumed" and int(row[1]) == 10
        g = (await session.execute(text("SELECT remaining_amount, reserved_amount FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).one()
        assert (int(g[0]), int(g[1])) == (10, 0)


@pytest.mark.asyncio
async def test_settle_after_deadline_rejected() -> None:
    uid = await _make_user()
    await _add_grant(uid, amount=20)
    rid = await _reserve(uid, 5, "ttl2")
    async with TEST_SESSION_FACTORY() as session:
        # قدیمی‌کردن created_at رزرو برای عبور از مهلت
        await session.execute(text("UPDATE reservations SET created_at = now() - interval '20 minutes' WHERE id=:r"), {"r": str(rid)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(AppError) as excinfo:
            await service.settle(rid)
        assert excinfo.value.code == "reservation_deadline_passed"


@pytest.mark.asyncio
async def test_deadline_job_releases_overdue_no_resurrection() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid, amount=20)
    rid = await _reserve(uid, 8, "ttl3")
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE reservations SET created_at = now() - interval '20 minutes' WHERE id=:r"), {"r": str(rid)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        assert await service.expire_reservation_deadlines(batch_limit=10, user_id=uid) == 1
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        status = (await session.execute(text("SELECT status FROM reservations WHERE id=:r"), {"r": str(rid)})).scalar_one()
        assert status == "released"
        g = (await session.execute(text("SELECT remaining_amount, reserved_amount FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).one()
        assert (int(g[0]), int(g[1])) == (20, 0)  # بازگشت به منبع معتبر


@pytest.mark.asyncio
async def test_legacy_fallback_blocked_when_grants_exist() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid, amount=5)
    # تمام grant رزرو می‌شود تا eligible=0 شود؛ fallback نباید فعال شود.
    await _reserve(uid, 5, "legacy1")
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(AppError) as excinfo:
            await service.reserve_credit(uid, 1, idempotency_key="legacy2", payload_fingerprint="f")
        assert excinfo.value.code == "insufficient_credit"
    async with TEST_SESSION_FACTORY() as session:
        count = (await session.execute(text("SELECT count(*) FROM reservations WHERE user_id=:u"), {"u": str(uid)})).scalar_one()
        assert count == 1
        g = (await session.execute(text("SELECT reserved_amount FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).scalar_one()
        assert int(g) == 5


@pytest.mark.asyncio
async def test_migration_0013_downgrade_guard() -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = get_settings().database_url
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "downgrade", "0012_plan_entitlements"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert result.returncode != 0
    assert "forward-only" in result.stderr
    async with TEST_SESSION_FACTORY() as session:
        exists = (await session.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_name='reservation_credit_allocations'"))).scalar_one()
        assert exists == 1


@pytest.mark.asyncio
async def test_reconcile_allocations_detects_reserved_mismatch() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid, amount=20)
    await _reserve(uid, 5, "rc1")
    async with TEST_SESSION_FACTORY() as session:
        # تزریق ناسازگاری: reserved دستی بدون allocation
        await session.execute(text("UPDATE credit_grants SET reserved_amount = 10 WHERE id=:g"), {"g": str(grant_id)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        report = await ReconcileService(session).reconcile_allocations(user_id=uid)
        assert report["mismatch_count"] == 1
        assert report["mismatches"][0]["type"] == "reserved_vs_allocations"
