"""قرارداد rate limit؛ backend واقعی Redis در فاز هویت اضافه می‌شود."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """سقف و پنجرهٔ یک ریت‌لیمیت از تنظیمات را نگه می‌دارد."""

    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.limit <= 0 or self.window_seconds <= 0:
            raise ValueError("Rate limit and window must be positive")
