"""تست‌های اصلاح‌های هدفمند ممیزی: C-01، C-03، M-03."""

import asyncio
import os
import subprocess
import sys
import uuid

import pytest
from app.core.config import get_settings
from app.models.user import User
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import entitlements as ent_repo
from app.repositories import payment_transactions as payments_repo
from app.repositories import users as users_repo
from app.services.plans import PlanService
from httpx import ASGITransport, AsyncClient
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


async def _paid_payment(user_id: uuid.UUID, *, product: str, plan_type: str, credits: int) -> uuid.UUID:
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.create(
            session,
            user_id=user_id,
            product_id=product,
            amount_toman=1,
            credit_grant=credits,
            plan_type=plan_type,
            duration_days=30,
            provider="zarinpal",
            provider_currency="IRR",
            provider_amount=10,
            idempotency_key=f"pay-{uuid.uuid4()}",
            request_fingerprint="f",
        )
        await session.execute(
            text("UPDATE payment_transactions SET status='succeeded', succeeded_at=now() WHERE id=:i"),
            {"i": str(payment.id)},
        )
        if plan_type == "credit" and credits > 0:
            await ledger_repo.create(
                session, user_id=user_id, kind="plan_grant", amount=credits,
                idempotency_key=f"gr:{payment.id}",
            )
            await session.execute(
                text("UPDATE credit_accounts SET available_balance = available_balance + :c WHERE user_id=:u"),
                {"c": credits, "u": str(user_id)},
            )
        await session.commit()
        return payment.id


# ------------------------------------------------------------------ C-01

@pytest.mark.asyncio
async def test_migration_0012_downgrade_guard_protects_data() -> None:
    """downgrade (forward-only) باید پیش از هر DDL رد شود و schema/داده را دست‌نخورده نگه دارد."""
    user_id = await _make_user()
    await _paid_payment(user_id, product="unlimited", plan_type="unlimited", credits=0)
    async with TEST_SESSION_FACTORY() as session:
        payment_id = (await session.execute(text("SELECT id FROM payment_transactions WHERE user_id=:u LIMIT 1"), {"u": str(user_id)})).scalar_one()
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, payment_id))
        await session.commit()

    env = os.environ.copy()
    env["DATABASE_URL"] = get_settings().database_url
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "downgrade", "0011_abuse_flags"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert result.returncode != 0
    assert "forward-only" in result.stderr

    async with TEST_SESSION_FACTORY() as session:
        ents = (await session.execute(text("SELECT count(*) FROM plan_entitlements WHERE user_id=:u"), {"u": str(user_id)})).scalar_one()
        assert ents == 1
        for table in ("plan_entitlements", "credit_grants", "cancellation_requests", "refund_records"):
            exists = (await session.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_name=:t"), {"t": table})).scalar_one()
            assert exists == 1
        # ستون‌های snapshot نیز باید باقی باشند (ثابتِ DDL-نشدن)
        col = (await session.execute(text("SELECT count(*) FROM information_schema.columns WHERE table_name='payment_transactions' AND column_name='duration_days'"))).scalar_one()
        assert col == 1


# ------------------------------------------------------------------ C-03

@pytest.mark.asyncio
async def test_expiration_concurrent_workers_single_adjust() -> None:
    user_id = await _make_user()
    payment_id = await _paid_payment(user_id, product="basic", plan_type="credit", credits=500)
    async with TEST_SESSION_FACTORY() as session:
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, payment_id))
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE plan_entitlements SET expires_at = now() - interval '2 days' WHERE user_id=:u"), {"u": str(user_id)})
        await session.commit()

    async def expire() -> int:
        async with TEST_SESSION_FACTORY() as session:
            count = await PlanService(session).expire_due_entitlements(batch_limit=10, user_id=user_id)
            await session.commit()
            return count

    results = await asyncio.gather(expire(), expire())
    assert sum(results) == 1
    async with TEST_SESSION_FACTORY() as session:
        adjusts = (await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id=:u AND kind='adjust'"), {"u": str(user_id)})).scalar_one()
        assert adjusts == 1
        ents = (await session.execute(text("SELECT status FROM plan_entitlements WHERE user_id=:u"), {"u": str(user_id)})).scalar_one()
        assert ents == "expired"


# ------------------------------------------------------------------ M-03

def _override_deps(app, session_factory, user_provider) -> None:
    from app.api.deps import get_current_user
    from app.db.session import get_db

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = user_provider


@pytest.mark.asyncio
async def test_api_isolation_user_ownership() -> None:
    from app.main import app as real_app

    user_a = await _make_user()
    user_b = await _make_user()
    await _paid_payment(user_a, product="basic", plan_type="credit", credits=500)
    async with TEST_SESSION_FACTORY() as session:
        payment_id = (await session.execute(text("SELECT id FROM payment_transactions WHERE user_id=:u LIMIT 1"), {"u": str(user_a)})).scalar_one()
        await PlanService(session).process_paid_payment(await payments_repo.get_by_id(session, payment_id))
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        entitlement = await ent_repo.get_active_entitlement(session, user_a, "basic")
        await ent_repo.create_cancellation_request(session, user_id=user_a, entitlement_id=entitlement.id)
        await session.commit()
        cancel_id = (await session.execute(text("SELECT id FROM cancellation_requests WHERE user_id=:u"), {"u": str(user_a)})).scalar_one()

    async def user_b_provider():
        async with TEST_SESSION_FACTORY() as session:
            user = await users_repo.get_by_id(session, user_b)
            return user or User()

    previous_overrides = dict(real_app.dependency_overrides)
    _override_deps(real_app, TEST_SESSION_FACTORY, user_b_provider)
    try:
        async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://localhost") as client:
            resp = await client.get("/api/v1/billing/entitlements")
            assert resp.status_code == 200
            assert all(item["product_id"] != "basic" for item in resp.json())
            pre = await client.get("/api/v1/billing/pre-purchase-info", params={"product_id": "basic"})
            assert pre.status_code == 200
            assert pre.json()["current_entitlement"] is None
            withdraw = await client.post(f"/api/v1/billing/cancellation-requests/{cancel_id}/withdraw")
            assert withdraw.status_code == 409
    finally:
        real_app.dependency_overrides.clear()
        real_app.dependency_overrides.update(previous_overrides)

    # ناشناس → 401 با dependency واقعی
    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://localhost") as client:
        resp = await client.get("/api/v1/billing/entitlements")
        assert resp.status_code == 401
