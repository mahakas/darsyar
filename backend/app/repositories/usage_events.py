"""دسترسی دادهٔ رویدادهای مصرف؛ فقط درج (append-only)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_event import UsageEvent


async def get_by_key(session: AsyncSession, user_id: uuid.UUID, event_key: str) -> UsageEvent | None:
    result = await session.execute(
        select(UsageEvent).where(UsageEvent.user_id == user_id, UsageEvent.event_key == event_key)
    )
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_key: str,
    kind: str,
    token_count: int,
    estimated: bool,
    payload_fingerprint: str,
    reservation_id: uuid.UUID | None = None,
) -> UsageEvent:
    event = UsageEvent(
        user_id=user_id,
        reservation_id=reservation_id,
        event_key=event_key,
        kind=kind,
        token_count=token_count,
        estimated=estimated,
        payload_fingerprint=payload_fingerprint,
    )
    session.add(event)
    await session.flush()
    return event


async def count_in_range(
    session: AsyncSession,
    user_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> int:
    result = await session.execute(
        select(func.count()).select_from(UsageEvent).where(
            UsageEvent.user_id == user_id,
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
    )
    return int(result.scalar_one())


async def count_countable_in_range(
    session: AsyncSession,
    user_id: uuid.UUID,
    start: datetime,
    end: datetime,
    *,
    kind: str = "message_usage",
) -> int:
    """شمارش فقط رویدادهای قابل‌شمارش (پاسخ دستیار) در بازهٔ نیمه‌باز.

    idempotency رویدادها با UNIQUE(user_id, event_key) از شمارش تکراری جلوگیری می‌کند.
    """
    result = await session.execute(
        select(func.count()).select_from(UsageEvent).where(
            UsageEvent.user_id == user_id,
            UsageEvent.kind == kind,
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
    )
    return int(result.scalar_one())
