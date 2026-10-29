"""سرویس دامنهٔ پرداخت (ADR-047): checkout، نهایی‌سازی اتمیک، reconcile و resolution."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.payment_transaction import PaymentTransaction
from app.repositories import admin_audit_log as audit_repo
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import payment_transactions as payments_repo
from app.repositories import product_catalog as catalog_repo
from app.services.payment_provider import (
    VERIFY_CODE_ALREADY_VERIFIED,
    VERIFY_CODE_SUCCESS,
    PaymentProvider,
    PaymentProviderError,
    PaymentProviderMerchantError,
    PaymentProviderValidationError,
    VerifyResult,
    ZarinPalProvider,
)

IDEMPOTENCY_CONFLICT = AppError("idempotency_conflict", 409, "کلید یکتا با بار متفاوت استفاده شده است.")
UNKNOWN_PRODUCT = AppError("unknown_product", 404, "محصول موردنظر موجود نیست.")
CATALOG_UNAVAILABLE = AppError("catalog_unavailable", 503, "کاتالوگ محصولات موقتاً در دسترس نیست.")
PAYMENT_NOT_FOUND = AppError("payment_not_found", 404, "پرداخت یافت نشد.")
INVALID_PAYMENT_STATE = AppError("invalid_payment_state", 409, "وضعیت پرداخت اجازهٔ این گذار را نمی‌دهد.")


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    payment_id: uuid.UUID
    status: str
    redirect_url: str | None = None
    amount_toman: int | None = None


def canonical_payload_fingerprint(product_id: str) -> str:
    """Fingerprint پایدار از فیلد معنایی نرمال‌شده (فقط product_id)."""
    canonical = json.dumps({"product_id": product_id}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PaymentService:
    """orchestration دامنهٔ پرداخت؛ نهایی‌سازی اتمیک و idempotent."""

    def __init__(self, session: AsyncSession, provider: PaymentProvider | None = None) -> None:
        self._session = session
        self._settings = get_settings()
        self._provider = provider or ZarinPalProvider(self._settings)

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _existing_outcome(self, payment: PaymentTransaction) -> CheckoutResult:
        if payment.status == payments_repo.STATUS_PENDING and payment.authority:
            redirect_url = self._provider.gateway_url(payment.authority)
            return CheckoutResult(payment.id, payment.status, redirect_url=redirect_url, amount_toman=payment.amount_toman)
        return CheckoutResult(payment.id, payment.status)

    async def checkout(
        self,
        user_id: uuid.UUID,
        product_id: str,
        *,
        idempotency_key: str,
        request_id: str | None = None,
    ) -> CheckoutResult:
        fingerprint = canonical_payload_fingerprint(product_id)

        existing = await payments_repo.get_by_idempotency_key(self._session, user_id, idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise IDEMPOTENCY_CONFLICT
            return self._existing_outcome(existing)

        try:
            product = await catalog_repo.get_active(self._session, product_id)
        except SQLAlchemyError as exc:
            raise CATALOG_UNAVAILABLE from exc
        if product is None:
            raise UNKNOWN_PRODUCT

        provider_amount = self._provider.to_provider_amount(product.price_toman)
        payment = await payments_repo.create(
            self._session,
            user_id=user_id,
            product_id=product.product_id,
            amount_toman=product.price_toman,
            credit_grant=product.credit_grant,
            provider=self._settings.payment_provider,
            provider_currency="IRR",
            provider_amount=provider_amount,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            request_id=request_id,
        )
        await self._session.commit()

        claimed = await payments_repo.try_claim_request(self._session, payment.id)
        await self._session.commit()
        if not claimed:
            refreshed = await payments_repo.get_by_id(self._session, payment.id)
            if refreshed is None:
                raise INVALID_PAYMENT_STATE
            return self._existing_outcome(refreshed)

        try:
            authority = await self._provider.request_payment(
                payment.amount_toman,
                self._settings.zarinpal_callback_url,
                f"darsyar-{product.product_id}",
            )
        except PaymentProviderMerchantError as exc:
            await payments_repo.try_mark_failed(
                self._session, payment.id, failure_code=exc.category, failure_reason=exc.message
            )
            await self._session.commit()
            return CheckoutResult(payment.id, payments_repo.STATUS_FAILED)
        except PaymentProviderValidationError as exc:
            await payments_repo.try_mark_failed(
                self._session, payment.id, failure_code=exc.category, failure_reason=exc.message
            )
            await self._session.commit()
            return CheckoutResult(payment.id, payments_repo.STATUS_FAILED)
        except (PaymentProviderError, OSError):
            # غیرقطعی: بدون failed، بدون resend؛ در requesting می‌ماند تا reconcile.
            await self._session.rollback()
            return CheckoutResult(payment.id, payments_repo.STATUS_REQUESTING)

        persisted = await payments_repo.try_persist_authority(self._session, payment.id, authority)
        await self._session.commit()
        if not persisted:
            refreshed = await payments_repo.get_by_id(self._session, payment.id)
            if refreshed is None:
                raise INVALID_PAYMENT_STATE
            return self._existing_outcome(refreshed)
        redirect_url = self._provider.gateway_url(authority)
        return CheckoutResult(payment.id, payments_repo.STATUS_PENDING, redirect_url=redirect_url, amount_toman=payment.amount_toman)

    async def finalize_succeeded(self, payment: PaymentTransaction, ref_id: str) -> PaymentTransaction:
        """فاینال اتمیک: pending→succeeded + ledger plan_grant + balance + ref_id."""
        won = await payments_repo.try_finalize_succeeded(self._session, payment.id, ref_id, self._now())
        if not won:
            refreshed = await payments_repo.get_by_id(self._session, payment.id)
            if refreshed is not None and refreshed.status == payments_repo.STATUS_SUCCEEDED:
                return refreshed
            raise INVALID_PAYMENT_STATE

        if not await accounts_repo.exists(self._session, payment.user_id):
            await accounts_repo.create(self._session, user_id=payment.user_id, available_balance=0)
        account = await accounts_repo.get_for_update(self._session, payment.user_id)
        await ledger_repo.create(
            self._session,
            user_id=payment.user_id,
            kind="plan_grant",
            amount=payment.credit_grant,
            idempotency_key=f"payment:{payment.id}:credit-grant",
            request_id=payment.request_id,
            reason=f"one-time purchase {payment.product_id}",
        )
        account.available_balance += payment.credit_grant
        await self._session.flush()
        return payment

    async def verify_and_finalize(self, authority: str, request_id: str | None = None) -> str:
        """جریان callback: lookup + verify خارج از تراکنش + نهایی‌سازی اتمیک."""
        payment = await payments_repo.get_by_authority(self._session, authority)
        if payment is None:
            return "not_found"
        if payment.status == payments_repo.STATUS_SUCCEEDED:
            return "succeeded"
        if payment.status != payments_repo.STATUS_PENDING:
            await audit_repo.create(
                self._session,
                action="payment_reconcile_case",
                entity_type="payment_transaction",
                entity_id=str(payment.id),
                reason=f"callback for non-pending payment in state {payment.status}",
                after={"status": payment.status},
            )
            await self._session.commit()
            return "unresolved"

        try:
            result: VerifyResult = await self._provider.verify_payment(authority, payment.amount_toman)
        except (PaymentProviderError, OSError):
            await audit_repo.create(
                self._session,
                action="payment_reconcile_case",
                entity_type="payment_transaction",
                entity_id=str(payment.id),
                reason="verification outcome uncertain",
            )
            await self._session.commit()
            return "unresolved"

        if result.code == VERIFY_CODE_SUCCESS or result.code == VERIFY_CODE_ALREADY_VERIFIED:
            ref_id = result.ref_id or authority
            try:
                await self.finalize_succeeded(payment, ref_id)
            except AppError:
                refreshed = await payments_repo.get_by_id(self._session, payment.id)
                if refreshed is not None and refreshed.status == payments_repo.STATUS_SUCCEEDED:
                    await self._session.commit()
                    return "succeeded"
                raise
            await self._session.commit()
            return "succeeded"

        await payments_repo.try_mark_failed(
            self._session, payment.id, failure_code=f"verify_code_{result.code}", failure_reason="provider rejected verification"
        )
        await audit_repo.create(
            self._session,
            action="payment_reconcile_case",
            entity_type="payment_transaction",
            entity_id=str(payment.id),
            reason=f"provider verification code {result.code} finalised as failed",
            after={"status": payments_repo.STATUS_FAILED},
        )
        await self._session.commit()
        return "failed"

    async def reconcile_stale_requesting(
        self,
        *,
        batch_limit: int,
        user_id: uuid.UUID | None = None,
        request_id: str | None = None,
    ) -> int:
        """reconcile محدود: requesting کهنه → unknown_outcome؛ بدون تماس provider.

        user_id اختیاری است؛ در صورت دادن فقط رزروهای همان کاربر بررسی می‌شوند (برای تست‌های ایزوله).
        """
        if batch_limit < 1:
            raise AppError("invalid_batch_limit", 422, "سقف دسته باید مثبت باشد.")
        cutoff = self._now() - timedelta(minutes=self._settings.payment_request_stale_minutes)
        stale = await payments_repo.list_stale_requesting(self._session, cutoff, batch_limit, user_id)
        moved = 0
        for payment in stale:
            if await payments_repo.try_mark_unknown_outcome(self._session, payment.id):
                moved += 1
        await self._session.commit()
        return moved

    async def record_manual_resolution(
        self,
        *,
        actor_user_id: uuid.UUID,
        payment_id: uuid.UUID,
        reason: str,
        evidence_ref: str,
    ) -> None:
        """بازرسی/ثبت auditable؛ بدون تغییر وضعیت و بدون grant خودکار (ADR-047)."""
        if not reason.strip() or not evidence_ref.strip():
            raise AppError("invalid_resolution_input", 422, "دلیل و مرجع شواهد الزامی است.")
        payment = await payments_repo.get_by_id(self._session, payment_id)
        if payment is None:
            raise PAYMENT_NOT_FOUND
        await audit_repo.create(
            self._session,
            actor_user_id=actor_user_id,
            action="payment_manual_resolution",
            entity_type="payment_transaction",
            entity_id=str(payment_id),
            reason=reason,
            after={"status": payment.status, "evidence_ref": evidence_ref},
        )
        await self._session.commit()

    async def list_unresolved(self, *, limit: int = 50) -> list[PaymentTransaction]:
        if limit < 1 or limit > 200:
            raise AppError("invalid_limit", 422, "محدودهٔ نامعتبر.")
        result = await self._session.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.status.in_([payments_repo.STATUS_REQUESTING, payments_repo.STATUS_UNKNOWN_OUTCOME]))
            .order_by(PaymentTransaction.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
