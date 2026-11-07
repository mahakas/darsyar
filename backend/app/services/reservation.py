"""سرویس دامنهٔ مالی Slice A: رزرو/تسویه/رهاسازی اتمیک و reconcile (ADR-035)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.credit_account import CreditAccount
from app.models.reservation import Reservation
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import entitlements as ent_repo
from app.repositories import reservations as reservations_repo

INSUFFICIENT_CREDIT = AppError("insufficient_credit", 409, "اعتبار کافی موجود نیست.")
RESERVATION_DEADLINE_MINUTES = 15
RESERVATION_DEADLINE_PASSED = AppError("reservation_deadline_passed", 409, "مهلت ۱۵ دقیقه‌ای رزرو گذشته است.")
IDEMPOTENCY_CONFLICT = AppError("idempotency_conflict", 409, "کلید یکتا با بار متفاوت استفاده شده است.")
INVALID_RESERVATION_STATE = AppError("invalid_reservation_state", 409, "وضعیت رزرو اجازهٔ این گذار را نمی‌دهد.")
RESERVATION_NOT_FOUND = AppError("reservation_not_found", 404, "رزرو یافت نشد.")


class FinanceService:
    """orchestration دامنهٔ مالی؛ تراکنش توسط فراخواننده commit می‌شود."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    def _now(self) -> datetime:
        return datetime.now(UTC)

    async def _ensure_account(self, user_id: uuid.UUID) -> CreditAccount:
        if not await accounts_repo.exists(self._session, user_id):
            return await accounts_repo.create(self._session, user_id=user_id)
        return await accounts_repo.get_for_update(self._session, user_id)

    async def reserve_credit(
        self,
        user_id: uuid.UUID,
        amount: int,
        *,
        idempotency_key: str,
        payload_fingerprint: str,
        request_id: str | None = None,
    ) -> Reservation:
        """رزرو مبتنی بر کردیت: قفل حساب + idempotency + بدهی موقت spend + کاهش موجودی."""
        if amount <= 0:
            raise AppError("invalid_reservation_amount", 422, "مبلغ رزرو باید مثبت باشد.")
        account = await self._ensure_account(user_id)

        existing = await reservations_repo.get_by_idempotency_key(self._session, user_id, idempotency_key)
        if existing is not None:
            if existing.payload_fingerprint != payload_fingerprint:
                raise IDEMPOTENCY_CONFLICT
            return existing

        # D-02: حین Unlimited فعال، مصرف عادی اعتبار مجاز نیست (grantها انتخاب نمی‌شوند).
        from app.services.plans import PlanService

        if await PlanService(self._session).is_unlimited_active(user_id):
            from app.core.errors import AppError as _AE

            raise _AE("unlimited_active_blocks_credit_reservation", 409, "حین پلن Unlimited فعال، رزرو اعتبار معمولی مجاز نیست.")

        # انتخاب EFF (D-01) فقط از grantهای معتبر و غیرکاملاً‌رزروشده
        now = self._now()
        eligible = await ent_repo.list_eligible_grants(self._session, user_id, now, exclude_reserved=True)
        eligible_total = sum(g.remaining_amount - g.reserved_amount for g in eligible)
        # legacy: فقط وقتی کاربر هیچ grantی ندارد (پیش از 0013)؛ ور نه fail-safe.
        legacy_fallback = eligible_total == 0 and account.available_balance >= amount and await ent_repo.count_grants(self._session, user_id) == 0
        if eligible_total < amount and not legacy_fallback:
            raise INSUFFICIENT_CREDIT
        if account.available_balance < amount:
            raise INSUFFICIENT_CREDIT

        reservation = await reservations_repo.create(
            self._session,
            user_id=user_id,
            kind="credit",
            amount=amount,
            idempotency_key=idempotency_key,
            payload_fingerprint=payload_fingerprint,
            request_id=request_id,
        )
        remaining_to_allocate = amount
        if not legacy_fallback:
            for grant in eligible:
                if remaining_to_allocate == 0:
                    break
                # قفل grant + بازاعتبارسنجی دلیل/واجد شرایط بودن در همان تراکنش (race-safe).
                locked = await ent_repo.get_grant_for_update(self._session, grant.id)
                if locked is None or locked.lifecycle_reason is not None:
                    continue
                take = min(remaining_to_allocate, locked.remaining_amount - locked.reserved_amount)
                if take <= 0:
                    continue
                if not await ent_repo.increase_reserved(self._session, locked.id, take):
                    raise INSUFFICIENT_CREDIT
                await ent_repo.create_allocation(self._session, reservation_id=reservation.id, grant_id=locked.id, amount=take)
                remaining_to_allocate -= take
            if remaining_to_allocate > 0:
                raise INSUFFICIENT_CREDIT
        await ledger_repo.create(
            self._session,
            user_id=user_id,
            reservation_id=reservation.id,
            kind="spend",
            amount=-amount,
            idempotency_key=f"reservation:{reservation.id}:reserve-debit",
            request_id=request_id,
            reason="provisional reservation debit",
        )
        account.available_balance -= amount
        await self._session.flush()
        return reservation

    async def reserve_unlimited(
        self,
        user_id: uuid.UUID,
        *,
        idempotency_key: str,
        payload_fingerprint: str,
        request_id: str | None = None,
    ) -> Reservation:
        """رزرو unlimited: بدون تغییر موجودی و بدون رویداد مالی (R-129/ADR-035).

        فقط با entitlement فعال Unlimited مجاز است (ADR-052).
        """
        from app.services.plans import PlanService

        if not await PlanService(self._session).is_unlimited_active(user_id):
            from app.core.errors import AppError as _AE

            raise _AE("unlimited_inactive", 403, "پلن Unlimited فعال نیست.")
        existing = await reservations_repo.get_by_idempotency_key(self._session, user_id, idempotency_key)
        if existing is not None:
            if existing.payload_fingerprint != payload_fingerprint:
                raise IDEMPOTENCY_CONFLICT
            return existing
        reservation = await reservations_repo.create(
            self._session,
            user_id=user_id,
            kind="unlimited",
            amount=0,
            idempotency_key=idempotency_key,
            payload_fingerprint=payload_fingerprint,
            request_id=request_id,
        )
        await self._session.flush()
        return reservation

    def _deadline(self, reservation: Reservation) -> datetime:
        return reservation.created_at + timedelta(minutes=RESERVATION_DEADLINE_MINUTES)

    async def settle(self, reservation_id: uuid.UUID) -> Reservation:
        """تسویه: بدون بدهی دوم و بدون رویداد ledger جدید؛ مصرف دقیقاً allocations همان رزرو.

        گیت OQ-027: فقط تا `created_at + 15 دقیقه` (مهلت ثابت و تغییرناپذیر).
        """
        reservation = await reservations_repo.get_by_id(self._session, reservation_id)
        if reservation is None:
            raise RESERVATION_NOT_FOUND
        if reservation.status == "settled":
            return reservation
        if self._now() >= self._deadline(reservation):
            raise RESERVATION_DEADLINE_PASSED
        won = await reservations_repo.try_transition_to_terminal(
            self._session, reservation.id, "settled", self._now()
        )
        if not won:
            raise INVALID_RESERVATION_STATE
        if reservation.kind == "credit":
            allocations = await ent_repo.list_allocations_for_reservation(self._session, reservation.id)
            for allocation in allocations:
                if allocation.status != "active":
                    continue
                grant = await ent_repo.get_grant_for_update(self._session, allocation.grant_id)
                if grant is None:
                    raise INVALID_RESERVATION_STATE
                # OQ-028: allocationهای موجود (قبل از تصمیم ادمین) تا مهلت اصلی مجازند؛
                # allocationهای پس از effective_at مجاز نیستند.
                # Policy: admin_void => never settle (even pre-void allocation).
                if grant.lifecycle_reason == "admin_void":
                    raise INVALID_RESERVATION_STATE
                # OQ-028: immediate_cancellation / approved_refund => grandfather only when
                # allocation predates effective void timestamp.
                if grant.lifecycle_reason in ent_repo.ADMIN_LIFECYCLE_REASONS and (
                    grant.lifecycle_reason not in ent_repo.SETTLE_GRANDFATHERED_REASONS
                    or grant.voided_at is None
                    or allocation.created_at >= grant.voided_at
                ):
                    raise INVALID_RESERVATION_STATE
                if not await ent_repo.consume_reserved(self._session, allocation.grant_id, allocation.allocated_amount):
                    raise INVALID_RESERVATION_STATE
                await ent_repo.mark_allocation_consumed(self._session, allocation.id, allocation.allocated_amount)
        await self._session.flush()
        return reservation

    async def release(
        self,
        reservation_id: uuid.UUID,
        *,
        reason: str = "manual",
        request_id: str | None = None,
    ) -> Reservation:
        """رهاسازی: گذار شرطی برنده + refund جبرانی + بازیابی projection."""
        reservation = await reservations_repo.get_by_id(self._session, reservation_id)
        if reservation is None:
            raise RESERVATION_NOT_FOUND
        if reservation.status == "released":
            return reservation
        won = await reservations_repo.try_transition_to_terminal(
            self._session, reservation.id, "released", self._now()
        )
        if not won:
            raise INVALID_RESERVATION_STATE
        if reservation.kind == "credit":
            account = await accounts_repo.get_for_update(self._session, reservation.user_id)
            allocations = await ent_repo.list_allocations_for_reservation(self._session, reservation.id)
            if not allocations and await ent_repo.count_grants(self._session, reservation.user_id) > 0:
                # رکورد grant‌دار بدون allocation = حالت خطا؛ مستقیماً به مسیر legacy نمی‌رود.
                raise INVALID_RESERVATION_STATE
            if not allocations:
                # رزرو legacy (پیش از 0013، بدون allocation): بازگشت کامل تاریخی
                await ledger_repo.create(
                    self._session,
                    user_id=reservation.user_id,
                    reservation_id=reservation.id,
                    kind="refund",
                    amount=reservation.amount,
                    idempotency_key=f"reservation:{reservation.id}:release-refund",
                    request_id=request_id,
                    reason=reason,
                )
                account.available_balance += reservation.amount
                await self._session.flush()
                return reservation
            restored_total = 0
            for allocation in allocations:
                if allocation.status != "active":
                    continue
                grant = await ent_repo.get_grant_for_update(self._session, allocation.grant_id)
                grant_valid = (
                    grant is not None
                    and grant.remaining_amount > 0
                    and grant.lifecycle_reason is None
                    and (grant.expires_at is None or grant.expires_at > self._now())
                )
                if grant_valid:
                    if await ent_repo.restore_reserved(self._session, allocation.grant_id, allocation.allocated_amount):
                        await ent_repo.mark_allocation_released(self._session, allocation.id, allocation.allocated_amount)
                        restored_total += allocation.allocated_amount
                else:
                    # منبع باطل/منقضی: بدون بازگشت (OQ: settle در جریان پس از انقضا)
                    await ent_repo.decrease_reserved(self._session, allocation.grant_id, allocation.allocated_amount)
                    await ent_repo.mark_allocation_voided(self._session, allocation.id, allocation.allocated_amount)
            if restored_total > 0:
                await ledger_repo.create(
                    self._session,
                    user_id=reservation.user_id,
                    reservation_id=reservation.id,
                    kind="refund",
                    amount=restored_total,
                    idempotency_key=f"reservation:{reservation.id}:release-refund",
                    request_id=request_id,
                    reason=reason,
                )
                account.available_balance += restored_total
        await self._session.flush()
        return reservation

    async def expire_reservation_deadlines(
        self,
        *,
        batch_limit: int = 200,
        user_id: uuid.UUID | None = None,
    ) -> int:
        """رهاسازی رزروهای pendingِ عبورکرده از مهلت ۱۵ دقیقه (OQ-027).

        همان مسیر release (منبع‌محور) را دنبال می‌کند؛ idempotent.
        """
        if batch_limit < 1:
            raise AppError("invalid_batch_limit", 422, "سقف دسته نامعتبر است.")
        deadline = self._now() - timedelta(minutes=RESERVATION_DEADLINE_MINUTES)
        overdue = await reservations_repo.list_pending_overdue(self._session, deadline, batch_limit, user_id)
        released = 0
        for reservation in overdue:
            try:
                await self.release(reservation.id, reason="reservation_deadline")
                released += 1
            except AppError:
                continue
        return released

    async def reconcile_stale(
        self,
        *,
        batch_limit: int,
        user_id: uuid.UUID | None = None,
        older_than: datetime | None = None,
        request_id: str | None = None,
    ) -> int:
        """رهاسازی امن رزروهای stale؛ فقط اگر هنوز pending باشند و گذار برنده شود.

        batch_limit الزامی و مثبت است تا فراخوانی عملیاتی ناخواسته بدون کران اجرا نشود.
        user_id اختیاری است؛ اگر داده شود فقط رزروهای همان کاربر بررسی می‌شوند (برای
        هدف‌گیری و تست‌های ایزوله)؛ پیش‌فرض همهٔ کاربران است.
        """
        if batch_limit < 1:
            raise AppError("invalid_batch_limit", 422, "سقف دستهٔ reconcile باید مثبت باشد.")
        cutoff = older_than or (self._now() - timedelta(minutes=self._settings.reservation_stale_minutes))
        stale = await reservations_repo.list_stale_pending(self._session, user_id, cutoff, batch_limit)
        released = 0
        for reservation in stale:
            try:
                await self.release(reservation.id, reason="stale_reconcile", request_id=request_id)
                released += 1
            except AppError:
                continue
        return released
