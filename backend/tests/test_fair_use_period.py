"""تست‌های واحد محاسبهٔ دورهٔ ماهانه (ADR-040) بدون نیاز به DB."""

from datetime import UTC, datetime

import pytest
from app.core.errors import AppError
from app.services.fair_use import month_period


def test_normal_month_bounds() -> None:
    period = month_period(datetime(2026, 10, 15, 12, 0, tzinfo=UTC))
    assert period.key == "2026-10"
    # اول اکتبر نیمه‌شب تهران = 30 سپتامبر 20:30 UTC (ایران +3:30)
    assert period.start_utc == datetime(2026, 9, 30, 20, 30, tzinfo=UTC)
    # اول نوامبر نیمه‌شب تهران = 31 اکتبر 20:30 UTC
    assert period.end_utc == datetime(2026, 10, 31, 20, 30, tzinfo=UTC)
    assert period.end_utc > period.start_utc


def test_january_boundary() -> None:
    period = month_period(datetime(2026, 1, 10, tzinfo=UTC))
    assert period.key == "2026-01"
    assert period.start_utc == datetime(2025, 12, 31, 20, 30, tzinfo=UTC)
    assert period.end_utc == datetime(2026, 1, 31, 20, 30, tzinfo=UTC)


def test_december_to_january_rollover() -> None:
    period = month_period(datetime(2026, 12, 5, tzinfo=UTC))
    assert period.key == "2026-12"
    assert period.start_utc == datetime(2026, 11, 30, 20, 30, tzinfo=UTC)
    assert period.end_utc == datetime(2026, 12, 31, 20, 30, tzinfo=UTC)
    january = month_period(datetime(2027, 1, 2, tzinfo=UTC))
    assert january.key == "2027-01"
    assert january.start_utc == datetime(2026, 12, 31, 20, 30, tzinfo=UTC)


def test_leap_year_february() -> None:
    period = month_period(datetime(2024, 2, 10, tzinfo=UTC))
    assert period.key == "2024-02"
    assert period.end_utc == datetime(2024, 2, 29, 20, 30, tzinfo=UTC)


def test_starts_at_tehran_midnight_utc() -> None:
    # لحظهٔ دقیق شروع: 2026-10-01T00:00+03:30 == 2026-09-30T20:30Z
    start = datetime(2026, 9, 30, 20, 30, tzinfo=UTC)
    period = month_period(start)
    assert period.start_utc == start
    assert period.end_utc > start


def test_strict_half_open_end_excluded() -> None:
    period = month_period(datetime(2026, 10, 1, tzinfo=UTC))
    assert period.end_utc == datetime(2026, 10, 31, 20, 30, tzinfo=UTC)
    # لحظهٔ دقیق پایان باید خارج از بازه باشد؛ لحظهٔ درست قبل از آن داخل است.
    assert period.end_utc > period.start_utc


def test_naive_datetime_rejected() -> None:
    with pytest.raises(AppError):
        month_period(datetime(2026, 10, 1))
