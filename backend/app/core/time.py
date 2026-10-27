"""ابزارهای timezone-aware برای ذخیرهٔ UTC و محاسبهٔ دورهٔ محلی."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo("Asia/Tehran")


def utc_now() -> datetime:
    """زمان فعلی timezone-aware را با UTC برمی‌گرداند."""
    return datetime.now(UTC)


def tehran_now() -> datetime:
    """زمان فعلی را برای نمایش/محاسبهٔ دوره به منطقهٔ تهران تبدیل می‌کند."""
    return utc_now().astimezone(TEHRAN)
