"""تست‌های حسابداری انقضای طبیعی با رزروهای فعال (Phase 2 fix).

تأیید می‌کند که `expire_due_entitlements` فقط بخش غیررزروشده (remaining - reserved)
را باطل و از موجودی کسر می‌کند، هرگز بدهیِ ازپیش‌ثبت‌شدهٔ رزروها را دوباره کم نمی‌کند،
و قواعد مصوب OQ-027 / D-04 / D-05 را حفظ می‌کند. روی PostgreSQL واقعی (SQLite ممنوع).
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


async def _make_entitlement_and_grant(user_id: uuid.UUID, *, amount: int = 100):
    async with TEST_SESSION_FACTORY() as session:
        now = datetime.now(UTC)
        entitlement = await ent_repo.create_entitlement(
            session, user_id=user_id, product_id="basic", plan_type="credit",
            activated_at=now - timedelta(days=1), expires_at=now + timedelta(days=30),
            granted_credits=amount, payment_id=None, snapshot={},
        )
        grant = await ent_repo.create_grant(
            session, user_id=user_id, entitlement_id=entitlement.id, kind="plan_grant", amount=amount,
            expires_at=now + timedelta(days=30), payment_id=None,
        )
        await session.execute(
            text("UPDATE credit_accounts SET available_balance = available_balance + :c WHERE user_id=:u"),
            {"c": amount, "u": str(user_id)},
        )
        await ledger_repo.create(session, user_id=user_id, kind="plan_grant", amount=amount, idempotency_key=f"gr-{grant.id}")
        await session.commit()
        return entitlement.id, grant.id


async def _add_grant_to_entitlement(user_id: uuid.UUID, entitlement_id: uuid.UUID, amount: int) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        now = datetime.now(UTC)
        grant = await ent_repo.create_grant(
            session, user_id=user_id, entitlement_id=entitlement_id, kind="plan_grant", amount=amount,
            expires_at=now + timedelta(days=30), payment_id=None,
        )
        await session.execute(
            text("UPDATE credit_accounts SET available_balance = available_balance + :c WHERE user_id=:u"),
            {"c": amount, "u": str(user_id)},
        )
        await ledger_repo.create(session, user_id=user_id, kind="plan_grant", amount=amount, idempotency_key=f"gr-{grant.id}")
        await session.commit()
        return grant.id


async def _spend_down_grant(user_id: uuid.UUID, grant_id: uuid.UUID, amount: int) -> None:
    async with TEST_SESSION_FACTORY() as session:
        await ent_repo.consume_grant(session, grant_id, amount)
        await ledger_repo.create(session, user_id=user_id, kind="adjust", amount=-amount, idempotency_key=f"spent-{grant_id}")
        await session.execute(
            text("UPDATE credit_accounts SET available_balance = available_balance - :c WHERE user_id=:u"),
            {"c": amount, "u": str(user_id)},
        )
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


async def _force_expiry_and_run_job(entitlement_id: uuid.UUID, user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE plan_entitlements SET expires_at = now() - interval '1 hour' WHERE id=:e"), {"e": str(entitlement_id)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        n = await PlanService(session).expire_due_entitlements(batch_limit=20, user_id=user_id)
        await session.commit()
        return n


async def _expiry_runner(entitlement_id: uuid.UUID, user_id: uuid.UUID) -> int:
    return await _force_expiry_and_run_job(entitlement_id, user_id)


async def _grant_row(grant_id: uuid.UUID):
    async with TEST_SESSION_FACTORY() as session:
        row = (
            await session.execute(
                text("SELECT remaining_amount, reserved_amount, lifecycle_reason FROM credit_grants WHERE id=:g"),
                {"g": str(grant_id)},
            )
        ).one()
        return int(row[0]), int(row[1]), row[2]


async def _allocation_row(reservation_id: uuid.UUID):
    async with TEST_SESSION_FACTORY() as session:
        row = (
            await session.execute(
                text("SELECT status, consumed_amount, released_amount, voided_amount FROM reservation_credit_allocations WHERE reservation_id=:r"),
                {"r": str(reservation_id)},
            )
        ).one()
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


# ---------------------------------------------------------------------------
# Test A — fully reserved grant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_fully_reserved_grant_no_second_debit() -> None:
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid, amount=100)
    rid = await _reserve(uid, 100, "A-r")  # remaining=100, reserved=100

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)

    rem, res, reason = await _grant_row(grant_id)
    assert (rem, res, reason) == (100, 100, "natural_expiry")

    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "active" and consumed == 0

    # settle داخل مهلت اصلی موفق است (بدون spend دوم)
    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid)
        await session.commit()
    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "consumed" and consumed == 100
    assert await _ledger_count_kind(uid, "spend") == 1

    err = await _reserve_expect_error(uid, 5, "A-new")
    assert err is not None and err.code == "insufficient_credit"


# ---------------------------------------------------------------------------
# Test B — partially reserved grant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_partially_reserved_grant_voids_only_unreserved() -> None:
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid, amount=100)
    rid = await _reserve(uid, 40, "B-r")  # remaining=100, reserved=40

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)

    rem, res, reason = await _grant_row(grant_id)
    assert (rem, res, reason) == (40, 40, "natural_expiry")

    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "active" and consumed == 0

    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid)
        await session.commit()
    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "consumed" and consumed == 40
    rem, res, reason = await _grant_row(grant_id)
    assert (rem, res) == (0, 0)

    err = await _reserve_expect_error(uid, 5, "B-new")
    assert err is not None and err.code == "insufficient_credit"


# ---------------------------------------------------------------------------
# Test C — unreserved grant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_unreserved_grant_voids_full_amount() -> None:
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid, amount=100)

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)

    rem, res, reason = await _grant_row(grant_id)
    assert (rem, res, reason) == (0, 0, "natural_expiry")

    err = await _reserve_expect_error(uid, 5, "C-new")
    assert err is not None and err.code == "insufficient_credit"


# ---------------------------------------------------------------------------
# Test D — multiple grants with mixed states
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_multiple_grants_sum_of_unreserved() -> None:
    uid = await _make_user()
    ent_id, g1 = await _make_entitlement_and_grant(uid, amount=100)
    g2 = await _add_grant_to_entitlement(uid, ent_id, 100)
    g3 = await _add_grant_to_entitlement(uid, ent_id, 100)
    g4 = await _add_grant_to_entitlement(uid, ent_id, 100)
    await _spend_down_grant(uid, g4, 100)  # zero remaining

    await _reserve(uid, 100, "D-r1")  # fully reserves g1
    await _reserve(uid, 40, "D-r2")   # partially reserves g2
    # g3 unreserved=100, g4 zero

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)

    assert await _grant_row(g1) == (100, 100, "natural_expiry")
    assert await _grant_row(g2) == (40, 40, "natural_expiry")
    assert await _grant_row(g3) == (0, 0, "natural_expiry")
    assert await _grant_row(g4) == (0, 0, "natural_expiry")


# ---------------------------------------------------------------------------
# Test E — settlement after natural expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_settle_within_deadline_succeeds() -> None:
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid, amount=100)
    rid = await _reserve(uid, 40, "E-r")

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).settle(rid)
        await session.commit()

    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "consumed" and consumed == 40
    assert await _ledger_count_kind(uid, "spend") == 1
    assert await _balance(uid) == await _ledger_sum(uid)


# ---------------------------------------------------------------------------
# Test F — deadline exceeded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_deadline_exceeded_settle_rejected_release_no_restore() -> None:
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid, amount=100)
    rid = await _reserve(uid, 40, "F-r")

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE reservations SET created_at = now() - interval '20 minutes' WHERE id=:r"), {"r": str(rid)})
        await session.commit()

    serr = await _settle_expect_error(rid)
    assert serr is not None and serr.code == "reservation_deadline_passed"

    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).release(rid, reason="deadline")
        await session.commit()

    status, consumed, released, voided = await _allocation_row(rid)
    assert status == "voided" and consumed == 0 and released == 0 and voided == 40
    rem, res, reason = await _grant_row(grant_id)
    assert (rem, res, reason) == (40, 0, "natural_expiry")
    assert await _ledger_count_kind(uid, "refund") == 0
    assert await _balance(uid) == 0
    assert await _balance(uid) == await _ledger_sum(uid)


# ---------------------------------------------------------------------------
# Test G — release after natural expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_release_voids_without_refund_or_restore() -> None:
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid, amount=100)
    rid = await _reserve(uid, 40, "G-r")

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    async with TEST_SESSION_FACTORY() as session:
        await FinanceService(session).release(rid, reason="manual")
        await session.commit()

    status, _, released, voided = await _allocation_row(rid)
    assert status == "voided" and released == 0 and voided == 40
    assert await _ledger_count_kind(uid, "refund") == 0
    assert await _balance(uid) == await _ledger_sum(uid)


# ---------------------------------------------------------------------------
# Test H — concurrent reservation versus expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_waits_on_grant_lock_held_by_reservation() -> None:
    """H1: هنگام نگه‌داشتن قفل ردیف grant (پنجرهٔ reserve)، job انقضا منتظر می‌ماند."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid, amount=100)

    async with TEST_SESSION_FACTORY() as holder:
        await ent_repo.get_grant_for_update(holder, grant_id)
        etask = asyncio.create_task(_expiry_runner(ent_id, uid))
        await asyncio.sleep(0.05)
        done, _ = await asyncio.wait([etask], timeout=1.0)
        assert etask not in done, "expiry باید روی قفل ردیف grant صبر کند"
        await holder.rollback()

    assert await etask == 1
    rem, res, reason = await _grant_row(grant_id)
    assert (rem, res, reason) == (0, 0, "natural_expiry")
    assert await _balance(uid) == 0
    err = await _reserve_expect_error(uid, 5, "H1-new")
    assert err is not None and err.code == "insufficient_credit"


@pytest.mark.asyncio
async def test_expiry_never_double_debits_committed_reservation() -> None:
    """H2: رزرو ابتدا commit می‌شود؛ expiry فقط بخش غیررزروشده را کم می‌کند."""
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid, amount=100)
    rid = await _reserve(uid, 40, "H2-r")

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    assert await _balance(uid) == 0  # نه منفی؛ بدهی ۴۰ دوباره کسر نشده
    assert await _balance(uid) == await _ledger_sum(uid)
    rem, res, reason = await _grant_row(grant_id)
    assert (rem, res, reason) == (40, 40, "natural_expiry")
    status, consumed, _, _ = await _allocation_row(rid)
    assert status == "active" and consumed == 0


@pytest.mark.asyncio
async def test_expiry_first_rejects_new_reservation() -> None:
    """H3: expiry ابتدا commit می‌شود؛ رزرو جدید رد می‌شود."""
    uid = await _make_user()
    ent_id, _ = await _make_entitlement_and_grant(uid, amount=100)

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    err = await _reserve_expect_error(uid, 5, "H3-new")
    assert err is not None and err.code == "insufficient_credit"


# ---------------------------------------------------------------------------
# Test I — idempotent repeated expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expiry_repeated_is_idempotent() -> None:
    uid = await _make_user()
    ent_id, grant_id = await _make_entitlement_and_grant(uid, amount=100)
    await _reserve(uid, 40, "I-r")

    assert await _force_expiry_and_run_job(ent_id, uid) == 1
    assert await _force_expiry_and_run_job(ent_id, uid) == 0

    assert await _ledger_count_kind(uid, "adjust") == 1
    rem, res, reason = await _grant_row(grant_id)
    assert (rem, res, reason) == (40, 40, "natural_expiry")
    assert await _balance(uid) == await _ledger_sum(uid)
