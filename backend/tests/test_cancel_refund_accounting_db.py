"""تست‌های حسابداری لغو فوری/refund با رزروهای فعال (Phase 2 fix).

تأیید می‌کند که `_apply_cancellation_effect` و `decide_refund` فقط بخش غیررزروشده
(remaining - reserved) را باطل و از موجودی کسر می‌کنند و هرگز بدهیِ ازپیش‌ثبت‌شدهٔ
رزروها را دوباره کم نمی‌کنند؛ روی PostgreSQL واقعی (SQLite ممنوع).
سیاست‌های مصوب D-04 / D-05 / OQ-028 دست‌نخورده می‌مانند.
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
from app.repositories import payment_transactions as payments_repo
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


async def _make_admin() -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role="admin")
        await session.commit()
        return user.id


async def _setup_paid_plan(user_id: uuid.UUID, *, credits: int = 100):
    """پرداخت موفق + فعال‌سازی پلن + grant + موجودی/ledger (معادل finalize_succeeded)."""
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.create(
            session, user_id=user_id, product_id="basic", amount_toman=1, credit_grant=credits,
            plan_type="credit", duration_days=30, provider="zarinpal", provider_currency="IRR",
            provider_amount=10, idempotency_key=f"pay-{user_id}-{uuid.uuid4()}", request_fingerprint="f",
        )
        await session.execute(text("UPDATE payment_transactions SET status='succeeded', succeeded_at=now() WHERE id=:i"), {"i": str(payment.id)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, payment.id)
        entitlement = await PlanService(session).process_paid_payment(payment)
        await ledger_repo.create(session, user_id=user_id, kind="plan_grant", amount=credits, idempotency_key=f"gr:{payment.id}")
        await session.execute(text("UPDATE credit_accounts SET available_balance = available_balance + :c WHERE user_id=:u"), {"c": credits, "u": str(user_id)})
        await session.commit()
        grant_id = (await session.execute(text("SELECT id FROM credit_grants WHERE entitlement_id=:e ORDER BY created_at LIMIT 1"), {"e": str(entitlement.id)})).scalar_one()
        return payment.id, entitlement.id, grant_id


async def _add_grant_to_entitlement(user_id: uuid.UUID, entitlement_id: uuid.UUID, amount: int) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        now = datetime.now(UTC)
        grant = await ent_repo.create_grant(
            session, user_id=user_id, entitlement_id=entitlement_id, kind="plan_grant", amount=amount,
            expires_at=now + timedelta(days=30), payment_id=None,
        )
        await session.execute(text("UPDATE credit_accounts SET available_balance = available_balance + :c WHERE user_id=:u"), {"c": amount, "u": str(user_id)})
        await ledger_repo.create(session, user_id=user_id, kind="plan_grant", amount=amount, idempotency_key=f"gr-{grant.id}")
        await session.commit()
        return grant.id


async def _spend_down_grant(user_id: uuid.UUID, grant_id: uuid.UUID, amount: int) -> None:
    async with TEST_SESSION_FACTORY() as session:
        await ent_repo.consume_grant(session, grant_id, amount)
        await ledger_repo.create(session, user_id=user_id, kind="adjust", amount=-amount, idempotency_key=f"spent-{grant_id}")
        await session.execute(text("UPDATE credit_accounts SET available_balance = available_balance - :c WHERE user_id=:u"), {"c": amount, "u": str(user_id)})
        await session.commit()


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


async def _cancel_once(user_id: uuid.UUID, admin_id: uuid.UUID, entitlement_id: uuid.UUID) -> None:
    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_cancellation(user_id, entitlement_id)
        pending = await ent_repo.get_pending_cancellation(session, user_id, entitlement_id)
        assert pending is not None
        await service.decide_cancellation(pending.id, actor_user_id=admin_id, approve=True, reason="audit", mode="immediate")
        await session.commit()


async def _refund_once(
    user_id: uuid.UUID, admin_id: uuid.UUID, payment_id: uuid.UUID, entitlement_id: uuid.UUID, credit_voided: int
) -> None:
    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_refund(user_id=user_id, payment_id=payment_id, entitlement_id=entitlement_id, requested_amount=500000, reason="audit")
        record_id = (await session.execute(text("SELECT id FROM refund_records ORDER BY created_at DESC LIMIT 1"))).scalar_one()
        await service.decide_refund(record_id, actor_user_id=admin_id, approve=True, reason="approved", credit_voided=credit_voided)
        await session.commit()


async def _decide_cancel_attempt(pending_id: uuid.UUID, admin_id: uuid.UUID) -> str:
    async with TEST_SESSION_FACTORY() as session:
        try:
            await PlanService(session).decide_cancellation(pending_id, actor_user_id=admin_id, approve=True, reason="audit", mode="immediate")
            await session.commit()
            return "ok"
        except AppError:
            await session.rollback()
            return "dup"


async def _decide_refund_attempt(record_id: uuid.UUID, admin_id: uuid.UUID, credit_voided: int) -> str:
    async with TEST_SESSION_FACTORY() as session:
        try:
            await PlanService(session).decide_refund(record_id, actor_user_id=admin_id, approve=True, reason="approved", credit_voided=credit_voided)
            await session.commit()
            return "ok"
        except AppError:
            await session.rollback()
            return "dup"


async def _grant_row(grant_id: uuid.UUID):
    async with TEST_SESSION_FACTORY() as session:
        row = (await session.execute(text("SELECT remaining_amount, reserved_amount, lifecycle_reason FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).one()
        return int(row[0]), int(row[1]), row[2]


async def _allocation_row(reservation_id: uuid.UUID):
    async with TEST_SESSION_FACTORY() as session:
        row = (await session.execute(text("SELECT status, consumed_amount, released_amount, voided_amount FROM reservation_credit_allocations WHERE reservation_id=:r"), {"r": str(reservation_id)})).one()
        return row[0], int(row[1]), int(row[2]), int(row[3])


async def _balance(user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return int((await session.execute(text("SELECT available_balance FROM credit_accounts WHERE user_id=:u"), {"u": str(user_id)})).scalar_one())


async def _ledger_sum(user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return int((await session.execute(text("SELECT COALESCE(SUM(amount),0) FROM credit_ledger WHERE user_id=:u"), {"u": str(user_id)})).scalar_one())


async def _ledger_count_kind(user_id: uuid.UUID, kind: str) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return int((await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id=:u AND kind=:k"), {"u": str(user_id), "k": kind})).scalar_one())


# ===========================================================================
# Immediate cancellation
# ===========================================================================

@pytest.mark.asyncio
async def test_cancel_fully_reserved_no_second_debit() -> None:
    """Test A: لغو فوری با grant کاملاً رزروشده — بدون کسر دوم؛ settle داخل مهلت مجاز."""
    uid = await _make_user()
    admin = await _make_admin()
    _, ent_id, grant_id = await _setup_paid_plan(uid, credits=100)
    rid = await _reserve(uid, 100, "A-r")

    await _cancel_once(uid, admin, ent_id)
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)
    assert await _grant_row(grant_id) == (100, 100, "immediate_cancellation")

    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "active" and consumed == 0
    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid)
        await session.commit()
    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "consumed" and consumed == 100
    assert await _ledger_count_kind(uid, "spend") == 1

    err = await _reserve_expect_error(uid, 5, "A-new")
    assert err is not None and err.code == "insufficient_credit"


@pytest.mark.asyncio
async def test_cancel_partially_reserved_voids_only_unreserved() -> None:
    """Test B: لغو فوری با grant نیمه‌رزروشده — دقیقاً ۶۰ باطل؛ ۴۰ باقی برای allocation."""
    uid = await _make_user()
    admin = await _make_admin()
    _, ent_id, grant_id = await _setup_paid_plan(uid, credits=100)
    rid = await _reserve(uid, 40, "B-r")

    await _cancel_once(uid, admin, ent_id)
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)
    assert await _grant_row(grant_id) == (40, 40, "immediate_cancellation")

    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "active" and consumed == 0
    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid)
        await session.commit()
    assert (await _allocation_row(rid))[:2] == ("consumed", 40)

    err = await _reserve_expect_error(uid, 5, "B-new")
    assert err is not None and err.code == "insufficient_credit"


@pytest.mark.asyncio
async def test_cancel_unreserved_voids_full() -> None:
    """Test C: لغو فوری با grant غیررزروشده — دقیقاً ۱۰۰ باطل."""
    uid = await _make_user()
    admin = await _make_admin()
    _, ent_id, grant_id = await _setup_paid_plan(uid, credits=100)

    await _cancel_once(uid, admin, ent_id)
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)
    assert await _grant_row(grant_id) == (0, 0, "immediate_cancellation")
    err = await _reserve_expect_error(uid, 5, "C-new")
    assert err is not None and err.code == "insufficient_credit"


@pytest.mark.asyncio
async def test_cancel_settle_and_release_after_invalidation() -> None:
    """Test G (لغو): settle داخل مهلت؛ release پس از مهلت بدون بازگشت/refund."""
    uid = await _make_user()
    admin = await _make_admin()
    _, ent_id, grant_id = await _setup_paid_plan(uid, credits=100)
    rid_settle = await _reserve(uid, 40, "G-c-s")
    rid_release = await _reserve(uid, 10, "G-c-r")

    await _cancel_once(uid, admin, ent_id)
    assert await _grant_row(grant_id) == (50, 50, "immediate_cancellation")

    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid_settle)
        await session.commit()
    assert (await _allocation_row(rid_settle))[:2] == ("consumed", 40)
    assert (await _grant_row(grant_id))[:2] == (10, 10)

    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE reservations SET created_at = now() - interval '20 minutes' WHERE id=:r"), {"r": str(rid_release)})
        await session.commit()
    serr = await _settle_expect_error(rid_release)
    assert serr is not None and serr.code == "reservation_deadline_passed"

    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).release(rid_release, reason="deadline")
        await session.commit()
    status, _, released, voided = await _allocation_row(rid_release)
    assert status == "voided" and released == 0 and voided == 10
    assert (await _grant_row(grant_id))[:2] == (10, 0)
    assert await _ledger_count_kind(uid, "refund") == 0
    assert await _balance(uid) == await _ledger_sum(uid)


@pytest.mark.asyncio
async def test_cancel_idempotent_repeat_decide_blocked() -> None:
    """Test H (لغو): تأیید دوبارهٔ همان درخواست رد می‌شود؛ بدون adjust تکراری."""
    uid = await _make_user()
    admin = await _make_admin()
    _, ent_id, _ = await _setup_paid_plan(uid, credits=100)

    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_cancellation(uid, ent_id)
        pending = await ent_repo.get_pending_cancellation(session, uid, ent_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).decide_cancellation(pending.id, actor_user_id=admin, approve=True, reason="audit", mode="immediate")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(AppError) as excinfo:
            await PlanService(session).decide_cancellation(pending.id, actor_user_id=admin, approve=True, reason="audit", mode="immediate")
        assert excinfo.value.code == "cancellation_not_pending"
    assert await _ledger_count_kind(uid, "adjust") == 1
    assert await _balance(uid) == await _ledger_sum(uid)


# ===========================================================================
# Approved refund
# ===========================================================================

@pytest.mark.asyncio
async def test_refund_fully_reserved_guard_rejects_reserved_debit() -> None:
    """Test D: refund کاملاً رزروشده — کسر اعتبار رزروشده رد می‌شود؛ بدون بدهی دوم."""
    uid = await _make_user()
    admin = await _make_admin()
    payment_id, ent_id, grant_id = await _setup_paid_plan(uid, credits=100)
    rid = await _reserve(uid, 100, "D-r")

    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_refund(user_id=uid, payment_id=payment_id, entitlement_id=ent_id, requested_amount=500000, reason="audit")
        record_id = (await session.execute(text("SELECT id FROM refund_records ORDER BY created_at DESC LIMIT 1"))).scalar_one()
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(AppError) as excinfo:
            await PlanService(session).decide_refund(record_id, actor_user_id=admin, approve=True, reason="approved", credit_voided=100)
        assert excinfo.value.code == "refund_credit_void_exceeds_unreserved"

    assert await _balance(uid) == 0  # منفی نشده؛ کسر دوم رخ نداده
    assert await _grant_row(grant_id) == (100, 100, None)  # باطل نشده
    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "active" and consumed == 0


@pytest.mark.asyncio
async def test_refund_partially_reserved_voids_only_unreserved() -> None:
    """Test E: refund نیمه‌رزروشده — دقیقاً ۶۰ باطل؛ ۴۰ برای allocation باقی می‌ماند."""
    uid = await _make_user()
    admin = await _make_admin()
    payment_id, ent_id, grant_id = await _setup_paid_plan(uid, credits=100)
    rid = await _reserve(uid, 40, "E-r")

    await _refund_once(uid, admin, payment_id, ent_id, credit_voided=60)
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)
    assert await _grant_row(grant_id) == (40, 40, "approved_refund")

    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "active" and consumed == 0
    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid)
        await session.commit()
    assert (await _allocation_row(rid))[:2] == ("consumed", 40)

    err = await _reserve_expect_error(uid, 5, "E-new")
    assert err is not None and err.code == "insufficient_credit"


@pytest.mark.asyncio
async def test_refund_multiple_grants_sum_of_unreserved() -> None:
    """Test F: چند grant مخلوط — مجموع adjust = مجموع بخش‌های غیررزروشده، دقیقاً یک‌بار."""
    uid = await _make_user()
    admin = await _make_admin()
    payment_id, ent_id, g1 = await _setup_paid_plan(uid, credits=100)
    g2 = await _add_grant_to_entitlement(uid, ent_id, 100)
    g3 = await _add_grant_to_entitlement(uid, ent_id, 100)
    g4 = await _add_grant_to_entitlement(uid, ent_id, 100)
    await _spend_down_grant(uid, g4, 100)

    await _reserve(uid, 100, "F-r1")
    await _reserve(uid, 40, "F-r2")

    await _refund_once(uid, admin, payment_id, ent_id, credit_voided=160)
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)
    assert await _grant_row(g1) == (100, 100, "approved_refund")
    assert await _grant_row(g2) == (40, 40, "approved_refund")
    assert await _grant_row(g3) == (0, 0, "approved_refund")
    assert await _grant_row(g4) == (0, 0, "approved_refund")


@pytest.mark.asyncio
async def test_refund_settle_and_release_after_invalidation() -> None:
    """Test G (refund): settle داخل مهلت؛ release پس از مهلت بدون بازگشت/refund."""
    uid = await _make_user()
    admin = await _make_admin()
    payment_id, ent_id, grant_id = await _setup_paid_plan(uid, credits=100)
    rid_settle = await _reserve(uid, 40, "G-r-s")
    rid_release = await _reserve(uid, 10, "G-r-r")

    await _refund_once(uid, admin, payment_id, ent_id, credit_voided=50)
    assert await _grant_row(grant_id) == (50, 50, "approved_refund")

    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid_settle)
        await session.commit()
    assert (await _allocation_row(rid_settle))[:2] == ("consumed", 40)
    assert (await _grant_row(grant_id))[:2] == (10, 10)

    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE reservations SET created_at = now() - interval '20 minutes' WHERE id=:r"), {"r": str(rid_release)})
        await session.commit()
    serr = await _settle_expect_error(rid_release)
    assert serr is not None and serr.code == "reservation_deadline_passed"

    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).release(rid_release, reason="deadline")
        await session.commit()
    status, _, released, voided = await _allocation_row(rid_release)
    assert status == "voided" and released == 0 and voided == 10
    assert (await _grant_row(grant_id))[:2] == (10, 0)
    assert await _ledger_count_kind(uid, "refund") == 0
    assert await _balance(uid) == await _ledger_sum(uid)


@pytest.mark.asyncio
async def test_refund_idempotent_repeat_decide_blocked() -> None:
    """Test H (refund): تأیید دوبارهٔ همان درخواست رد می‌شود؛ بدون adjust/refund تکراری."""
    uid = await _make_user()
    admin = await _make_admin()
    payment_id, ent_id, _ = await _setup_paid_plan(uid, credits=100)

    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_refund(user_id=uid, payment_id=payment_id, entitlement_id=ent_id, requested_amount=500000, reason="audit")
        record_id = (await session.execute(text("SELECT id FROM refund_records ORDER BY created_at DESC LIMIT 1"))).scalar_one()
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).decide_refund(record_id, actor_user_id=admin, approve=True, reason="approved", credit_voided=100)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(AppError) as excinfo:
            await PlanService(session).decide_refund(record_id, actor_user_id=admin, approve=True, reason="approved", credit_voided=100)
        assert excinfo.value.code == "refund_not_pending"
    assert await _ledger_count_kind(uid, "adjust") == 1
    assert await _balance(uid) == await _ledger_sum(uid)


# ===========================================================================
# Concurrency
# ===========================================================================

@pytest.mark.asyncio
async def test_cancel_waits_on_grant_lock_held_by_reservation() -> None:
    """Test I (لغو): هنگام نگه‌داشتن قفل ردیف grant، لغو فوری منتظر می‌ماند."""
    uid = await _make_user()
    admin = await _make_admin()
    _, ent_id, grant_id = await _setup_paid_plan(uid, credits=100)

    async with TEST_SESSION_FACTORY() as holder:
        await ent_repo.get_grant_for_update(holder, grant_id)
        task = asyncio.create_task(_cancel_once(uid, admin, ent_id))
        await asyncio.sleep(0.05)
        done, _ = await asyncio.wait([task], timeout=1.0)
        assert task not in done, "cancellation باید روی قفل ردیف grant صبر کند"
        await holder.rollback()
    await task

    assert (await _grant_row(grant_id))[2] == "immediate_cancellation"
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)
    err = await _reserve_expect_error(uid, 5, "I-c-new")
    assert err is not None and err.code == "insufficient_credit"


@pytest.mark.asyncio
async def test_refund_waits_on_grant_lock_held_by_reservation() -> None:
    """Test I (refund): هنگام نگه‌داشتن قفل ردیف grant، refund منتظر می‌ماند."""
    uid = await _make_user()
    admin = await _make_admin()
    payment_id, ent_id, grant_id = await _setup_paid_plan(uid, credits=100)

    async with TEST_SESSION_FACTORY() as holder:
        await ent_repo.get_grant_for_update(holder, grant_id)
        task = asyncio.create_task(_refund_once(uid, admin, payment_id, ent_id, credit_voided=100))
        await asyncio.sleep(0.05)
        done, _ = await asyncio.wait([task], timeout=1.0)
        assert task not in done, "refund باید روی قفل ردیف grant صبر کند"
        await holder.rollback()
    await task

    assert (await _grant_row(grant_id))[2] == "approved_refund"
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)
    err = await _reserve_expect_error(uid, 5, "I-r-new")
    assert err is not None and err.code == "insufficient_credit"


@pytest.mark.asyncio
async def test_two_workers_cancel_compete_single_adjust() -> None:
    """Test I: دو worker هم‌زمان همان لغو را تأیید می‌کنند — فقط یکی برنده؛ یک adjust."""
    uid = await _make_user()
    admin = await _make_admin()
    _, ent_id, _ = await _setup_paid_plan(uid, credits=100)

    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_cancellation(uid, ent_id)
        pending = await ent_repo.get_pending_cancellation(session, uid, ent_id)
        await session.commit()

    results = await asyncio.gather(
        _decide_cancel_attempt(pending.id, admin),
        _decide_cancel_attempt(pending.id, admin),
    )
    assert sorted(results) == ["dup", "ok"]
    assert await _ledger_count_kind(uid, "adjust") == 1
    assert await _balance(uid) == await _ledger_sum(uid)


@pytest.mark.asyncio
async def test_two_workers_refund_compete_single_adjust() -> None:
    """Test I: دو worker هم‌زمان همان refund را تأیید می‌کنند — فقط یکی برنده؛ یک adjust."""
    uid = await _make_user()
    admin = await _make_admin()
    payment_id, ent_id, _ = await _setup_paid_plan(uid, credits=100)

    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_refund(user_id=uid, payment_id=payment_id, entitlement_id=ent_id, requested_amount=500000, reason="audit")
        record_id = (await session.execute(text("SELECT id FROM refund_records ORDER BY created_at DESC LIMIT 1"))).scalar_one()
        await session.commit()

    results = await asyncio.gather(
        _decide_refund_attempt(record_id, admin, 100),
        _decide_refund_attempt(record_id, admin, 100),
    )
    assert sorted(results) == ["dup", "ok"]
    assert await _ledger_count_kind(uid, "adjust") == 1
    assert await _balance(uid) == await _ledger_sum(uid)
