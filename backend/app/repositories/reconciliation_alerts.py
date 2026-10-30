"""دسترسی دادهٔ هشدارهای تطبیق؛ dedupe فعال با قید جزئی و lifecycle حفظ‌شونده."""

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult as _CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reconciliation_alert import ReconciliationAlert

CursorResult = _CursorResult[object]

ACTIVE_WHERE = ReconciliationAlert.resolved_at.is_(None)


async def upsert_active(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    alert_type: str,
    severity: str,
    context: dict[str, object],
    alert_hash: str,
    now: datetime,
) -> ReconciliationAlert:
    """درج هشدار فعال یا به‌روزرسانی همان فعال من (occurrences/last_seen_at/context)."""
    statement = (
        insert(ReconciliationAlert)
        .values(
            user_id=user_id,
            alert_type=alert_type,
            severity=severity,
            context=context,
            alert_hash=alert_hash,
            occurrences=1,
            last_seen_at=now,
            created_at=now,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "alert_type", "alert_hash"],
            index_where=ACTIVE_WHERE,
            set_={
                "occurrences": ReconciliationAlert.occurrences + 1,
                "last_seen_at": now,
                "context": context,
            },
        )
        .returning(ReconciliationAlert)
    )
    result = await session.execute(statement)
    return result.scalar_one()


async def resolve_active(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    alert_type: str,
    now: datetime,
) -> int:
    """حل هشدارهای فعال همان نوع/کاربر؛ تاریخچه حذف نمی‌شود."""
    result = await session.execute(
        update(ReconciliationAlert)
        .where(
            ReconciliationAlert.user_id == user_id,
            ReconciliationAlert.alert_type == alert_type,
            ACTIVE_WHERE,
        )
        .values(resolved_at=now)
    )
    return cast(CursorResult, result).rowcount
