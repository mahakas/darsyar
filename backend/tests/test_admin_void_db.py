"""تست‌های تصمیم admin_void (D-05) و گارد 0014."""

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


async def _add_grant(user_id: uuid.UUID, *, amount: int = 500) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        grant = await ent_repo.create_grant(
            session, user_id=user_id, entitlement_id=None, kind="plan_grant", amount=amount,
            expires_at=datetime.now(UTC) + timedelta(days=30), payment_id=None,
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


async def _apply_admin_void(user_id: uuid.UUID, grant_id: uuid.UUID) -> None:
    async with TEST_SESSION_FACTORY() as session:
        now = datetime.now(UTC)
        entitlement = await ent_repo.create_entitlement(
            session, user_id=user_id, product_id="basic", plan_type="credit",
            activated_at=now - timedelta(days=1), expires_at=now + timedelta(days=30),
            granted_credits=500, payment_id=None, snapshot={},
        )
        await session.execute(text("UPDATE credit_grants SET entitlement_id=:e WHERE id=:g"), {"e": str(entitlement.id), "g": str(grant_id)})
        await ent_repo.void_all_grants_of_entitlement(session, entitlement.id, reason="admin_void", effective_at=now, now=now)
        await session.commit()


@pytest.mark.asyncio
async def test_admin_void_settle_denied_even_for_pre_void_allocation() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid)
    rid = await _reserve(uid, 100, "av1")
    await _apply_admin_void(uid, grant_id)
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(AppError) as excinfo:
            await service.settle(rid)
        assert excinfo.value.code == "invalid_reservation_state"


@pytest.mark.asyncio
async def test_admin_void_release_voids_allocation_without_restore() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid)
    rid = await _reserve(uid, 100, "av2")
    await _apply_admin_void(uid, grant_id)
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.release(rid, reason="admin_void")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        row = (await session.execute(text("SELECT status, voided_amount FROM reservation_credit_allocations WHERE reservation_id=:r"), {"r": str(rid)})).one()
        assert row[0] == "voided" and int(row[1]) == 100
        g = (await session.execute(text("SELECT remaining_amount, reserved_amount, lifecycle_reason FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).one()
        # اعتبار 400 غیررزروشده هنگام admin_void باطل شد؛ ادعای 100 بدون بازگشت حذف شد.
        assert (int(g[0]), int(g[1])) == (100, 0)
        assert g[2] == "admin_void"
        # هیچ refund/جبرانی نباید برای این رزرو ساخته شود
        refunds = (await session.execute(text("SELECT count(*) FROM credit_ledger WHERE kind='refund' AND user_id=:u"), {"u": str(uid)})).scalar_one()
        assert refunds == 0


@pytest.mark.asyncio
async def test_admin_void_blocks_new_reservation() -> None:
    uid = await _make_user()
    grant_id = await _add_grant(uid)
    await _reserve(uid, 100, "av3")
    await _apply_admin_void(uid, grant_id)
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(AppError) as excinfo:
            await service.reserve_credit(uid, 10, idempotency_key="av-new", payload_fingerprint="f")
        assert excinfo.value.code == "insufficient_credit"


@pytest.mark.asyncio
async def test_migration_0014_downgrade_guard() -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = get_settings().database_url
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "downgrade", "0013_grant_allocation"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert result.returncode != 0
    assert "forward-only" in result.stderr
    async with TEST_SESSION_FACTORY() as session:
        col = (await session.execute(text("SELECT count(*) FROM information_schema.columns WHERE table_name='credit_grants' AND column_name='lifecycle_reason'"))).scalar_one()
        assert col == 1
