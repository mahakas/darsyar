"""طھط³طھâ€Œظ‡ط§غŒ غŒع©ظ¾ط§ط±ع†ظ‡ظ” ظ¾ظ„ظ†/entitlement (ADR-052) ط±ظˆغŒ PostgreSQL ظˆط§ظ‚ط¹غŒ."""

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


async def _make_user(balance: int = 0) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=_new_phone(), role="user")
        await accounts_repo.create(session, user_id=user.id, available_balance=balance)
        await session.commit()
        return user.id


async def _paid_payment(user_id: uuid.UUID, *, product: str, plan_type: str, credits: int, duration: int = 30):
    """ط³ط§ط®طھ غŒع© ظ¾ط±ط¯ط§ط®طھ ظ…ظˆظپظ‚ ط¨ظ‡â€Œطµظˆط±طھ ظ…ط³طھظ‚غŒظ… (ط¨ط±ط§غŒ طھط³طھ ط¯ط§ظ…ظ†ظ‡ظ” ظ¾ظ„ظ†).

    ط¨ط±ط§غŒ ظ¾ظ„ظ†â€Œظ‡ط§غŒ creditطŒ ledger/balance ظ…ط§ظ†ظ†ط¯ PaymentService.finalize_succeeded ط§ط¹طھط¨ط§ط±
    ظ…غŒâ€Œع¯غŒط±ظ†ط¯ طھط§ ط§ظ†ظ‚ط¶ط§/refund ط¨طھظˆط§ظ†ظ†ط¯ ط¢ظ† ط±ط§ ط¨ط§ط·ظ„ ع©ظ†ظ†ط¯.
    """
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.create(
            session,
            user_id=user_id,
            product_id=product,
            amount_toman=1,
            credit_grant=credits,
            plan_type=plan_type,
            duration_days=duration,
            provider="zarinpal",
            provider_currency="IRR",
            provider_amount=10,
            idempotency_key=f"pay-{user_id}-{product}-{uuid.uuid4()}",
            request_fingerprint="f",
        )
        await session.execute(
            text("UPDATE payment_transactions SET status = 'succeeded', succeeded_at = now() WHERE id = :i"),
            {"i": str(payment.id)},
        )
        if plan_type == "credit" and credits > 0:
            await ledger_repo.create(
                session, user_id=user_id, kind="plan_grant", amount=credits,
                idempotency_key=f"gr:{payment.id}",
            )
            await session.execute(
                text("UPDATE credit_accounts SET available_balance = available_balance + :c WHERE user_id = :u"),
                {"c": credits, "u": str(user_id)},
            )
        await session.commit()
        return payment.id


async def _active_entitlement(user_id: uuid.UUID, product: str):
    async with TEST_SESSION_FACTORY() as session:
        return await ent_repo.get_active_entitlement(session, user_id, product)


async def _balance(user_id: uuid.UUID) -> int:
    async with TEST_SESSION_FACTORY() as session:
        return (await accounts_repo.get_for_update(session, user_id)).available_balance


@pytest.mark.asyncio
async def test_paid_basic_activates_entitlement_and_grant() -> None:
    user_id = await _make_user()
    payment_id = await _paid_payment(user_id, product="basic", plan_type="credit", credits=500)
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, payment_id)
        await PlanService(session).process_paid_payment(payment)
        await session.commit()
    entitlement = await _active_entitlement(user_id, "basic")
    assert entitlement is not None
    assert entitlement.plan_type == "credit"
    assert entitlement.granted_credits == 500
    assert entitlement.remaining_credits == 500
    assert entitlement.expires_at > datetime.now(UTC)
    async with TEST_SESSION_FACTORY() as session:
        grants = await ent_repo.list_eligible_grants(session, user_id, datetime.now(UTC))
        assert len(grants) == 1
        assert grants[0].remaining_amount == 500


@pytest.mark.asyncio
async def test_repurchase_active_basic_extends_30d_and_adds_credits() -> None:
    user_id = await _make_user()
    p1 = await _paid_payment(user_id, product="basic", plan_type="credit", credits=500)
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, p1))
        await session.commit()
    first = await _active_entitlement(user_id, "basic")
    first_expiry = first.expires_at
    p2 = await _paid_payment(user_id, product="basic", plan_type="credit", credits=300)
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, p2))
        await session.commit()
    second = await _active_entitlement(user_id, "basic")
    assert second is not None and second.id == first.id
    assert second.expires_at == first_expiry + timedelta(days=30)
    assert second.remaining_credits == 800
    async with TEST_SESSION_FACTORY() as session:
        grants = await ent_repo.list_eligible_grants(session, user_id, datetime.now(UTC))
        assert len(grants) == 2


@pytest.mark.asyncio
async def test_repurchase_after_expiry_starts_fresh_period() -> None:
    user_id = await _make_user()
    p1 = await _paid_payment(user_id, product="basic", plan_type="credit", credits=500)
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, p1))
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        # ظ†غŒط±ظˆغŒ ط§ظ†ظ‚ط¶ط§
        await session.execute(text("UPDATE plan_entitlements SET expires_at = now() - interval '2 days' WHERE user_id = :u"), {"u": str(user_id)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        expired = await PlanService(session).expire_due_entitlements(batch_limit=10, user_id=user_id)
        assert expired >= 1

        await session.commit()
    second_ent = await _active_entitlement(user_id, "basic")
    assert second_ent is None
    p2 = await _paid_payment(user_id, product="basic", plan_type="credit", credits=500)
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, p2))
        await session.commit()
    active = await _active_entitlement(user_id, "basic")
    assert active is not None
    assert active.remaining_credits == 500
    assert active.expires_at - datetime.now(UTC) <= timedelta(days=31)


@pytest.mark.asyncio
async def test_unlimited_activation_and_repurchase() -> None:
    user_id = await _make_user()
    p1 = await _paid_payment(user_id, product="unlimited", plan_type="unlimited", credits=0)
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, p1))
        await session.commit()
    ent = await _active_entitlement(user_id, "unlimited")
    assert ent is not None and ent.plan_type == "unlimited"
    first_expiry = ent.expires_at
    p2 = await _paid_payment(user_id, product="unlimited", plan_type="unlimited", credits=0)
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, p2))
        await session.commit()
    ent2 = await _active_entitlement(user_id, "unlimited")
    assert ent2.id == ent.id
    assert ent2.expires_at == first_expiry + timedelta(days=30)


@pytest.mark.asyncio
async def test_unlimited_reservation_gate() -> None:
    user_id = await _make_user(balance=0)
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(AppError) as excinfo:
            await service.reserve_unlimited(user_id, idempotency_key="k1", payload_fingerprint="f")
        assert excinfo.value.code == "unlimited_inactive"
    p = await _paid_payment(user_id, product="unlimited", plan_type="unlimited", credits=0)
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, p))
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_unlimited(user_id, idempotency_key="k2", payload_fingerprint="f")
        await session.commit()
        assert reservation.kind == "unlimited"
        assert await _balance(user_id) == 0


@pytest.mark.asyncio
async def test_expire_job_voids_remaining_exactly_once() -> None:
    user_id = await _make_user(balance=500)
    p = await _paid_payment(user_id, product="pro", plan_type="credit", credits=1200)
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, p))
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE plan_entitlements SET expires_at = now() - interval '2 days' WHERE user_id = :u"), {"u": str(user_id)})
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        assert await PlanService(session).expire_due_entitlements(batch_limit=10, user_id=user_id) >= 1

        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        remaining_sum = (
            await session.execute(text("SELECT COALESCE(SUM(remaining_amount),0) FROM credit_grants WHERE user_id=:u"), {"u": str(user_id)})
        ).scalar_one()
        assert remaining_sum == 0
        assert await _balance(user_id) == 500  # فقط اعتبار خودِ تست باطل شد؛ پایهٔ 500 دست‌نخورده
    async with TEST_SESSION_FACTORY() as session:
        assert await PlanService(session).expire_due_entitlements(batch_limit=10, user_id=user_id) == 0


@pytest.mark.asyncio
async def test_cancellation_request_withdraw_and_admin_decision_immediate() -> None:
    user_id = await _make_user(balance=500)
    admin_id = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        admin = await users_repo.get_by_id(session, admin_id)
        admin.role = "admin"
        await session.commit()
    p = await _paid_payment(user_id, product="basic", plan_type="credit", credits=500)
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, p)
        await PlanService(session).process_paid_payment(payment)
        await session.commit()
    entitlement = await _active_entitlement(user_id, "basic")
    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_cancellation(user_id, entitlement.id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        pending = await ent_repo.get_pending_cancellation(session, user_id, entitlement.id)
        await service.withdraw_cancellation(user_id, pending.id)
        await session.commit()
    # ط¯ط±ط®ظˆط§ط³طھ ط¬ط¯غŒط¯ + طھطµظ…غŒظ… ط§ط¯ظ…غŒظ† (immediate) â†’ ط§ط¨ط·ط§ظ„ ط§ط¹طھط¨ط§ط±ظ‡ط§
    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_cancellation(user_id, entitlement.id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        pending = await ent_repo.get_pending_cancellation(session, user_id, entitlement.id)
        await service.decide_cancellation(
            pending.id, actor_user_id=admin_id, approve=True, reason="requested", mode="immediate"
        )
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        ent = await ent_repo.get_active_entitlement(session, user_id, "basic")
        assert ent is None
        row = (await session.execute(text("SELECT status FROM plan_entitlements WHERE user_id = :u"), {"u": str(user_id)})).scalar_one()
        assert row == "cancelled"
        assert await _balance(user_id) == 500


@pytest.mark.asyncio
async def test_refund_decision_voids_credits_without_erasing_history() -> None:
    user_id = await _make_user(balance=500)
    admin_id = await _make_user()
    async with TEST_SESSION_FACTORY() as session:
        admin = await users_repo.get_by_id(session, admin_id)
        admin.role = "admin"
        await session.commit()
    p = await _paid_payment(user_id, product="pro", plan_type="credit", credits=1200)
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, p)
        await PlanService(session).process_paid_payment(payment)
        await session.commit()
    entitlement = await _active_entitlement(user_id, "pro")
    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        await service.request_refund(
            user_id=user_id, payment_id=p, entitlement_id=entitlement.id, requested_amount=1000000, reason="technical failure"
        )
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = PlanService(session)
        record = (await session.execute(text("SELECT id FROM refund_records ORDER BY created_at DESC LIMIT 1"))).scalar_one()
        await service.decide_refund(record, actor_user_id=admin_id, approve=True, reason="approved", credit_voided=1200)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        row = (await session.execute(text("SELECT status, credit_voided FROM refund_records ORDER BY created_at DESC LIMIT 1"))).one()
        assert row[0] == "approved"
        assert row[1] == 1200
        assert await _balance(user_id) == 500
        ledger_rows = (await session.execute(text("SELECT kind FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})).scalars().all()
        assert "plan_grant" in ledger_rows
        assert ledger_rows.count("adjust") == 1
