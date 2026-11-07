"""طھط³طھâ€Œظ‡ط§غŒ طھط®طµغŒطµ grantâ†’ط±ط²ط±ظˆ (ADR-053ط› D-01/D-02) ط±ظˆغŒ PostgreSQL ظˆط§ظ‚ط¹غŒ."""

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


async def _add_grant(
    user_id: uuid.UUID,
    *,
    kind: str = "plan_grant",
    amount: int,
    expires_at: datetime | None = None,
) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        grant = await ent_repo.create_grant(
            session, user_id=user_id, entitlement_id=None, kind=kind, amount=amount,
            expires_at=expires_at, payment_id=None,
        )
        await session.execute(
            text("UPDATE credit_accounts SET available_balance = available_balance + :c WHERE user_id=:u"),
            {"c": amount, "u": str(user_id)},
        )
        await ledger_repo.create(
            session, user_id=user_id, kind="plan_grant", amount=amount,
            idempotency_key=f"gr-{grant.id}",
        )
        await session.commit()
        return grant.id


async def _allocations(reservation_id: uuid.UUID):
    async with TEST_SESSION_FACTORY() as session:
        rows = (
            await session.execute(text("SELECT grant_id, allocated_amount, consumed_amount, released_amount, voided_amount, status FROM reservation_credit_allocations WHERE reservation_id=:r"), {"r": str(reservation_id)})
        ).all()
        return rows


async def _grant_state(grant_id: uuid.UUID):
    async with TEST_SESSION_FACTORY() as session:
        row = (await session.execute(text("SELECT remaining_amount, reserved_amount FROM credit_grants WHERE id=:g"), {"g": str(grant_id)})).one()
        return (int(row[0]), int(row[1]))


async def _balance(user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return int((await accounts_repo.get_for_update(session, user_id)).available_balance)


async def _reserve(user_id: uuid.UUID, amount: int, key: str):
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, amount, idempotency_key=key, payload_fingerprint="f")
        await session.commit()
        return reservation.id


@pytest.mark.asyncio
async def test_eff_selects_earliest_expiry_first() -> None:
    uid = await _make_user()
    now = datetime.now(UTC)
    late = await _add_grant(uid, amount=100, expires_at=now + timedelta(days=30))
    early = await _add_grant(uid, amount=100, expires_at=now + timedelta(days=5))
    rid = await _reserve(uid, 40, "k1")
    rows = await _allocations(rid)
    assert len(rows) == 1
    assert rows[0][0] == early
    assert rows[0][1] == 40
    assert await _grant_state(early) == (100, 40)
    assert await _grant_state(late) == (100, 0)


@pytest.mark.asyncio
async def test_eff_equal_expiry_older_created_first() -> None:
    uid = await _make_user()
    expiry = datetime.now(UTC) + timedelta(days=10)
    older = await _add_grant(uid, amount=50, expires_at=expiry)
    await _add_grant(uid, amount=50, expires_at=expiry)
    rid = await _reserve(uid, 40, "k2")
    rows = await _allocations(rid)
    assert len(rows) == 1 and rows[0][0] == older


@pytest.mark.asyncio
async def test_multi_grant_allocation() -> None:
    uid = await _make_user()
    g1 = await _add_grant(uid, amount=10, expires_at=datetime.now(UTC) + timedelta(days=1))
    g2 = await _add_grant(uid, amount=10, expires_at=datetime.now(UTC) + timedelta(days=2))
    rid = await _reserve(uid, 15, "k3")
    rows = await _allocations(rid)
    by_grant = {r[0]: r[1] for r in rows}
    assert by_grant == {g1: 10, g2: 5}
    assert await _grant_state(g1) == (10, 10)
    assert await _grant_state(g2) == (10, 5)


@pytest.mark.asyncio
async def test_insufficient_eligible_leaves_no_partial() -> None:
    uid = await _make_user()
    g1 = await _add_grant(uid, amount=10)
    with pytest.raises(AppError) as excinfo:
        await _reserve(uid, 11, "k4")
    assert excinfo.value.code == "insufficient_credit"
    async with TEST_SESSION_FACTORY() as session:
        count = (await session.execute(text("SELECT count(*) FROM reservation_credit_allocations WHERE grant_id=:g"), {"g": str(g1)})).scalar_one()
        assert count == 0


@pytest.mark.asyncio
async def test_settle_consumes_exact_allocations() -> None:
    uid = await _make_user()
    g1 = await _add_grant(uid, amount=10)
    g2 = await _add_grant(uid, amount=10)
    rid = await _reserve(uid, 12, "k5")
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(rid)
        await session.commit()
    rows = await _allocations(rid)
    assert sorted(r[5] for r in rows) == ["consumed", "consumed"]
    assert sum(r[2] for r in rows) == 12
    assert await _grant_state(g1) == (0, 0)
    assert await _grant_state(g2) == (8, 0)


@pytest.mark.asyncio
async def test_release_restores_only_valid_sources() -> None:
    uid = await _make_user()
    valid = await _add_grant(uid, amount=10, expires_at=datetime.now(UTC) + timedelta(days=30))
    expired = await _add_grant(uid, amount=10, expires_at=datetime.now(UTC) + timedelta(days=30))
    rid = await _reserve(uid, 20, "k6")
    async with TEST_SESSION_FACTORY() as session:
        # ظ†غŒط±ظˆغŒ ط§ظ†ظ‚ط¶ط§غŒ grant ط¯ظˆظ…
        await session.execute(text("UPDATE credit_grants SET expires_at = now() - interval '1 day' WHERE id=:g"), {"g": str(expired)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.release(rid)
        await session.commit()
    rows = await _allocations(rid)
    statuses = {r[0]: r[5] for r in rows}
    assert statuses[valid] == "released"
    assert statuses[expired] == "voided"
    assert await _grant_state(valid) == (10, 0)
    assert await _grant_state(expired) == (10, 0)  # ط¨ط¯ظˆظ† ط¨ط§ط²ع¯ط´طھ


@pytest.mark.asyncio
async def test_duplicate_release_no_double_refund() -> None:
    uid = await _make_user()
    await _add_grant(uid, amount=10)
    rid = await _reserve(uid, 5, "k7")
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.release(rid)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.release(rid)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        refunds = (
            await session.execute(text("SELECT count(*) FROM credit_ledger WHERE kind='refund' AND user_id=:u"), {"u": str(uid)})
        ).scalar_one()
        assert refunds == 1


@pytest.mark.asyncio
async def test_concurrent_reservations_cannot_overallocate() -> None:
    uid = await _make_user()
    g1 = await _add_grant(uid, amount=10)
    g2 = await _add_grant(uid, amount=10)

    async def reserve(key: str, amount: int) -> str:
        async with TEST_SESSION_FACTORY() as session:
            service = FinanceService(session)
            try:
                await service.reserve_credit(uid, amount, idempotency_key=key, payload_fingerprint="f")
                await session.commit()
                return "ok"
            except AppError as exc:
                await session.rollback()
                return exc.code

    results = await asyncio.gather(reserve("c1", 15), reserve("c2", 15))
    assert results.count("ok") == 1
    async with TEST_SESSION_FACTORY() as session:
        total_alloc = (await session.execute(text("SELECT COALESCE(SUM(allocated_amount),0) FROM reservation_credit_allocations WHERE grant_id IN (:a,:b)"), {"a": str(g1), "b": str(g2)})).scalar_one()
        assert total_alloc == 15


@pytest.mark.asyncio
async def test_unlimited_preserves_free_basic_pro() -> None:
    uid = await _make_user()
    free_g = await _add_grant(uid, kind="free_grant", amount=5)
    basic_g = await _add_grant(uid, amount=500)
    # ظپط¹ط§ظ„â€Œط³ط§ط²غŒ unlimited
    async with TEST_SESSION_FACTORY() as session:
        from app.repositories import payment_transactions as payments_repo

        payment = await payments_repo.create(
            session, user_id=uid, product_id="unlimited", amount_toman=1, credit_grant=0,
            plan_type="unlimited", duration_days=30, provider="zarinpal", provider_currency="IRR",
            provider_amount=10, idempotency_key=f"u-{uuid.uuid4()}", request_fingerprint="f",
        )
        await session.execute(text("UPDATE payment_transactions SET status='succeeded', succeeded_at=now() WHERE id=:i"), {"i": str(payment.id)})
        await PlanService(session).process_paid_payment(payment)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_unlimited(uid, idempotency_key="u1", payload_fingerprint="f")
        await session.commit()
        assert reservation.kind == "unlimited"
    assert await _grant_state(free_g) == (5, 0)
    assert await _grant_state(basic_g) == (500, 0)
    async with TEST_SESSION_FACTORY() as session:
        alloc_count = (
            await session.execute(
                text("SELECT count(*) FROM reservation_credit_allocations WHERE reservation_id IN (SELECT id FROM reservations WHERE user_id=:u)"),
                {"u": str(uid)},
            )
        ).scalar_one()
        assert alloc_count == 0
    # ط­غŒظ† unlimitedطŒ ط±ط²ط±ظˆ ط§ط¹طھط¨ط§ط± ظ…ط¹ظ…ظˆظ„غŒ ط±ط¯ ظ…غŒâ€Œط´ظˆط¯
    with pytest.raises(AppError) as excinfo:
        await _reserve(uid, 1, "blocked")
    assert excinfo.value.code == "unlimited_active_blocks_credit_reservation"
