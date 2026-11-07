"""سرویس پلن‌ها و entitlementها (ADR-052؛ تصمیم‌های مالک 2026-10-31)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.payment_transaction import PaymentTransaction
from app.models.plan_entitlement import PlanEntitlement
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import entitlements as ent_repo
from app.repositories import users as users_repo

ENTITLEMENT_NOT_FOUND = AppError("entitlement_not_found", 404, "پلن فعال یافت نشد.")
CANCELLATION_ALREADY_PENDING = AppError("cancellation_already_pending", 409, "درخواست لغوی در انتظار است.")
CANCELLATION_NOT_PENDING = AppError("cancellation_not_pending", 409, "درخواست لغو در وضعیت قابل تغییر نیست.")
ADMIN_REQUIRED = AppError("admin_required", 403, "این عملیات فقط برای ادمین مجاز است.")
REFUND_NOT_PENDING = AppError("refund_not_pending", 409, "درخواست بازپرداخت در وضعیت قابل تصمیم نیست.")
UNLIMITED_INACTIVE = AppError("unlimited_inactive", 403, "پلن Unlimited فعال نیست.")
CANCELLATION_REASON_REQUIRED = AppError("cancellation_reason_required", 422, "دلیل الزامی است.")


class PlanService:
    """orchestration دامنهٔ پلن؛ فراخواننده تراکنش را commit می‌کند."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    def _now(self) -> datetime:
        return datetime.now(UTC)

    # ------------------------------------------------------------- activation

    async def process_paid_payment(self, payment: PaymentTransaction) -> PlanEntitlement:
        """پس از فاینال مالی پرداخت: ساخت/تمدید entitlement (Basic/Pro/Unlimited)."""
        now = self._now()
        product_id = payment.product_id
        plan_type = payment.plan_type
        duration = timedelta(days=payment.duration_days)
        snapshot: dict[str, object] = {
            "product_id": product_id,
            "amount_toman": payment.amount_toman,
            "credit_grant": payment.credit_grant,
            "plan_type": plan_type,
            "duration_days": payment.duration_days,
        }
        existing = await ent_repo.get_active_entitlement(self._session, payment.user_id, product_id)
        if existing is not None:
            new_expiry = existing.expires_at + duration
            await ent_repo.extend_entitlement_expiry(self._session, existing.id, new_expiry)
            if plan_type == "credit" and payment.credit_grant > 0:
                await ent_repo.add_credits(self._session, existing.id, payment.credit_grant)
                await ent_repo.create_grant(
                    self._session,
                    user_id=payment.user_id,
                    entitlement_id=existing.id,
                    kind="plan_grant",
                    amount=payment.credit_grant,
                    expires_at=new_expiry,
                    payment_id=payment.id,
                )
            return existing

        entitlement = await ent_repo.create_entitlement(
            self._session,
            user_id=payment.user_id,
            product_id=product_id,
            plan_type=plan_type,
            activated_at=now,
            expires_at=now + duration,
            granted_credits=payment.credit_grant if plan_type == "credit" else 0,
            payment_id=payment.id,
            snapshot=snapshot,
        )
        if plan_type == "credit" and payment.credit_grant > 0:
            await ent_repo.create_grant(
                self._session,
                user_id=payment.user_id,
                entitlement_id=entitlement.id,
                kind="plan_grant",
                amount=payment.credit_grant,
                expires_at=entitlement.expires_at,
                payment_id=payment.id,
            )
        return entitlement

    async def is_unlimited_active(self, user_id: uuid.UUID, now: datetime | None = None) -> bool:
        moment = now or self._now()
        entitlement = await ent_repo.get_active_entitlement(self._session, user_id, "unlimited")
        return entitlement is not None and entitlement.expires_at > moment

    # ------------------------------------------------------------- expiry job

    async def expire_due_entitlements(
        self, *, batch_limit: int = 200, user_id: uuid.UUID | None = None
    ) -> int:
        """انقضای اتمیک: entitlement → expired؛ باطل‌سازی grantها + رویداد جبرانی ledger + projection.

        user_id اختیاری است؛ اگر داده شود فقط همان کاربر بررسی می‌شود (برای هدف‌گیری/تست).
        """
        if batch_limit < 1:
            raise AppError("invalid_batch_limit", 422, "سقف دسته نامعتبر است.")
        now = self._now()
        due = await ent_repo.list_expired_active(self._session, now, batch_limit, user_id)
        expired = 0
        for entitlement in due:
            # ادعای اتمیک با savepoint: فقط برنده، ledger/balance/void را اعمال می‌کند؛
            # بازنده (worker هم‌زمان) بدون خطا رد می‌شود (C-03).
            try:
                async with self._session.begin_nested():
                    claimed = await ent_repo.mark_expired(self._session, entitlement.id, now)
                    if not claimed:
                        continue
                    if entitlement.plan_type == "credit":
                        # ترتیب قفل: ابتدا حساب (مشابه reserve/release)، سپس grantها با ترتیب EFF
                        # (مشابه reserve_credit) تا از deadlock با مسیرهای هم‌زمان جلوگیری شود.
                        account = await accounts_repo.get_for_update(self._session, entitlement.user_id)
                        grants = await ent_repo.lock_grants_for_lifecycle(self._session, entitlement.id)
                        for grant in grants:
                            if grant.remaining_amount < grant.reserved_amount:
                                raise AppError(
                                    "grant_accounting_invariant_violated", 500,
                                    "Invariant breach: remaining_amount < reserved_amount during expiry.",
                                )
                        # فقط بخش غیررزروشده (remaining - reserved) قابل ابطال است؛ بدهیِ
                        # ازپیش‌ثبت‌شدهٔ رزروهای فعال دوباره کسر نمی‌شود (OQ-027).
                        voidable = sum(g.remaining_amount - g.reserved_amount for g in grants)
                        if voidable > 0:
                            await ledger_repo.create(
                                self._session,
                                user_id=entitlement.user_id,
                                kind="adjust",
                                amount=-voidable,
                                idempotency_key=f"entitlement:{entitlement.id}:expiry-void",
                                request_id=None,
                                reason="plan credit expiry void",
                            )
                            account.available_balance -= voidable
                        await ent_repo.void_all_grants_of_entitlement(
                            self._session, entitlement.id, reason="natural_expiry", effective_at=now
                        )
                    expired += 1
            except IntegrityError as exc:
                # تنها علت قابل قبول: برخورد کلید idempotency رویداد انقضا (worker دیگر).
                if "uq_credit_ledger_user_key" not in str(exc):
                    raise
                continue
        return expired

    # ------------------------------------------------------------- cancellation

    async def request_cancellation(self, user_id: uuid.UUID, entitlement_id: uuid.UUID) -> None:
        from sqlalchemy import select

        result = await self._session.execute(
            select(PlanEntitlement).where(PlanEntitlement.id == entitlement_id, PlanEntitlement.user_id == user_id)
        )
        entitlement = result.scalar_one_or_none()
        if entitlement is None:
            raise ENTITLEMENT_NOT_FOUND
        pending = await ent_repo.get_pending_cancellation(self._session, user_id, entitlement_id)
        if pending is not None:
            raise CANCELLATION_ALREADY_PENDING
        await ent_repo.create_cancellation_request(self._session, user_id=user_id, entitlement_id=entitlement_id)
        await self._session.flush()

    async def withdraw_cancellation(self, user_id: uuid.UUID, request_id: uuid.UUID) -> None:
        if not await ent_repo.withdraw_cancellation(self._session, request_id, user_id):
            raise CANCELLATION_NOT_PENDING
        await self._session.flush()

    async def decide_cancellation(
        self,
        request_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        approve: bool,
        reason: str,
        mode: str | None = None,
    ) -> None:
        if not reason.strip():
            raise CANCELLATION_REASON_REQUIRED
        actor = await users_repo.get_by_id(self._session, actor_user_id)
        if actor is None or actor.role != "admin":
            raise ADMIN_REQUIRED
        from sqlalchemy import select

        from app.models.cancellation_request import CancellationRequest

        result = await self._session.execute(select(CancellationRequest).where(CancellationRequest.id == request_id))
        request = result.scalar_one_or_none()
        if request is None:
            raise AppError("cancellation_not_found", 404, "درخواست لغو یافت نشد.")
        if request.status != "pending":
            raise CANCELLATION_NOT_PENDING
        if approve and mode not in ("preserve_until_expiry", "immediate"):
            raise AppError("cancellation_mode_required", 422, "برای تأیید، حالت لغو الزامی است.")
        won = await ent_repo.decide_cancellation(
            self._session, request_id, approve=approve, decided_by=actor_user_id, reason=reason, now=self._now(), mode=mode
        )
        if not won:
            raise CANCELLATION_NOT_PENDING
        if approve:
            await self._apply_cancellation_effect(request, mode)
        await self._session.flush()

    async def _lock_unreserved_for_lifecycle(self, entitlement_id: uuid.UUID) -> int:
        """قفل grantهای non-voided این entitlement و محاسبهٔ بخش غیررزروشده زیر قفل.

        ترتیب قفل `lock_grants_for_lifecycle` است (EFF، مشابه reserve_credit)؛ فراخواننده
        ابتدا حساب را قفل می‌کند تا با مسیرهای هم‌زمان deadlock ایجاد نشود.
        """
        grants = await ent_repo.lock_grants_for_lifecycle(self._session, entitlement_id)
        for grant in grants:
            if grant.remaining_amount < grant.reserved_amount:
                raise AppError(
                    "grant_accounting_invariant_violated", 500,
                    "Invariant breach: remaining_amount < reserved_amount.",
                )
        return sum(g.remaining_amount - g.reserved_amount for g in grants)

    async def _apply_cancellation_effect(self, request: object, mode: str | None) -> None:
        from app.models.cancellation_request import CancellationRequest

        if not isinstance(request, CancellationRequest):
            return
        entitlement = await self._get_entitlement_by_id(request.entitlement_id)
        if entitlement is None:
            return
        if mode == "preserve_until_expiry":
            return  # دسترسی تا expiry؛ بدون تمدید
        # immediate: پایان فوری + ابطال اعتبارهای باقی‌مانده همان پلن.
        # فقط بخش غیررزروشده (remaining - reserved) باطل و از موجودی کسر می‌شود؛
        # بدهیِ ازپیش‌ثبت‌شدهٔ رزروهای فعال دوباره کسر نمی‌شود (D-04/OQ-028).
        if entitlement.plan_type == "credit":
            account = await accounts_repo.get_for_update(self._session, entitlement.user_id)
            voidable = await self._lock_unreserved_for_lifecycle(entitlement.id)
            if voidable > 0:
                await ledger_repo.create(
                    self._session,
                    user_id=entitlement.user_id,
                    kind="adjust",
                    amount=-voidable,
                    idempotency_key=f"entitlement:{entitlement.id}:cancel-void",
                    request_id=None,
                    reason="immediate cancellation credit void",
                )
                account.available_balance -= voidable
            now = self._now()
            await ent_repo.void_all_grants_of_entitlement(
                self._session, entitlement.id, reason="immediate_cancellation", effective_at=now, now=now
            )
        await ent_repo.mark_cancelled(
            self._session, entitlement.id, by=request.decided_by, reason=request.decision_reason or "", now=self._now()
        ) if request.decided_by is not None else None

    async def _get_entitlement_by_id(self, entitlement_id: uuid.UUID) -> PlanEntitlement | None:
        from sqlalchemy import select

        result = await self._session.execute(select(PlanEntitlement).where(PlanEntitlement.id == entitlement_id))
        return result.scalar_one_or_none()

    # ----------------------------------------------------------------- refund

    async def request_refund(
        self,
        *,
        user_id: uuid.UUID,
        payment_id: uuid.UUID,
        entitlement_id: uuid.UUID | None,
        requested_amount: int,
        reason: str,
    ) -> None:
        if requested_amount <= 0 or not reason.strip():
            raise AppError("invalid_refund_request", 422, "مبلغ و دلیل نامعتبر است.")
        await ent_repo.create_refund_request(
            self._session, payment_id=payment_id, entitlement_id=entitlement_id, requested_amount=requested_amount, reason=reason
        )
        await self._session.flush()

    async def decide_refund(
        self,
        refund_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        approve: bool,
        reason: str,
        credit_voided: int = 0,
    ) -> None:
        if not reason.strip():
            raise AppError("refund_reason_required", 422, "دلیل الزامی است.")
        actor = await users_repo.get_by_id(self._session, actor_user_id)
        if actor is None or actor.role != "admin":
            raise ADMIN_REQUIRED
        record = await ent_repo.get_refund_by_id(self._session, refund_id)
        if record is None:
            raise AppError("refund_not_found", 404, "درخواست بازپرداخت یافت نشد.")
        if record.status != "requested":
            raise REFUND_NOT_PENDING
        won = await ent_repo.decide_refund(
            self._session,
            refund_id,
            approve=approve,
            decided_by=actor_user_id,
            reason=reason,
            now=self._now(),
            approved_amount=record.requested_amount if approve else None,
            credit_voided=credit_voided if approve else 0,
        )
        if not won:
            raise REFUND_NOT_PENDING
        if approve and credit_voided > 0 and record.entitlement_id is not None:
            entitlement = await self._get_entitlement_by_id(record.entitlement_id)
            if entitlement is not None:
                # ابتدا حساب، سپس grantها (ترتیب قفل مشابه reserve/expiry).
                account = await accounts_repo.get_for_update(self._session, entitlement.user_id)
                non_reserved = await self._lock_unreserved_for_lifecycle(entitlement.id)
                # مبلغ باطل‌سازی نباید از بخش غیررزروشده تجاوز کند؛ در غیر این صورت
                # اعتبارِ تعهدشده به رزروهای فعال دوباره کسر می‌شود (D-04).
                if credit_voided > non_reserved:
                    raise AppError(
                        "refund_credit_void_exceeds_unreserved", 409,
                        "credit_voided exceeds the unreserved credit of the entitlement.",
                    )
                await ledger_repo.create(
                    self._session,
                    user_id=entitlement.user_id,
                    kind="adjust",
                    amount=-credit_voided,
                    idempotency_key=f"refund:{refund_id}:void",
                    request_id=None,
                    reason="refund approved credit void",
                )
                account.available_balance -= credit_voided
                now = self._now()
                await ent_repo.void_all_grants_of_entitlement(
                    self._session, entitlement.id, reason="approved_refund", effective_at=now, now=now
                )
        await self._session.flush()
