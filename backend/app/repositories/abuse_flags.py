"""دسترسی دادهٔ پرچم‌های Fair-Use؛ درج اتمیک و گذار solution شرطی."""

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult as _CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.abuse_flag import AbuseFlag

CursorResult = _CursorResult[object]

STATUS_ACTIVE = "active"
STATUS_RESOLVED = "resolved"


async def get_by_id(session: AsyncSession, flag_id: uuid.UUID) -> AbuseFlag | None:
    result = await session.execute(select(AbuseFlag).where(AbuseFlag.id == flag_id))
    return result.scalar_one_or_none()


async def get_by_user_period(
    session: AsyncSession,
    user_id: uuid.UUID,
    period_key: str,
) -> AbuseFlag | None:
    result = await session.execute(
        select(AbuseFlag).where(AbuseFlag.user_id == user_id, AbuseFlag.period_key == period_key)
    )
    return result.scalar_one_or_none()


async def create_if_absent(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    period_key: str,
    observed_count: int,
    threshold: int,
    now: datetime,
) -> AbuseFlag:
    """درج اتمیک؛ اگر قبلاً وجود داشت (فعال یا حل‌شده) همان رکورد بازگردانده می‌شود.

    هرگز حالت حل‌شده را بازفعال نمی‌کند و metadata آن را تغییر نمی‌دهد.
    """
    statement = (
        insert(AbuseFlag)
        .values(
            user_id=user_id,
            period_key=period_key,
            observed_count=observed_count,
            threshold=threshold,
            status=STATUS_ACTIVE,
            created_at=now,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "period_key"])
        .returning(AbuseFlag)
    )
    result = await session.execute(statement)
    created = result.scalar_one_or_none()
    if created is not None:
        return created
    existing = await get_by_user_period(session, user_id, period_key)
    if existing is None:
        raise RuntimeError("abuse flag conflict handling failed to find existing row")
    return existing


async def try_resolve(
    session: AsyncSession,
    flag_id: uuid.UUID,
    *,
    resolved_by: uuid.UUID,
    reason: str,
    now: datetime,
) -> bool:
    """گذار شرطی active→resolved؛ فقط یک سطر باید تغییر کند."""
    result = await session.execute(
        update(AbuseFlag)
        .where(AbuseFlag.id == flag_id, AbuseFlag.status == STATUS_ACTIVE)
        .values(status=STATUS_RESOLVED, resolved_at=now, resolved_by=resolved_by, resolution_reason=reason)
    )
    return cast(CursorResult, result).rowcount == 1
