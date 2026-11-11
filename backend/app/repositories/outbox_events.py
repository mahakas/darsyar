"""دسترسی دادهٔ outbox؛ claim/publish/fail با قفل ردیف.

قرارداد هم‌زمانی Slice 3: ادعای اتمیک در یک تراکنش کوتاه با
`FOR UPDATE SKIP LOCKED` انجام می‌شود تا دو publisher هم‌زمان سطر یکسانی را
پردازش نکنند. گذارهای وضعیت فقط روی رديف‌های واجدشرایط اعمال می‌شوند.
"""

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult as _CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox_event import OutboxEvent

CursorResult = _CursorResult[object]

ELIGIBLE_STATES = ("pending",)
CLAIMABLE_STATES = ("pending", "publishing")


async def claim_eligible_events(
    session: AsyncSession,
    *,
    limit: int,
    now: datetime,
) -> list[OutboxEvent]:
    """ادعای اتمیک رویدادهای واجدشرایط (pending و سررسیدشده).

    `FOR UPDATE SKIP LOCKED` تضمین می‌کند publisherهای هم‌زمان سطرهای قفل‌شده را
    رد می‌کنند؛ ترتیب پایدار `available_at`/`id` خروجی را قطعی می‌کند.
    """
    statement = (
        select(OutboxEvent)
        .where(
            OutboxEvent.publication_state.in_(ELIGIBLE_STATES),
            OutboxEvent.available_at <= now,
        )
        .order_by(OutboxEvent.available_at.asc(), OutboxEvent.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def mark_published(session: AsyncSession, event_id: uuid.UUID, now: datetime) -> bool:
    """ثبت انتشار موفق فقط پس از موفقیت enqueue."""
    result = await session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == event_id, OutboxEvent.publication_state.in_(CLAIMABLE_STATES))
        .values(
            publication_state="published",
            published_at=now,
            attempt_count=OutboxEvent.attempt_count + 1,
        )
    )
    return cast(CursorResult, result).rowcount == 1


async def record_transient_failure(
    session: AsyncSession,
    event_id: uuid.UUID,
    *,
    details: str,
) -> bool:
    """شکست گذرا (Redis در دسترس نیست یا خطای شبکه): رویداد واجدشرایط می‌ماند."""
    result = await session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == event_id, OutboxEvent.publication_state.in_(CLAIMABLE_STATES))
        .values(
            publication_state="pending",
            last_error_details=details,
            attempt_count=OutboxEvent.attempt_count + 1,
        )
    )
    return cast(CursorResult, result).rowcount == 1


async def record_permanent_failure(
    session: AsyncSession,
    event_id: uuid.UUID,
    *,
    details: str,
) -> bool:
    """شکست دائمی (قرارداد رویداد پشتیبانی‌نشده): وضعیت `failed`."""
    result = await session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == event_id, OutboxEvent.publication_state.in_(CLAIMABLE_STATES))
        .values(
            publication_state="failed",
            last_error_details=details,
            attempt_count=OutboxEvent.attempt_count + 1,
        )
    )
    return cast(CursorResult, result).rowcount == 1
