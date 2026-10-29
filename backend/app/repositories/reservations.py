"""دسترسی دادهٔ رزروها؛ گذار شرطی pending با راستی‌آزمایی «دقیقاً یک سطر»."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult as _CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation

CursorResult = _CursorResult[object]

TERMINAL_STATUSES = ("settled", "released")


async def get_by_id(session: AsyncSession, reservation_id: uuid.UUID) -> Reservation | None:
    result = await session.execute(select(Reservation).where(Reservation.id == reservation_id))
    return result.scalar_one_or_none()


async def get_by_idempotency_key(
    session: AsyncSession, user_id: uuid.UUID, key: str
) -> Reservation | None:
    result = await session.execute(
        select(Reservation).where(
            Reservation.user_id == user_id,
            Reservation.idempotency_key == key,
        )
    )
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: str,
    amount: int,
    idempotency_key: str,
    payload_fingerprint: str,
    request_id: str | None = None,
) -> Reservation:
    reservation = Reservation(
        user_id=user_id,
        kind=kind,
        amount=amount,
        status="pending",
        idempotency_key=idempotency_key,
        payload_fingerprint=payload_fingerprint,
        request_id=request_id,
    )
    session.add(reservation)
    await session.flush()
    return reservation


async def try_transition_to_terminal(
    session: AsyncSession,
    reservation_id: uuid.UUID,
    target: str,
    now: datetime,
) -> bool:
    """update شرطی فقط از pending؛ دقیقاً یک سطر باید تغییر کند."""
    timestamp_column = "settled_at" if target == "settled" else "released_at"
    result = await session.execute(
        update(Reservation)
        .where(Reservation.id == reservation_id, Reservation.status == "pending")
        .values(status=target, **{timestamp_column: now})
    )
    return cast(CursorResult, result).rowcount == 1


async def list_stale_pending(
    session: AsyncSession,
    user_id: uuid.UUID | None,
    older_than: datetime,
    limit: int | None,
) -> Sequence[Reservation]:
    statement = select(Reservation).where(Reservation.status == "pending", Reservation.created_at < older_than)
    if user_id is not None:
        statement = statement.where(Reservation.user_id == user_id)
    statement = statement.order_by(Reservation.created_at.asc())
    if limit is not None:
        statement = statement.limit(limit)
    result = await session.execute(statement)
    return result.scalars().all()
