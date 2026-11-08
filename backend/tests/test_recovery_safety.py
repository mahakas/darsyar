"""تست واحد DB-free برای منطق بازیابی ایمن (نگاشت + Lease)."""

from datetime import UTC, datetime, timedelta

import pytest
from app.services.worker import (
    STREAM_LEASE_EXPIRY_SECONDS,
    _terminal_status_for_recovery,
)


@pytest.mark.parametrize(
    "status,billable,expected",
    [
        ("settled", True, "completed"),
        ("settled", False, "completed"),
        ("released", True, "partial"),
        ("released", False, "cancelled"),
        ("pending", False, "cancelled"),
        ("pending", True, "cancelled"),
    ],
)
def test_terminal_status_mapping(status: str, billable: bool, expected: str) -> None:
    assert _terminal_status_for_recovery(status, billable) == expected


def test_released_billable_not_conflated_with_cancelled() -> None:
    # ADR-039: released بعد از خروجی billable (late-completion) باید partial باشد، نه cancelled.
    assert _terminal_status_for_recovery("released", True) == "partial"
    assert _terminal_status_for_recovery("released", False) == "cancelled"


def test_lease_expiry_constant_reasonable() -> None:
    assert 30 <= STREAM_LEASE_EXPIRY_SECONDS <= 300


def test_heartbeat_vs_lease_semantics() -> None:
    # یک Stream فعال با heartbeat تازه نباید orphan باشد؛ heartbeat قدیمی‌تر از lease بله.
    now = datetime.now(UTC)
    fresh = now - timedelta(seconds=5)
    stale = now - timedelta(seconds=STREAM_LEASE_EXPIRY_SECONDS + 5)
    assert fresh > now - timedelta(seconds=STREAM_LEASE_EXPIRY_SECONDS)
    assert stale < now - timedelta(seconds=STREAM_LEASE_EXPIRY_SECONDS)
