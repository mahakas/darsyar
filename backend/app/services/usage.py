"""سرویس ثبت رویداد مصرف؛ idempotent و مالکیت‌محور (Slice C-1)."""

import hashlib
import json
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.usage_event import UsageEvent
from app.repositories import reservations as reservations_repo
from app.repositories import usage_events as usage_repo

USAGE_EVENT_CONFLICT = AppError("usage_event_conflict", 409, "کلید رویداد با بار متفاوت استفاده شده است.")
RESERVATION_OWNERSHIP_MISMATCH = AppError("reservation_ownership_mismatch", 409, "رزرو متعلق به کاربر نیست.")
INVALID_TOKEN_COUNT = AppError("invalid_token_count", 422, "تعداد توکن نمی‌تواند منفی باشد.")


def canonical_usage_fingerprint(
    *,
    user_id: uuid.UUID,
    event_key: str,
    kind: str,
    token_count: int,
    estimated: bool,
    reservation_id: uuid.UUID | None,
) -> str:
    """fingerprint پایدار از فیلدهای مؤثر تغییرناپذیر رویداد."""
    canonical = json.dumps(
        {
            "user_id": str(user_id),
            "event_key": event_key,
            "kind": kind,
            "token_count": token_count,
            "estimated": bool(estimated),
            "reservation_id": str(reservation_id) if reservation_id else None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class UsageService:
    """ثبت داخلی رویداد مصرف؛ caller مورداعتماد event_key پایدار ارائه می‌دهد."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_event(
        self,
        *,
        user_id: uuid.UUID,
        event_key: str,
        kind: str,
        token_count: int,
        estimated: bool = False,
        reservation_id: uuid.UUID | None = None,
    ) -> UsageEvent:
        if not event_key.strip():
            raise AppError("invalid_event_key", 422, "کلید رویداد نامعتبر است.")
        if token_count < 0:
            raise INVALID_TOKEN_COUNT

        if reservation_id is not None:
            reservation = await reservations_repo.get_by_id(self._session, reservation_id)
            if reservation is None or reservation.user_id != user_id:
                raise RESERVATION_OWNERSHIP_MISMATCH

        fingerprint = canonical_usage_fingerprint(
            user_id=user_id,
            event_key=event_key,
            kind=kind,
            token_count=token_count,
            estimated=estimated,
            reservation_id=reservation_id,
        )

        existing = await usage_repo.get_by_key(self._session, user_id, event_key)
        if existing is not None:
            if existing.payload_fingerprint != fingerprint:
                raise USAGE_EVENT_CONFLICT
            return existing

        try:
            return await usage_repo.create(
                self._session,
                user_id=user_id,
                event_key=event_key,
                kind=kind,
                token_count=token_count,
                estimated=estimated,
                payload_fingerprint=fingerprint,
                reservation_id=reservation_id,
            )
        except IntegrityError:
            await self._session.rollback()
            existing = await usage_repo.get_by_key(self._session, user_id, event_key)
            if existing is not None and existing.payload_fingerprint == fingerprint:
                return existing
            raise USAGE_EVENT_CONFLICT from None
