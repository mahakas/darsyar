"""تست‌های سخت‌سازی هم‌زمانی مالی (Phase 2): مرزهای reserve/settle در برابر admin_void.

- صرفاً تست‌های یکپارچهٔ PostgreSQL واقعی؛ SQLite ممنوع (R-213).
- هم‌زمانی با قفل ردیف PostgreSQL (SELECT ... FOR UPDATE) به‌عنوان مانع صریح
  تراکنش کنترل می‌شود؛ بدون تغییر در کد تولید.
- سیاست‌های تجاری مصوب (D-04/D-05/OQ-028) دست‌نخورده می‌مانند.
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import entitlements as ent_repo
from app.repositories import reservations as reservations_repo
from app.repositories import users as users_repo
from app.services.plans import PlanService
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


async def _make_entitlement_and_grant(user_id: uuid.UUID, *, amount: int = 500, expiry_days: int = 30):
    async with TEST_SESSION_FACTORY() as session:
        now = datetime.now(UTC)
        entitlement = await ent_repo.create_entitlement(
            session, user_id=user_id, product_id="basic", plan_type="credit",
            activated_at=now - timedelta(days=1), expires_at=now + timedelta(days=expiry_days),
            granted_credits=amount, payment_id=None, snapshot={},
        )
        grant = await ent_repo.create_grant(
            session, user_id=user_id, entitlement_id=entitlement.id, kind="plan_grant",
            amount=amount, expires_at=now + timedelta(days=expiry_days), payment_id=None,
        )
        await session.execute(
            text("UPDATE credit_accounts SET available_balance = available_balance + :c WHERE user_id=:u"),
            {"c": amount, "u": str(user_id)},
        )
        await ledger_repo.create(session, user_id=user_id, kind="plan_grant", amount=amount, idempotency_key=f"gr-{grant.id}")
        await session.commit()
        return entitlement.id, grant.id


async def _reserve(user_id: uuid.UUID, amount: int, key: str) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, amount, idempotency_key=key, payload_fingerprint="f")
        await session.commit()
        return reservation.id


async def _reserve_expect_error(user_id: uuid.UUID, amount: int, key: str) -> AppError | None:
    async with TEST_SESSION_FACTORY() as session:
        try:
            await FinanceService(session).reserve_credit(user_id, amount, idempotency_key=key, payload_fingerprint="f")
            await session.commit()
            return None
        except AppError as exc:
            await session.rollback()
            return exc


async def _settle_expect_error(reservation_id: uuid.UUID) -> AppError | None:
    async with TEST_SESSION_FACTORY() as session:
        try:
            await FinanceService(session).settle(reservation_id)
            await session.commit()
            return None
        except AppError as exc:
            await session.rollback()
            return exc


async def _void(session, entitlement_id: uuid.UUID, reason: str, *, effective_at: datetime | None = None, now: datetime | None = None) -> None:
    eff = effective_at or datetime.now(UTC)
    mom = now or datetime.now(UTC)
    await ent_repo.void_all_grants_of_entitlement(session, entitlement_id, reason=reason, effective_at=eff, now=mom)


async def _void_runner(entitlement_id: uuid.UUID, reason: str) -> None:
    async with TEST_SESSION_FACTORY() as session:
        await _void(session, entitlement_id, reason)
        await session.commit()


async def _grant_row(grant_id: uuid.UUID):
    async with TEST_SESSION_FACTORY() as session:
        row = (
            await session.execute(
                text("SELECT remaining_amount, reserved_amount, lifecycle_reason, voided_at FROM credit_grants WHERE id=:g"),
                {"g": str(grant_id)},
            )
        ).one()
        return int(row[0]), int(row[1]), row[2], row[3]


async def _allocation_row(reservation_id: uuid.UUID):
    async with TEST_SESSION_FACTORY() as session:
        row = (
            await session.execute(
                text("SELECT status, consumed_amount, released_amount, voided_amount FROM reservation_credit_allocations WHERE reservation_id=:r"),
                {"r": str(reservation_id)},
            )
        ).one()
        return row[0], int(row[1]), int(row[2]), int(row[3])


async def _reservation_status(reservation_id: uuid.UUID) -> str:
    async with TEST_SESSION_FACTORY() as session:
        return (await session.execute(text("SELECT status FROM reservations WHERE id=:r"), {"r": str(reservation_id)})).scalar_one()


async def _balance(user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return int((await session.execute(text("SELECT available_balance FROM credit_accounts WHERE user_id=:u"), {"u": str(user_id)})).scalar_one())


async def _ledger_sum(user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return int((await session.execute(text("SELECT COALESCE(SUM(amount),0) FROM credit_ledger WHERE user_id=:u"), {"u": str(user_id)})).scalar_one())


async def _ledger_count_kind(user_id: uuid.UUID, kind: str) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return int((await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id=:u AND kind=:k"), {"u": str(user_id), "k": kind})).scalar_one())


# ---------------------------------------------------------------------------
# Test A — reserve versus admin_void
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reserve_vs_admin_void_void_lock_wins_no_allocation() -> None:
    """A2: admin_void نخست قفل grant را می‌گیرد؛ reserve بلاک می‌شود و پس از commit بازاعتبارسنجی می‌کند."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)

    async with TEST_SESSION_FACTORY() as vs:
        await _void(vs, ent_id, "admin_void")
        rtask = asyncio.create_task(_reserve_expect_error(uid, 10, "a2-new"))
        await asyncio.sleep(0.05)
        done, _ = await asyncio.wait([rtask], timeout=1.0)
        assert rtask not in done, "reserve باید روی قفل ردیف grant بلاک بماند"
        await vs.commit()

    err = await rtask
    assert err is not None and err.code == "insufficient_credit"
    async with TEST_SESSION_FACTORY() as session:
        n = (await session.execute(text("SELECT count(*) FROM reservations WHERE idempotency_key='a2-new'"))).scalar_one()
        assert n == 0


@pytest.mark.asyncio
async def test_reserve_vs_admin_void_reserve_first_then_void_blocks_new_and_settle() -> None:
    """A1: reserve پیش از void commit می‌شود؛ سپس void رزروهای جدید را می‌بندد و settle pre-void را رد می‌کند."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)
    rid = await _reserve(uid, 100, "a1")

    async with TEST_SESSION_FACTORY() as vs:
        await _void(vs, ent_id, "admin_void")
        await vs.commit()

    rem, res, reason, _ = await _grant_row(grant_id)
    assert (rem, res, reason) == (100, 100, "admin_void")
    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "active" and consumed == 0

    err = await _reserve_expect_error(uid, 10, "a1-new")
    assert err is not None and err.code == "insufficient_credit"
    serr = await _settle_expect_error(rid)
    assert serr is not None and serr.code == "invalid_reservation_state"


@pytest.mark.asyncio
async def test_admin_void_waits_on_grant_lock_held_by_reserve_window() -> None:
    """A1 (ترتیب قفل): هنگام نگه‌داشتن قفل ردیف grant (پنجرهٔ reserve)، admin_void منتظر می‌ماند."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)

    async with TEST_SESSION_FACTORY() as holder:
        await ent_repo.get_grant_for_update(holder, grant_id)
        vtask = asyncio.create_task(_void_runner(ent_id, "admin_void"))
        await asyncio.sleep(0.05)
        done, _ = await asyncio.wait([vtask], timeout=1.0)
        assert vtask not in done, "admin_void باید روی قفل ردیف grant صبر کند"
        await holder.rollback()
    await vtask


# ---------------------------------------------------------------------------
# Test B — settle versus admin_void
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settle_vs_admin_void_void_lock_wins_rejects_settle() -> None:
    """B2: admin_void نخست قفل را می‌گیرد؛ settle بلاک و سپس با خطای دامنه رد می‌شود."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)
    rid = await _reserve(uid, 100, "b2")

    async with TEST_SESSION_FACTORY() as vs:
        await _void(vs, ent_id, "admin_void")
        stask = asyncio.create_task(_settle_expect_error(rid))
        await asyncio.sleep(0.05)
        done, _ = await asyncio.wait([stask], timeout=1.0)
        assert stask not in done, "settle باید روی قفل ردیف grant بلاک بماند"
        await vs.commit()

    serr = await stask
    assert serr is not None and serr.code == "invalid_reservation_state"
    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "active" and consumed == 0
    assert await _reservation_status(rid) == "pending"


@pytest.mark.asyncio
async def test_settle_vs_admin_void_settle_first_then_void_preserves_state() -> None:
    """B1: settle پیش از ثبت دلیل اتفاق می‌افتد؛ سپس void مقادیر remaining/reserved را حفظ می‌کند."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)
    rid = await _reserve(uid, 100, "b1")

    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid)
        await session.commit()
    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "consumed" and consumed == 100

    await _void_runner(ent_id, "admin_void")
    rem, res, reason, _ = await _grant_row(grant_id)
    assert (rem, res, reason) == (0, 0, "admin_void")
    assert await _balance(uid) == await _ledger_sum(uid)


@pytest.mark.asyncio
async def test_admin_void_waits_on_grant_lock_held_by_settle_window() -> None:
    """B1 (ترتیب قفل): هنگام نگه‌داشتن قفل ردیف grant (پنجرهٔ settle)، admin_void منتظر می‌ماند."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)

    async with TEST_SESSION_FACTORY() as holder:
        await ent_repo.get_grant_for_update(holder, grant_id)
        vtask = asyncio.create_task(_void_runner(ent_id, "admin_void"))
        await asyncio.sleep(0.05)
        done, _ = await asyncio.wait([vtask], timeout=1.0)
        assert vtask not in done, "admin_void باید روی قفل ردیف grant صبر کند"
        await holder.rollback()
    await vtask


# ---------------------------------------------------------------------------
# Test C — defense-in-depth: post-void allocation guards
# ---------------------------------------------------------------------------

async def _manual_reservation_with_allocation(user_id: uuid.UUID, grant_id: uuid.UUID, amount: int, key: str) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        reservation = await reservations_repo.create(
            session, user_id=user_id, kind="credit", amount=amount, idempotency_key=key, payload_fingerprint="f"
        )
        await ent_repo.create_allocation(session, reservation_id=reservation.id, grant_id=grant_id, amount=amount)
        await session.commit()
        return reservation.id


@pytest.mark.asyncio
async def test_immediate_cancellation_post_void_allocation_rejected() -> None:
    """C: allocation با created_at >= voided_at تحت immediate_cancellation باید رد شود."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)
    await _void_runner(ent_id, "immediate_cancellation")
    rid = await _manual_reservation_with_allocation(uid, grant_id, 50, "post-cancel")
    serr = await _settle_expect_error(rid)
    assert serr is not None and serr.code == "invalid_reservation_state"


@pytest.mark.asyncio
async def test_approved_refund_post_void_allocation_rejected() -> None:
    """C: allocation با created_at >= voided_at تحت approved_refund باید رد شود."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)
    await _void_runner(ent_id, "approved_refund")
    rid = await _manual_reservation_with_allocation(uid, grant_id, 50, "post-refund")
    serr = await _settle_expect_error(rid)
    assert serr is not None and serr.code == "invalid_reservation_state"


@pytest.mark.asyncio
async def test_admin_void_post_void_allocation_rejected() -> None:
    """C: admin_void حتی allocation با created_at < voided_at را رد می‌کند (D-05)."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)
    await _void_runner(ent_id, "admin_void")
    rid = await _manual_reservation_with_allocation(uid, grant_id, 50, "post-void")
    serr = await _settle_expect_error(rid)
    assert serr is not None and serr.code == "invalid_reservation_state"


# ---------------------------------------------------------------------------
# Test D — natural_expiry: انتقال واقعی lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_natural_expiry_job_records_reason_and_blocks_new() -> None:
    """D: کار انقضای طبیعی (expire_due_entitlements) بدون رزرو فعال، دلیل را ثبت و رزرو جدید را می‌بندد."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)

    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE plan_entitlements SET expires_at = now() - interval '1 hour' WHERE id=:e"), {"e": str(ent_id)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        n = await PlanService(session).expire_due_entitlements(batch_limit=10, user_id=uid)
        assert n == 1
        await session.commit()

    rem, res, reason, _ = await _grant_row(grant_id)
    assert reason == "natural_expiry"
    assert (rem, res) == (0, 0)
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)

    err = await _reserve_expect_error(uid, 10, "d-new")
    assert err is not None and err.code == "insufficient_credit"


@pytest.mark.asyncio
async def test_natural_expiry_grandfather_deadline_and_no_resurrect() -> None:
    """D: انتقال واقعی natural_expiry (void_all_grants_of_entitlement) — grandfather، مرز مهلت و بدون بازگشت."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid)
    rid_grandfather = await _reserve(uid, 100, "d-grandfather")
    rid_deadline = await _reserve(uid, 100, "d-deadline")

    async with TEST_SESSION_FACTORY() as session:
        await _void(session, ent_id, "natural_expiry")
        await session.commit()

    rem, res, reason, _ = await _grant_row(grant_id)
    assert reason == "natural_expiry"
    assert rem == res == 200  # بخش غیررزروشده باطل شد؛ بخش رزروشده بازگردانده نشد

    err = await _reserve_expect_error(uid, 10, "d-new2")
    assert err is not None and err.code == "insufficient_credit"

    # grandfather: settle در مهلت اصلی حتی پس از انقضای طبیعی موفق است
    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid_grandfather)
        await session.commit()
    status, consumed, _, _ = await _allocation_row(rid_grandfather)
    assert status == "consumed" and consumed == 100

    # مرز مهلت: settle پس از مهلت رد می‌شود
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE reservations SET created_at = now() - interval '20 minutes' WHERE id=:r"), {"r": str(rid_deadline)})
        await session.commit()
    serr = await _settle_expect_error(rid_deadline)
    assert serr is not None and serr.code == "reservation_deadline_passed"

    # release پس از انقضا: باطل بدون بازگشت و بدون refund
    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).release(rid_deadline, reason="deadline")
        await session.commit()
    status2, _, released, voided = await _allocation_row(rid_deadline)
    assert status2 == "voided" and voided == 100 and released == 0
    rem2, res2, _, _ = await _grant_row(grant_id)
    assert res2 == 0 and rem2 == 100  # ادعای reserved حذف شد؛ بدون بازگشت (no resurrection)

    assert await _ledger_count_kind(uid, "refund") == 0
    assert await _balance(uid) == await _ledger_sum(uid)
