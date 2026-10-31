"""پایهٔ Fair-Use (ADR-040/050): دورهٔ Gregorian، شمارش، پرچم و حل ادمین."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.abuse_flag import AbuseFlag
from app.repositories import abuse_flags as flags_repo
from app.repositories import usage_events as usage_repo
from app.repositories import users as users_repo

PERIOD_TIMEZONE = ZoneInfo("Asia/Tehran")
COUNTABLE_EVENT_KIND = "message_usage"
FLAG_STATUS_ACTIVE = "active"

FLAG_NOT_FOUND = AppError("abuse_flag_not_found", 404, "پرچم یافت نشد.")
FLAG_ALREADY_RESOLVED = AppError("abuse_flag_already_resolved", 409, "پرچم قبلاً حل شده است.")
ADMIN_REQUIRED = AppError("admin_required", 403, "این عملیات فقط برای ادمین مجاز است.")
RESOLUTION_REASON_REQUIRED = AppError("resolution_reason_required", 422, "دلیل حل پرچم الزامی است.")


@dataclass(frozen=True, slots=True)
class Period:
    key: str
    start_utc: datetime
    end_utc: datetime


def month_period(at: datetime) -> Period:
    """بازهٔ ماهانهٔ Gregorian در Asia/Tehran: [نیمه‌شب محلی اول ماه، نیمه‌شب محلی اول ماه بعد).

    مرزها به UTC تبدیل می‌شوند؛ هیچ datetime ساده‌ای تولید نمی‌شود.
    """
    if at.tzinfo is None:
        raise AppError("invalid_period", 422, "زمان باید timezone-aware باشد.")
    local = at.astimezone(PERIOD_TIMEZONE)
    start_local = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start_local.month == 12:
        end_local = start_local.replace(year=start_local.year + 1, month=1)
    else:
        end_local = start_local.replace(month=start_local.month + 1)
    key = start_local.strftime("%Y-%m")
    return Period(key=key, start_utc=start_local.astimezone(UTC), end_utc=end_local.astimezone(UTC))


class FairUseService:
    """سرویس Fair-Use؛ بدون بلاک/کسر/پلن؛ بدون یکپارچه‌سازی چت."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    @property
    def threshold(self) -> int:
        return self._settings.fair_use_monthly_message_limit

    async def count_events(
        self,
        user_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> int:
        """سازگار با API فاز C-1: شمارش خام در بازهٔ صریح."""
        if start.tzinfo is None or end.tzinfo is None:
            raise AppError("invalid_range", 422, "بازهٔ زمانی باید timezone-aware باشد.")
        if start >= end:
            raise AppError("invalid_range", 422, "شروع بازه باید کوچک‌تر از پایان باشد.")
        return await usage_repo.count_in_range(self._session, user_id, start, end)

    async def count_for_period(self, user_id: uuid.UUID, period: Period) -> int:
        return await usage_repo.count_countable_in_range(
            self._session, user_id, period.start_utc, period.end_utc, kind=COUNTABLE_EVENT_KIND
        )

    async def detect_and_flag(self, user_id: uuid.UUID, *, now: datetime | None = None) -> AbuseFlag | None:
        """شمارش و ایجاد پرچم فقط وقتی count > threshold؛ idempotent و هم‌زمانی-ایمن.

        پرچم حل‌شدهٔ همان دوره بازفعال نمی‌شود و فرادادهٔ آن تغییر نمی‌کند.
        """
        moment = now or datetime.now(UTC)
        period = month_period(moment)
        count = await self.count_for_period(user_id, period)
        if count <= self.threshold:
            return None
        return await flags_repo.create_if_absent(
            self._session,
            user_id=user_id,
            period_key=period.key,
            observed_count=count,
            threshold=self.threshold,
            now=moment,
        )

    async def resolve_flag(
        self,
        flag_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        reason: str,
        now: datetime | None = None,
    ) -> AbuseFlag:
        if not reason.strip():
            raise RESOLUTION_REASON_REQUIRED
        if len(reason) > 500:
            raise AppError("resolution_reason_too_long", 422, "دلیل بیش از حد طولانی است.")
        actor = await users_repo.get_by_id(self._session, actor_user_id)
        if actor is None or actor.role != "admin":
            raise ADMIN_REQUIRED
        flag = await flags_repo.get_by_id(self._session, flag_id)
        if flag is None:
            raise FLAG_NOT_FOUND
        won = await flags_repo.try_resolve(
            self._session,
            flag_id,
            resolved_by=actor_user_id,
            reason=reason.strip(),
            now=now or datetime.now(UTC),
        )
        if not won:
            raise FLAG_ALREADY_RESOLVED
        await self._session.flush()
        return flag
