"""دسترسی دادهٔ ledger append-only؛ فقط درج (R-125)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_ledger import CreditLedger


async def create(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: str,
    amount: int,
    idempotency_key: str,
    reservation_id: uuid.UUID | None = None,
    request_id: str | None = None,
    reason: str | None = None,
) -> CreditLedger:
    entry = CreditLedger(
        user_id=user_id,
        reservation_id=reservation_id,
        kind=kind,
        amount=amount,
        idempotency_key=idempotency_key,
        request_id=request_id,
        reason=reason,
    )
    session.add(entry)
    await session.flush()
    return entry


async def sum_balance_affecting(session: AsyncSession, user_id: uuid.UUID) -> int:
    """مجموع امضا‌شدهٔ رکوردهای مؤثر بر موجودی (spend منفی؛ grant/refund/adjust غیرصفر)."""
    result = await session.execute(
        select(CreditLedger.amount).where(
            CreditLedger.user_id == user_id,
            CreditLedger.kind != "unlimited_usage",
        )
    )
    return sum(int(row[0]) for row in result.all())
