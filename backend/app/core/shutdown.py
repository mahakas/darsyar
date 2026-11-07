"""حالت خاموشی تدریجی درون‌فرایندی (Slice F).

نگه‌داشتن state در-process برای چرخهٔ عمر درخواست‌های استریم؛ بدون ذخیرهٔ خارجی.
"""

import asyncio
from typing import Any


class ShutdownState:
    def __init__(self) -> None:
        self.draining = False
        self.active_streams: set[asyncio.Task[Any]] = set()
        self.metrics_internal_only = True


SHUTDOWN_STATE = ShutdownState()
