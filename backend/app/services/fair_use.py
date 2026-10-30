"""شمارش بازهٔ صریح رویدادهای مصرف؛ بدون قواعد تجاری (Slice C-1)."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.repositories import usage_events as usage_repo


class FairUseService:
    """فقط شمارش رویدادهای یکتا در بازهٔ [start, end)؛ بدون سقف/abuse."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_events(
        self,
        user_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> int:
        if start.tzinfo is None or end.tzinfo is None:
            raise AppError("invalid_range", 422, "بازهٔ زمانی باید timezone-aware باشد.")
        if start >= end:
            raise AppError("invalid_range", 422, "شروع بازه باید کوچک‌تر از پایان باشد.")
        return await usage_repo.count_in_range(self._session, user_id, start, end)
