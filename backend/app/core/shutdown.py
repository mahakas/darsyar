"""حالت خاموشی تدریجی درون‌فرایندی (Slice F).

نگه‌داشتن state در-process برای چرخهٔ عمر درخواست‌های استریم؛ بدون ذخیرهٔ خارجی.
"""

import asyncio
from typing import Any


class ShutdownState:
    def __init__(self) -> None:
        self.draining = False
        self.active_streams: set[asyncio.Task[Any]] = set()
        # cleanupهای مالی که پس از مهلت cancel هنوز pending هستند؛ reference قوی نگه‌داشته
        # می‌شود تا DB engine پیش از تعیین تکلیف آن‌ها dispose نشود (fail-closed).
        self.pending_cleanups: set[asyncio.Task[Any]] = set()
        self.metrics_internal_only = True


SHUTDOWN_STATE = ShutdownState()
