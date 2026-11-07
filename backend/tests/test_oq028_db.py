"""تست‌های OQ-028 (لغو فوری/refund با رزرو فعال) روی PostgreSQL واقعی."""

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


async def _make_user(role: str = "user") -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role=role)
        await accounts_repo.create(session, user_id=user.id, available_balance=0)
        await session.commit()
        return user.id


async def _add_grant(user_id: uuid.UUID, *, amount: int = 500, expiry_days: int = 30) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        grant = await ent_repo.create_grant(
            session, user_id=user_id, entitlement_id=None, kind="plan_grant", amount=amount,
            expires_at=datetime.now(UTC) + timedelta(days=expiry_days), payment_id=None,
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


async def _admin_void_entitlement(user_id: uuid.UUID, grant_id: uuid.UUID, reason: str) -> datetime:
    """شبیه‌سازی تصمیم ادمین (لغو فوری/refund) روی entitlement ساختگی."""
    async with TEST_SESSION_FACTORY() as session:
        now = datetime.now(UTC)
        # ساخت entitlement موقت و اتصال grant
        entitlement = await ent_repo.create_entitlement(
            session, user_id=user_id, product_id="basic", plan_type="credit",
            activated_at=now - timedelta(days=1), expires_at=now + timedelta(days=30),
            granted_credits=500, payment_id=None, snapshot={},
        )
        await session.execute(text("UPDATE credit_grants SET entitlement_id=:e WHERE id=:g"), {"e": str(entitlement.id), "g": str(grant_id)})
        await ent_repo.void_all_grants_of_entitlement(
            session, entitlement.id, reason=reason, effective_at=now, now=now
        )
        await session.commit()
        return now


@pytest.mark.asyncio
async def test_immediate_cancellation_blocks_new_but_allows_grandfathered_settle() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid)
    rid = await _reserve(uid, 100, "oq1")
    await _admin_void_entitlement(uid, grant_id, "immediate_cancellation")

    # رزرو جدید رد می‌شود
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(AppError) as excinfo:
            await service.reserve_credit(uid, 10, idempotency_key="oq-new", payload_fingerprint="f")
        assert excinfo.value.code == "insufficient_credit"

    # settle قبل از مهلت (گرندفادر) موفق است
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(rid)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        row = (await session.execute(text("SELECT status, consumed_amount FROM reservation_credit_allocations WHERE reservation_id=:r"), {"r": str(rid)})).one()
        assert row[0] == "consumed" and int(row[1]) == 100
        g = (await session.execute(text("SELECT remaining_amount, reserved_amount, lifecycle_reason FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).one()
        assert (int(g[0]), int(g[1])) == (0, 0)
        assert g[2] == "immediate_cancellation"


@pytest.mark.asyncio
async def test_immediate_cancellation_deadline_expiry_voids_allocation() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid)
    rid = await _reserve(uid, 100, "oq2")
    await _admin_void_entitlement(uid, grant_id, "immediate_cancellation")
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE reservations SET created_at = now() - interval '20 minutes' WHERE id=:r"), {"r": str(rid)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(AppError):
            await service.settle(rid)
        await service.release(rid, reason="deadline")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        row = (await session.execute(text("SELECT status, voided_amount FROM reservation_credit_allocations WHERE reservation_id=:r"), {"r": str(rid)})).one()
        assert row[0] == "voided" and int(row[1]) == 100
        g = (await session.execute(text("SELECT remaining_amount, reserved_amount FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).one()
        # بدون بازگشت: ادعای 100 حذف می‌شود؛ remaining=100 (بخش رزروشدهٔ باقی‌مانده) می‌ماند
        assert (int(g[0]), int(g[1])) == (100, 0)


@pytest.mark.asyncio
async def test_approved_refund_same_behavior_and_reason_isolation() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid)
    rid = await _reserve(uid, 50, "oq3")
    await _admin_void_entitlement(uid, grant_id, "approved_refund")
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(rid)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        g = (await session.execute(text("SELECT lifecycle_reason FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).scalar_one()
        assert g == "approved_refund"


@pytest.mark.asyncio
async def test_natural_expiry_regression_unaffected() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid)
    rid = await _reserve(uid, 50, "oq4")
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE credit_grants SET expires_at = now() - interval '1 hour' WHERE id=:g"), {"g": str(grant_id)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(rid)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        g = (await session.execute(text("SELECT lifecycle_reason FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).scalar_one()
        assert g is None  # طبیعی: بدون reason ادمین
