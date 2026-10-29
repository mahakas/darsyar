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
from app.repositories import reservations as reservations_repo

INSUFFICIENT_CREDIT = AppError("insufficient_credit", 409, "اعتبار کافی موجود نیست.")
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
        """رزرو unlimited: بدون تغییر موجودی و بدون رویداد مالی (R-129/ADR-035)."""
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

    async def settle(self, reservation_id: uuid.UUID) -> Reservation:
        """تسویه: بدون بدهی دوم و بدون رویداد ledger جدید."""
        reservation = await reservations_repo.get_by_id(self._session, reservation_id)
        if reservation is None:
            raise RESERVATION_NOT_FOUND
        if reservation.status == "settled":
            return reservation
        won = await reservations_repo.try_transition_to_terminal(
            self._session, reservation.id, "settled", self._now()
        )
        if not won:
            if reservation.status == "released":
                raise INVALID_RESERVATION_STATE
            raise INVALID_RESERVATION_STATE
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

    async def reconcile_stale(
        self,
        *,
        older_than: datetime | None = None,
        batch_limit: int | None = None,
        request_id: str | None = None,
    ) -> int:
        """رهاسازی امن رزروهای stale؛ فقط اگر هنوز pending باشند و گذار برنده شود."""
        cutoff = older_than or (self._now() - timedelta(minutes=self._settings.reservation_stale_minutes))
        stale = await reservations_repo.list_stale_pending(self._session, None, cutoff, batch_limit)
        released = 0
        for reservation in stale:
            try:
                await self.release(reservation.id, reason="stale_reconcile", request_id=request_id)
                released += 1
            except AppError:
                continue
        return released
