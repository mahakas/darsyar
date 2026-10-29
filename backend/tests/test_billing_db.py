"""تست‌های یکپارچهٔ پرداخت (Slice B) روی PostgreSQL واقعی با FakeProvider (ADR-047)."""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories import admin_audit_log as audit_module
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import payment_transactions as payments_repo
from app.repositories import product_catalog as catalog_repo
from app.repositories import users as users_repo
from app.scripts.upsert_product import upsert_product
from app.services.payment import PaymentService
from app.services.payment_provider import (
    PaymentProviderMalformedError,
    PaymentProviderMerchantError,
    PaymentProviderTransportError,
    VerifyResult,
)
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

AUTHORITY = "A" + "0" * 35


@pytest.fixture(autouse=True)
async def _reset_catalog() -> None:
    """بازنشانی قطعی کاتالوگ پیش از هر تست؛ مستقل از دادهٔ باقی‌مانده."""
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(
            text(
                "UPDATE product_catalog SET active = true, "
                "price_toman = CASE product_id WHEN 'basic' THEN 500000 ELSE 1000000 END, "
                "credit_grant = CASE product_id WHEN 'basic' THEN 500 ELSE 1200 END"
            )
        )
        await session.commit()
    yield


def _new_phone() -> str:
    return f"+989{str(uuid.uuid4().int)[:9]}"


class FakeProvider:
    """PaymentProvider قطعی؛ هر تماس ثبت می‌شود."""

    def __init__(self) -> None:
        self.request_calls: list[tuple[int, str, str]] = []
        self.verify_calls: list[tuple[str, int]] = []
        self.request_error: Exception | None = None
        self.verify_error: Exception | None = None
        self.verify_result = VerifyResult(code=100, ref_id="REF-1")
        self.authority = AUTHORITY

    async def request_payment(self, amount_toman: int, callback_url: str, description: str) -> str:
        self.request_calls.append((amount_toman, callback_url, description))
        if self.request_error is not None:
            raise self.request_error
        # authority یکتا و درون‌اجرایی؛ از برخورد با اجراهای قبلی جلوگیری می‌کند.
        self.authority = "A" + uuid.uuid4().hex + "000"
        return self.authority

    async def verify_payment(self, authority: str, amount_toman: int) -> VerifyResult:
        self.verify_calls.append((authority, amount_toman))
        if self.verify_error is not None:
            raise self.verify_error
        return self.verify_result

    def gateway_url(self, authority: str) -> str:
        return f"https://sandbox.zarinpal.com/pg/StartPay/{authority}"

    def to_provider_amount(self, amount_toman: int) -> int:
        return amount_toman * 10


async def _make_user(balance: int | None = None) -> uuid.UUID:
    phone = _new_phone()
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=phone, role="user")
        if balance is not None:
            await accounts_repo.create(session, user_id=user.id, available_balance=balance)
        await session.commit()
        return user.id


@pytest.fixture()
async def user_id() -> uuid.UUID:
    return await _make_user(balance=0)


async def _checkout(service: PaymentService, user_id: uuid.UUID, key: str = "key-1", product: str = "basic"):
    return await service.checkout(user_id, product, idempotency_key=key, request_id="req-1")


async def _count(session, table: str, user_id: uuid.UUID) -> int:
    result = await session.execute(text(f"SELECT count(*) FROM {table} WHERE user_id = :u"), {"u": str(user_id)})
    return int(result.scalar_one())


@pytest.mark.asyncio
async def test_catalog_seeded_with_basic_and_pro() -> None:
    async with TEST_SESSION_FACTORY() as session:
        basic = await catalog_repo.get_active(session, "basic")
        pro = await catalog_repo.get_active(session, "pro")
        assert basic is not None and basic.price_toman == 500000 and basic.credit_grant == 500
        assert pro is not None and pro.price_toman == 1000000 and pro.credit_grant == 1200


@pytest.mark.asyncio
async def test_checkout_basic_creates_pending_with_snapshot(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        result = await _checkout(service, user_id)
        assert result.redirect_url is not None and result.amount_toman == 500000
        payment = await payments_repo.get_by_id(session, result.payment_id)
        assert payment.status == "pending"
        assert payment.authority == provider.authority
        assert len(payment.authority) == 36
        assert payment.credit_grant == 500
        assert payment.provider_amount == 5000000
        assert payment.provider_currency == "IRR"
        assert len(provider.request_calls) == 1
        # هنوز هیچ grantی
        assert await _count(session, "credit_ledger", user_id) == 0


@pytest.mark.asyncio
async def test_checkout_unknown_and_inactive_product(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        with pytest.raises(AppError) as excinfo:
            await _checkout(service, user_id, product="pro-max")
        assert excinfo.value.code == "unknown_product"
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(text("UPDATE product_catalog SET active = false WHERE product_id = 'basic'"))
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, FakeProvider())
        with pytest.raises(AppError) as excinfo:
            await _checkout(service, user_id)
        assert excinfo.value.code == "unknown_product"


@pytest.mark.asyncio
async def test_checkout_same_key_same_payload_no_second_provider_call(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        first = await _checkout(service, user_id)
        second = await _checkout(service, user_id)
        assert first.payment_id == second.payment_id
        assert second.redirect_url is not None
        assert len(provider.request_calls) == 1
        assert await _count(session, "payment_transactions", user_id) == 1


@pytest.mark.asyncio
async def test_checkout_same_key_different_payload_conflict(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        await _checkout(service, user_id, key="key-x")
        with pytest.raises(AppError) as excinfo:
            await _checkout(service, user_id, key="key-x", product="pro")
        assert excinfo.value.code == "idempotency_conflict"
        assert await _count(session, "payment_transactions", user_id) == 1


@pytest.mark.asyncio
async def test_checkout_concurrent_retries_single_provider_request(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        await PaymentService(session, provider).checkout(user_id, "basic", idempotency_key="key-c", request_id="r")
        await session.commit()

    async def retry() -> str:
        async with TEST_SESSION_FACTORY() as session:
            service = PaymentService(session, provider)
            outcome = await service.checkout(user_id, "basic", idempotency_key="key-c", request_id="r")
            await session.commit()
            return outcome.status

    outcomes = await asyncio.gather(retry(), retry(), retry())
    assert all(status in ("pending", "requesting") for status in outcomes)
    assert len(provider.request_calls) == 1


@pytest.mark.asyncio
async def test_provider_definitive_rejection_marks_failed(user_id) -> None:
    provider = FakeProvider()
    provider.request_error = PaymentProviderMerchantError("merchant_error")
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        result = await _checkout(service, user_id)
        assert result.status == "failed"
        payment = await payments_repo.get_by_id(session, result.payment_id)
        assert payment.status == "failed"
        assert payment.failure_code == "merchant"
        assert await _count(session, "credit_ledger", user_id) == 0


@pytest.mark.asyncio
async def test_uncertain_provider_outcome_stays_requesting_no_grant(user_id) -> None:
    provider = FakeProvider()
    provider.request_error = PaymentProviderTransportError("transport")
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        result = await _checkout(service, user_id)
        assert result.status == "requesting"
        assert result.redirect_url is None
        payment = await payments_repo.get_by_id(session, result.payment_id)
        assert payment.status == "requesting"
        assert await _count(session, "credit_ledger", user_id) == 0


@pytest.mark.asyncio
async def test_malformed_provider_response_stays_requesting(user_id) -> None:
    provider = FakeProvider()
    provider.request_error = PaymentProviderMalformedError("malformed")
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        result = await _checkout(service, user_id)
        assert result.status == "requesting"


@pytest.mark.asyncio
async def test_reconcile_stale_requesting_bounded(user_id) -> None:
    provider = FakeProvider()
    provider.request_error = PaymentProviderTransportError("transport")
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        for i in range(4):
            outcome = await service.checkout(user_id, "basic", idempotency_key=f"key-r-{i}", request_id="r")
            assert outcome.status == "requesting"
        await session.commit()
        await session.execute(
            text("UPDATE payment_transactions SET created_at = :t WHERE user_id = :u"),
            {"t": datetime.now(UTC) - timedelta(hours=1), "u": str(user_id)},
        )
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, FakeProvider())
        assert await service.reconcile_stale_requesting(batch_limit=2, user_id=user_id) == 2
        await session.commit()
        with pytest.raises(AppError) as excinfo:
            await service.reconcile_stale_requesting(batch_limit=0, user_id=user_id)
        assert excinfo.value.code == "invalid_batch_limit"
    async with TEST_SESSION_FACTORY() as session:
        statuses = (
            await session.execute(text("SELECT status FROM payment_transactions WHERE user_id = :u"), {"u": str(user_id)})
        ).scalars().all()
        assert sorted(statuses) == ["requesting", "requesting", "unknown_outcome", "unknown_outcome"]


@pytest.mark.asyncio
async def test_verify_success_grants_exactly_once_and_ledger_consistent(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        outcome = await _checkout(service, user_id)
        payment_id = outcome.payment_id
        assert await service.verify_and_finalize(provider.authority, "req") == "succeeded"
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, payment_id)
        assert payment.status == "succeeded"
        assert payment.ref_id == "REF-1"
        account = await accounts_repo.get_for_update(session, user_id)
        assert account.available_balance == 500
        assert await ledger_repo.sum_balance_affecting(session, user_id) == 500
        keys = (await session.execute(text("SELECT idempotency_key FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})).scalars().all()
        assert keys == [f"payment:{payment_id}:credit-grant"]


@pytest.mark.asyncio
async def test_repeated_and_concurrent_callbacks_single_grant(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        await _checkout(service, user_id)
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        assert await service.verify_and_finalize(provider.authority) == "succeeded"
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        assert await service.verify_and_finalize(provider.authority) == "succeeded"

    async def callback() -> str:
        async with TEST_SESSION_FACTORY() as session:
            svc = PaymentService(session, provider)
            outcome = await svc.verify_and_finalize(provider.authority)
            await session.commit()
            return outcome

    results = await asyncio.gather(callback(), callback())
    assert all(r == "succeeded" for r in results)
    async with TEST_SESSION_FACTORY() as session:
        assert await _count(session, "credit_ledger", user_id) == 1
        account = await accounts_repo.get_for_update(session, user_id)
        assert account.available_balance == 500


@pytest.mark.asyncio
async def test_verify_101_already_verified_local_succeeded(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        await _checkout(service, user_id)
        await service.verify_and_finalize(provider.authority)
        await session.commit()
    provider.verify_result = VerifyResult(code=101, ref_id="REF-2")
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        assert await service.verify_and_finalize(provider.authority) == "succeeded"
        assert await _count(session, "credit_ledger", user_id) == 1


@pytest.mark.asyncio
async def test_verify_101_already_verified_local_pending_finalizes_once(user_id) -> None:
    provider = FakeProvider()
    provider.verify_result = VerifyResult(code=101, ref_id="REF-2")
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        outcome = await _checkout(service, user_id)
        assert await service.verify_and_finalize(provider.authority) == "succeeded"
        assert outcome.status == "pending"
    async with TEST_SESSION_FACTORY() as session:
        assert await _count(session, "credit_ledger", user_id) == 1
        account = await accounts_repo.get_for_update(session, user_id)
        assert account.available_balance == 500


@pytest.mark.asyncio
async def test_verify_transport_outcome_unresolved_no_grant(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        outcome = await _checkout(service, user_id)
        payment_id = outcome.payment_id
    provider.verify_error = PaymentProviderTransportError("transport")
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        assert await service.verify_and_finalize(provider.authority) == "unresolved"
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, payment_id)
        assert payment.status == "pending"
        assert await _count(session, "credit_ledger", user_id) == 0
        cases = await session.execute(text("SELECT count(*) FROM admin_audit_log WHERE action = 'payment_reconcile_case'"))
        assert cases.scalar_one() >= 1


@pytest.mark.asyncio
async def test_verify_provider_rejection_marks_failed_no_grant(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        outcome = await _checkout(service, user_id)
        payment_id = outcome.payment_id
    provider.verify_result = VerifyResult(code=-50)
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        assert await service.verify_and_finalize(provider.authority) == "failed"
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, payment_id)
        assert payment.status == "failed"
        assert await _count(session, "credit_ledger", user_id) == 0


@pytest.mark.asyncio
async def test_unknown_authority_and_status_nok_alone_do_not_finalize(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        await _checkout(service, user_id)
        assert await service.verify_and_finalize("A9999999999999999999999999999999999999999") == "not_found"
        # Status=NOK به‌تنهایی نباید چیزی را نهایی کند؛ verify همچنان واقعی اجرا می‌شود.
        assert await service.verify_and_finalize(provider.authority) == "succeeded"
    async with TEST_SESSION_FACTORY() as session:
        assert await _count(session, "credit_ledger", user_id) == 1


@pytest.mark.asyncio
async def test_finalize_atomic_rollback_leaves_pending_and_no_balance(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        outcome = await _checkout(service, user_id)
        payment_id = outcome.payment_id
        # درج دستی رکورد ledger با همان کلید → IntegrityError در فاینال → rollback کامل.
        await ledger_repo.create(
            session,
            user_id=user_id,
            kind="plan_grant",
            amount=500,
            idempotency_key=f"payment:{payment_id}:credit-grant",
        )
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        with pytest.raises(sqlalchemy_exc.IntegrityError):
            await service.verify_and_finalize(provider.authority)
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, payment_id)
        assert payment.status == "pending"
        account = await accounts_repo.get_for_update(session, user_id)
        assert account.available_balance == 0
        assert await ledger_repo.sum_balance_affecting(session, user_id) == 500  # فقط رکورد دستی


@pytest.mark.asyncio
async def test_missing_account_created_during_finalize(user_id) -> None:
    new_user = await _make_user(balance=None)
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        await _checkout(service, new_user)
        assert await service.verify_and_finalize(provider.authority) == "succeeded"
    async with TEST_SESSION_FACTORY() as session:
        account = await accounts_repo.get_for_update(session, new_user)
        assert account.available_balance == 500


@pytest.mark.asyncio
async def test_snapshot_survives_catalog_change(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        outcome = await _checkout(service, user_id)
        payment_id = outcome.payment_id
        assert outcome.amount_toman == 500000
    async with TEST_SESSION_FACTORY() as session:
        before, after = await catalog_repo.update_price_and_grant(
            session, "basic", price_toman=550000, credit_grant=550, actor_user_id=user_id, reason="price change"
        )
        assert before is not None and after is not None
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, payment_id)
        assert payment.amount_toman == 500000
        assert payment.credit_grant == 500


@pytest.mark.asyncio
async def test_catalog_update_requires_admin_and_supported_ids(user_id) -> None:
    from app.scripts.upsert_product import upsert_product

    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(AppError) as excinfo:
            await upsert_product(session, product_id="pro-max", price_toman=1, credit_grant=1, actor_user_id=user_id, reason="r")
        assert excinfo.value.code == "unsupported_product"
        with pytest.raises(AppError) as excinfo:
            await upsert_product(session, product_id="basic", price_toman=550000, credit_grant=550, actor_user_id=user_id, reason="r")
        assert excinfo.value.code == "actor_required"
        await session.rollback()


@pytest.mark.asyncio
async def test_catalog_update_success_writes_audit_atomically() -> None:
    from app.scripts.upsert_product import upsert_product

    admin_id = await _make_user(balance=None)
    async with TEST_SESSION_FACTORY() as session:
        admin = await users_repo.get_by_id(session, admin_id)
        admin.role = "admin"
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        await upsert_product(session, product_id="basic", price_toman=550000, credit_grant=550, actor_user_id=admin_id, reason="price review")
    async with TEST_SESSION_FACTORY() as session:
        basic = await catalog_repo.get_active(session, "basic")
        assert basic.price_toman == 550000 and basic.credit_grant == 550
        row = (
            await session.execute(
                text(
                    "SELECT before, after FROM admin_audit_log "
                    "WHERE action = 'catalog_price_change' ORDER BY created_at DESC LIMIT 1"
                )
            )
        ).one()
        assert row[0] == {"price_toman": 500000, "credit_grant": 500, "active": True}
        assert row[1] == {"price_toman": 550000, "credit_grant": 550, "active": True}


@pytest.mark.asyncio
async def test_user_deletion_does_not_cascade_payments(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        await _checkout(service, user_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(sqlalchemy_exc.IntegrityError):
            await session.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        assert await _count(session, "payment_transactions", user_id) == 1


@pytest.mark.asyncio
async def test_catalog_update_rolls_back_when_audit_insert_fails() -> None:
    """Gap A: شکست درج audit → تغییر کاتالوگ و رویداد جزئی rollback می‌شود."""
    admin_id = await _make_user(balance=None)
    async with TEST_SESSION_FACTORY() as session:
        admin = await users_repo.get_by_id(session, admin_id)
        admin.role = "admin"
        await session.commit()

    async with TEST_SESSION_FACTORY() as session:
        before_count = (await session.execute(text("SELECT count(*) FROM admin_audit_log"))).scalar_one()
        before_price = (await catalog_repo.get_active(session, "basic")).price_toman

    async def failing_audit_create(*args, **kwargs):
        raise RuntimeError("simulated-audit-failure")

    async with TEST_SESSION_FACTORY() as session:
        original_create = audit_module.create
        audit_module.create = failing_audit_create
        try:
            with pytest.raises(RuntimeError, match="simulated-audit-failure"):
                await upsert_product(session, product_id="basic", price_toman=550000, credit_grant=550, actor_user_id=admin_id, reason="r")
        finally:
            audit_module.create = original_create
        await session.rollback()

    async with TEST_SESSION_FACTORY() as session:
        basic = await catalog_repo.get_active(session, "basic")
        assert basic.price_toman == before_price and basic.credit_grant == 500
        after_count = (await session.execute(text("SELECT count(*) FROM admin_audit_log"))).scalar_one()
        assert after_count == before_count


@pytest.mark.asyncio
async def test_finalize_uncertain_commit_ack_is_resolved_by_reread_no_second_grant(user_id) -> None:
    """Gap B: commit پایدار ولی بدون acknowledgement → بازخوانی وضعیت پایدار، بدون grant دوم."""
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        outcome = await _checkout(service, user_id)
        await session.commit()
        payment_id = outcome.payment_id

    class SimulatedAckError(RuntimeError):
        pass

    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        real_commit = session.commit

        async def commit_then_raise():
            await real_commit()
            raise SimulatedAckError("ack-lost-after-durable-commit")

        session.commit = commit_then_raise  # type: ignore[method-assign]
        try:
            with pytest.raises(SimulatedAckError):
                await service.verify_and_finalize(provider.authority)
        finally:
            session.commit = real_commit  # type: ignore[method-assign]
        await session.rollback()

    # وضعیت پایدار دوباره خوانده می‌شود؛ بدون کار مالی تکراری.
    async with TEST_SESSION_FACTORY() as session:
        payment = await payments_repo.get_by_id(session, payment_id)
        assert payment.status == "succeeded"
        account = await accounts_repo.get_for_update(session, user_id)
        assert account.available_balance == 500
        assert await ledger_repo.sum_balance_affecting(session, user_id) == 500
        keys = (await session.execute(text("SELECT idempotency_key FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})).scalars().all()
        assert keys == [f"payment:{payment_id}:credit-grant"]

    # retry idempotent (پس از دریافت مجدد درخواست) نباید grant دوم بسازد.
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        assert await service.verify_and_finalize(provider.authority) == "succeeded"
    async with TEST_SESSION_FACTORY() as session:
        assert await _count(session, "credit_ledger", user_id) == 1


@pytest.mark.asyncio
async def test_manual_resolution_is_auditable_and_does_not_grant(user_id) -> None:
    provider = FakeProvider()
    async with TEST_SESSION_FACTORY() as session:
        service = PaymentService(session, provider)
        outcome = await _checkout(service, user_id)
        payment_id = outcome.payment_id
        await service.record_manual_resolution(
            actor_user_id=user_id, payment_id=payment_id, reason="review", evidence_ref="CASE-1"
        )
        with pytest.raises(AppError):
            await service.record_manual_resolution(actor_user_id=user_id, payment_id=payment_id, reason="  ", evidence_ref="")
    async with TEST_SESSION_FACTORY() as session:
        cases = await session.execute(
            text("SELECT count(*) FROM admin_audit_log WHERE action = 'payment_manual_resolution' AND entity_id = :e"),
            {"e": str(payment_id)},
        )
        assert cases.scalar_one() == 1
        assert await _count(session, "credit_ledger", user_id) == 0
