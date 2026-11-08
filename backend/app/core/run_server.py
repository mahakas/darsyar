"""Runner حداقلی Uvicorn با Early Draining (فاز ۳).

در Uvicorn 0.54.0، ترتیب shutdown چنین است:
  1) بستن listeners
  2) درخواست shutdown اتصال‌ها
  3) انتظار برای درخواست‌ها/تسک‌ها تا timeout_graceful_shutdown
  4) لغو باقی‌مانده در صورت timeout
  5) lifespan.shutdown (drain برنامه) — دیر است.

برای اینکه `ShutdownState.draining` از لحظه دریافت SIGTERM فعال شود و readiness بلافاصله
false شود، `handle_exit` را به‌صورت حداقلی زیرکلاس می‌کنیم. این یک monkey-patch نیست؛
subclass رسمی و محدود از `uvicorn.Server` است.
"""

from __future__ import annotations

from typing import Any

from uvicorn import Config, Server

from app.core.config import get_settings
from app.core.shutdown import SHUTDOWN_STATE


class DrainingServer(Server):
    def handle_exit(self, sig: int, frame: Any | None) -> None:
        SHUTDOWN_STATE.draining = True
        super().handle_exit(sig, frame)


def main() -> None:
    settings = get_settings()
    # سیاست shutdown واحد: Uvicorn graceful timeout باید حداقل برابر grace برنامه + حاشیهٔ
    # cleanup باشد. با تنظیم CHAT_STREAM_SHUTDOWN_GRACE_SECONDS (مثلاً در CI) قابل کوتاه‌کردن
    # است و نیازی به انتظار ۴۵ ثانیه‌ای hardcoded نیست.
    graceful_timeout = max(settings.chat_stream_shutdown_grace_seconds + 10, 15)
    config = Config(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        timeout_graceful_shutdown=graceful_timeout,
        log_level="warning",
    )
    server = DrainingServer(config)
    server.run()


if __name__ == "__main__":
    main()
