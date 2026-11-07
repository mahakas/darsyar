"""دسترسی دادهٔ plan entitlements، credit grants، cancellation و refund (ADR-052)."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult as _CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cancellation_request import CancellationRequest
from app.models.credit_grant import CreditGrant
from app.models.plan_entitlement import PlanEntitlement
from app.models.refund_record import RefundRecord
from app.models.reservation_allocation import ReservationAllocation

CursorResult = _CursorResult[object]

ENT_ACTIVE = "active"
ENT_EXPIRED = "expired"
ENT_CANCELLED = "cancelled"

CANCEL_PENDING = "pending"
CANCEL_WITHDRAWN = "withdrawn"
CANCEL_APPROVED = "approved"
CANCEL_REJECTED = "rejected"

REFUND_REQUESTED = "requested"
REFUND_APPROVED = "approved"
REFUND_REJECTED = "rejected"
REFUND_COMPLETED = "completed"


# ---------------------------------------------------------------- entitlements

async def get_active_entitlement(
    session: AsyncSession, user_id: uuid.UUID, product_id: str
) -> PlanEntitlement | None:
    result = await session.execute(
        select(PlanEntitlement).where(
            PlanEntitlement.user_id == user_id,
            PlanEntitlement.product_id == product_id,
            PlanEntitlement.status == ENT_ACTIVE,
        )
    )
    return result.scalar_one_or_none()


async def list_active_credit_entitlements(session: AsyncSession, user_id: uuid.UUID) -> Sequence[PlanEntitlement]:
    result = await session.execute(
        select(PlanEntitlement).where(
            PlanEntitlement.user_id == user_id,
            PlanEntitlement.status == ENT_ACTIVE,
            PlanEntitlement.plan_type == "credit",
        ).order_by(PlanEntitlement.expires_at.asc())
    )
    return result.scalars().all()


async def create_entitlement(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    product_id: str,
    plan_type: str,
    activated_at: datetime,
    expires_at: datetime,
    granted_credits: int,
    payment_id: uuid.UUID,
    snapshot: dict[str, object],
) -> PlanEntitlement:
    entitlement = PlanEntitlement(
        user_id=user_id,
        product_id=product_id,
        plan_type=plan_type,
        status=ENT_ACTIVE,
        activated_at=activated_at,
        expires_at=expires_at,
        granted_credits=granted_credits,
        remaining_credits=granted_credits,
        payment_id=payment_id,
        snapshot=snapshot,
    )
    session.add(entitlement)
    await session.flush()
    return entitlement


async def extend_entitlement_expiry(session: AsyncSession, entitlement_id: uuid.UUID, expires_at: datetime) -> bool:
    result = await session.execute(
        update(PlanEntitlement)
        .where(PlanEntitlement.id == entitlement_id, PlanEntitlement.status == ENT_ACTIVE)
        .values(expires_at=expires_at)
    )
    return cast(CursorResult, result).rowcount == 1


async def add_credits(session: AsyncSession, entitlement_id: uuid.UUID, amount: int) -> bool:
    result = await session.execute(
        update(PlanEntitlement)
        .where(PlanEntitlement.id == entitlement_id, PlanEntitlement.status == ENT_ACTIVE)
        .values(granted_credits=PlanEntitlement.granted_credits + amount, remaining_credits=PlanEntitlement.remaining_credits + amount)
    )
    return cast(CursorResult, result).rowcount == 1


async def mark_expired(session: AsyncSession, entitlement_id: uuid.UUID, now: datetime) -> bool:
    result = await session.execute(
        update(PlanEntitlement)
        .where(PlanEntitlement.id == entitlement_id, PlanEntitlement.status == ENT_ACTIVE)
        .values(status=ENT_EXPIRED, remaining_credits=0)
    )
    return cast(CursorResult, result).rowcount == 1


async def mark_cancelled(session: AsyncSession, entitlement_id: uuid.UUID, *, by: uuid.UUID, reason: str, now: datetime) -> bool:
    result = await session.execute(
        update(PlanEntitlement)
        .where(PlanEntitlement.id == entitlement_id, PlanEntitlement.status == ENT_ACTIVE)
        .values(status=ENT_CANCELLED, cancelled_at=now, cancelled_by=by, cancellation_reason=reason, remaining_credits=0)
    )
    return cast(CursorResult, result).rowcount == 1


async def list_expired_active(
    session: AsyncSession, now: datetime, limit: int, user_id: uuid.UUID | None = None
) -> Sequence[PlanEntitlement]:
    statement = select(PlanEntitlement).where(
        PlanEntitlement.status == ENT_ACTIVE, PlanEntitlement.expires_at < now
    )
    if user_id is not None:
        statement = statement.where(PlanEntitlement.user_id == user_id)
    statement = statement.order_by(PlanEntitlement.expires_at.asc()).limit(limit)
    result = await session.execute(statement)
    return result.scalars().all()


# ------------------------------------------------------------------ grants

async def create_grant(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    entitlement_id: uuid.UUID | None,
    kind: str,
    amount: int,
    expires_at: datetime | None,
    payment_id: uuid.UUID | None,
) -> CreditGrant:
    grant = CreditGrant(
        user_id=user_id,
        entitlement_id=entitlement_id,
        kind=kind,
        original_amount=amount,
        remaining_amount=amount,
        expires_at=expires_at,
        payment_id=payment_id,
    )
    session.add(grant)
    await session.flush()
    return grant


async def list_eligible_grants(
    session: AsyncSession, user_id: uuid.UUID, now: datetime, *, exclude_reserved: bool = False
) -> Sequence[CreditGrant]:
    """EFF (D-01): expires_at ASC NULLS LAST ← created_at ASC ← id ASC.

    در تخصیص، grantهای با `reserved_amount == remaining_amount` (کاملاً رزروشده)
    واجد شرایط نیستند.
    """
    statement = select(CreditGrant).where(
        CreditGrant.user_id == user_id,
        CreditGrant.remaining_amount > 0,
        CreditGrant.lifecycle_reason.is_(None),
        (CreditGrant.expires_at.is_(None)) | (CreditGrant.expires_at > now),
    )
    if exclude_reserved:
        statement = statement.where(CreditGrant.reserved_amount < CreditGrant.remaining_amount)
    statement = statement.order_by(
        CreditGrant.expires_at.asc().nulls_last(),
        CreditGrant.created_at.asc(),
        CreditGrant.id.asc(),
    )
    result = await session.execute(statement)
    return result.scalars().all()


async def get_grant_for_update(session: AsyncSession, grant_id: uuid.UUID) -> CreditGrant | None:
    result = await session.execute(select(CreditGrant).where(CreditGrant.id == grant_id).with_for_update())
    return result.scalar_one_or_none()


async def lock_grants_for_lifecycle(
    session: AsyncSession, entitlement_id: uuid.UUID
) -> Sequence[CreditGrant]:
    """Grantهای این entitlement که هنوز باطل نشده‌اند را با ترتیب قفل قطعی قفل می‌کند.

    ترتیب `expires_at → created_at → id` دقیقاً همان ترتیب EFF است که `reserve_credit`
    برای قفل grantها استفاده می‌کند؛ بنابراین هم‌ترتیب و بدون کلاس deadlock جدید است.
    محاسبهٔ بخش غیررزروشده زیر همین قفل انجام می‌شود تا یک رزرو هم‌زمان نتواند بین
    محاسبه و اعمال، `reserved_amount` را تغییر دهد (race-safe).
    """
    result = await session.execute(
        select(CreditGrant)
        .where(
            CreditGrant.entitlement_id == entitlement_id,
            CreditGrant.lifecycle_reason.is_(None),
        )
        .order_by(
            CreditGrant.expires_at.asc().nulls_last(),
            CreditGrant.created_at.asc(),
            CreditGrant.id.asc(),
        )
        .with_for_update()
    )
    return result.scalars().all()


async def increase_reserved(session: AsyncSession, grant_id: uuid.UUID, amount: int) -> bool:
    result = await session.execute(
        update(CreditGrant)
        .where(CreditGrant.id == grant_id, CreditGrant.remaining_amount - CreditGrant.reserved_amount >= amount)
        .values(reserved_amount=CreditGrant.reserved_amount + amount)
    )
    return cast(CursorResult, result).rowcount == 1


async def decrease_reserved(session: AsyncSession, grant_id: uuid.UUID, amount: int) -> bool:
    result = await session.execute(
        update(CreditGrant)
        .where(CreditGrant.id == grant_id, CreditGrant.reserved_amount >= amount)
        .values(reserved_amount=CreditGrant.reserved_amount - amount)
    )
    return cast(CursorResult, result).rowcount == 1


async def consume_reserved(session: AsyncSession, grant_id: uuid.UUID, amount: int) -> bool:
    """settle: reserved→consumed (remaining کاهش می‌یابد)."""
    result = await session.execute(
        update(CreditGrant)
        .where(CreditGrant.id == grant_id, CreditGrant.reserved_amount >= amount, CreditGrant.remaining_amount >= amount)
        .values(
            reserved_amount=CreditGrant.reserved_amount - amount,
            remaining_amount=CreditGrant.remaining_amount - amount,
        )
    )
    return cast(CursorResult, result).rowcount == 1


async def restore_reserved(session: AsyncSession, grant_id: uuid.UUID, amount: int) -> bool:
    """release به منبع معتبر: فقط ادعای reserved آزاد می‌شود (remaining تغییر نمی‌کند؛
    رزرو هرگز remaining را کاهش نمی‌دهد — فقط reserved را افزایش می‌دهد)."""
    result = await session.execute(
        update(CreditGrant)
        .where(CreditGrant.id == grant_id, CreditGrant.reserved_amount >= amount)
        .values(reserved_amount=CreditGrant.reserved_amount - amount)
    )
    return cast(CursorResult, result).rowcount == 1


async def create_allocation(
    session: AsyncSession,
    *,
    reservation_id: uuid.UUID,
    grant_id: uuid.UUID,
    amount: int,
) -> None:
    session.add(ReservationAllocation(reservation_id=reservation_id, grant_id=grant_id, allocated_amount=amount))
    await session.flush()


async def list_allocations_for_reservation(
    session: AsyncSession, reservation_id: uuid.UUID
) -> Sequence[ReservationAllocation]:
    result = await session.execute(
        select(ReservationAllocation).where(ReservationAllocation.reservation_id == reservation_id)
    )
    return result.scalars().all()


async def mark_allocation_consumed(session: AsyncSession, allocation_id: uuid.UUID, amount: int) -> bool:
    result = await session.execute(
        update(ReservationAllocation)
        .where(
            ReservationAllocation.id == allocation_id,
            ReservationAllocation.status == "active",
            ReservationAllocation.allocated_amount - ReservationAllocation.consumed_amount >= amount,
        )
        .values(consumed_amount=ReservationAllocation.consumed_amount + amount, status="consumed")
    )
    return cast(CursorResult, result).rowcount == 1


async def mark_allocation_released(session: AsyncSession, allocation_id: uuid.UUID, amount: int) -> bool:
    result = await session.execute(
        update(ReservationAllocation)
        .where(
            ReservationAllocation.id == allocation_id,
            ReservationAllocation.status == "active",
            ReservationAllocation.allocated_amount - ReservationAllocation.released_amount >= amount,
        )
        .values(released_amount=ReservationAllocation.released_amount + amount, status="released")
    )
    return cast(CursorResult, result).rowcount == 1


async def mark_allocation_voided(session: AsyncSession, allocation_id: uuid.UUID, amount: int) -> bool:
    result = await session.execute(
        update(ReservationAllocation)
        .where(
            ReservationAllocation.id == allocation_id,
            ReservationAllocation.status == "active",
            ReservationAllocation.allocated_amount - ReservationAllocation.voided_amount >= amount,
        )
        .values(voided_amount=ReservationAllocation.voided_amount + amount, status="voided")
    )
    return cast(CursorResult, result).rowcount == 1


async def consume_grant(session: AsyncSession, grant_id: uuid.UUID, amount: int) -> bool:
    result = await session.execute(
        update(CreditGrant)
        .where(CreditGrant.id == grant_id, CreditGrant.remaining_amount >= amount)
        .values(remaining_amount=CreditGrant.remaining_amount - amount)
    )
    return cast(CursorResult, result).rowcount == 1


LIFECYCLE_REASONS = ("natural_expiry", "immediate_cancellation", "approved_refund", "admin_void")
ADMIN_LIFECYCLE_REASONS = ("immediate_cancellation", "approved_refund", "admin_void")
# دلایل مجاز برای گرندفادر settle (OQ-028): فقط لغو/refund؛ admin_void هرگز مجاز نیست.
SETTLE_GRANDFATHERED_REASONS = ("immediate_cancellation", "approved_refund")


async def void_all_grants_of_entitlement(
    session: AsyncSession,
    entitlement_id: uuid.UUID,
    *,
    reason: str = "natural_expiry",
    effective_at: datetime | None = None,
    now: datetime | None = None,
) -> int:
    """مهر غیرمخرب «غیرفعال» برای grantهای این entitlement با **دلیل صریح**.

    - فقط بخش غیررزروشده (remaining = reserved) باطل می‌شود → ناوردان CHECK حفظ می‌شود.
    - `lifecycle_reason`/`voided_at` ثبت می‌شود تا OQ-027 (طقضای طبیعی) از
      OQ-028 (لغو فوری/refund) متمایز بماند.
    """
    if reason not in LIFECYCLE_REASONS:
        raise ValueError(f"unknown lifecycle reason: {reason}")
    moment = now or datetime.now(UTC)
    result = await session.execute(
        update(CreditGrant)
        .where(
            CreditGrant.entitlement_id == entitlement_id,
            CreditGrant.remaining_amount > CreditGrant.reserved_amount,
        )
        .values(
            remaining_amount=CreditGrant.reserved_amount,
            lifecycle_reason=reason,
            voided_at=effective_at or moment,
        )
    )
    # grantهای بدون بخش غیررزروشده نیز باید دلیل/زمان بگیرند (فقط در صورت عدم وجود).
    await session.execute(
        update(CreditGrant)
        .where(
            CreditGrant.entitlement_id == entitlement_id,
            CreditGrant.lifecycle_reason.is_(None),
        )
        .values(lifecycle_reason=reason, voided_at=effective_at or moment)
    )
    return cast(CursorResult, result).rowcount


async def count_grants(session: AsyncSession, user_id: uuid.UUID) -> int:
    from sqlalchemy import func

    result = await session.execute(
        select(func.count()).select_from(CreditGrant).where(CreditGrant.user_id == user_id)
    )
    return int(result.scalar_one())


# ------------------------------------------------------------- cancellation

async def create_cancellation_request(
    session: AsyncSession, *, user_id: uuid.UUID, entitlement_id: uuid.UUID
) -> CancellationRequest:
    request = CancellationRequest(user_id=user_id, entitlement_id=entitlement_id, status=CANCEL_PENDING)
    session.add(request)
    await session.flush()
    return request


async def get_pending_cancellation(
    session: AsyncSession, user_id: uuid.UUID, entitlement_id: uuid.UUID
) -> CancellationRequest | None:
    result = await session.execute(
        select(CancellationRequest).where(
            CancellationRequest.user_id == user_id,
            CancellationRequest.entitlement_id == entitlement_id,
            CancellationRequest.status == CANCEL_PENDING,
        )
    )
    return result.scalar_one_or_none()


async def withdraw_cancellation(session: AsyncSession, request_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await session.execute(
        update(CancellationRequest)
        .where(
            CancellationRequest.id == request_id,
            CancellationRequest.user_id == user_id,
            CancellationRequest.status == CANCEL_PENDING,
        )
        .values(status=CANCEL_WITHDRAWN)
    )
    return cast(CursorResult, result).rowcount == 1


async def decide_cancellation(
    session: AsyncSession,
    request_id: uuid.UUID,
    *,
    approve: bool,
    decided_by: uuid.UUID,
    reason: str,
    now: datetime,
    mode: str | None = None,
) -> bool:
    target = CANCEL_APPROVED if approve else CANCEL_REJECTED
    statement = (
        update(CancellationRequest)
        .where(
            CancellationRequest.id == request_id,
            CancellationRequest.status == CANCEL_PENDING,
        )
        .values(status=target, decided_at=now, decided_by=decided_by, decision_reason=reason)
    )
    if mode is not None:
        statement = statement.values(mode=mode)
    result = await session.execute(statement)
    return cast(CursorResult, result).rowcount == 1


# ---------------------------------------------------------------- refund

async def create_refund_request(
    session: AsyncSession,
    *,
    payment_id: uuid.UUID,
    entitlement_id: uuid.UUID | None,
    requested_amount: int,
    reason: str,
) -> RefundRecord:
    record = RefundRecord(
        payment_id=payment_id,
        entitlement_id=entitlement_id,
        requested_amount=requested_amount,
        reason=reason,
        status=REFUND_REQUESTED,
    )
    session.add(record)
    await session.flush()
    return record


async def get_refund_by_id(session: AsyncSession, refund_id: uuid.UUID) -> RefundRecord | None:
    result = await session.execute(select(RefundRecord).where(RefundRecord.id == refund_id))
    return result.scalar_one_or_none()


async def decide_refund(
    session: AsyncSession,
    refund_id: uuid.UUID,
    *,
    approve: bool,
    decided_by: uuid.UUID,
    reason: str,
    now: datetime,
    approved_amount: int | None = None,
    credit_voided: int = 0,
) -> bool:
    status = REFUND_APPROVED if approve else REFUND_REJECTED
    result = await session.execute(
        update(RefundRecord)
        .where(RefundRecord.id == refund_id, RefundRecord.status == REFUND_REQUESTED)
        .values(
            status=status,
            decision_at=now,
            decision_by=decided_by,
            reason=RefundRecord.reason + " | " + reason,
            approved_amount=approved_amount,
            credit_voided=credit_voided,
        )
    )
    return cast(CursorResult, result).rowcount == 1
