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

import asyncio
from typing import Any

from uvicorn import Config, Server

from app.core.config import get_settings
from app.core.shutdown import SHUTDOWN_STATE


class DrainingServer(Server):
    def handle_exit(self, sig: int, frame: Any | None) -> None:
        SHUTDOWN_STATE.draining = True
        super().handle_exit(sig, frame)

    async def shutdown(self, sockets: list[Any] | None = None) -> None:
        """coordinate فعال‌سازی active streams پیش از shutdown عادی Uvicorn.

        ترتیب Uvicorn 0.54.0: بستن listeners → درخواست shutdown اتصال‌ها → انتظار
        تا timeout → لغو → lifespan.shutdown. این override ابتدا جریان‌های ثبت‌شده را
        هماهنگ می‌کند (تا grace منتظر؛ سپس لغو + انتظار برای aclose/cleanup مالی) و سپس
        shutdown پدر را اجرا می‌کند — به‌گونه‌ای که settled بستن اتصال‌ها، cleanup مالی
        واقع شده باشد.
        """
        SHUTDOWN_STATE.draining = True
        settings = get_settings()
        grace = settings.chat_stream_shutdown_grace_seconds

        # ۱) منتظر پایان جریان‌های ثبت‌شده تا مهلت باش
        if SHUTDOWN_STATE.active_streams:
            pending = set(SHUTDOWN_STATE.active_streams)
            await asyncio.wait(pending, timeout=grace)

        # ۲) باقی‌مانده‌ها را لغو کن و برای aclose/cleanup منتظر باش (bounded)
        still = [t for t in SHUTDOWN_STATE.active_streams if not t.done()]
        if still:
            for t in still:
                t.cancel()
            await asyncio.wait(set(still), timeout=grace)

        # ۳) shutdown استاندارد Uvicorn (اتصال/تسک/lifespan)
        await super().shutdown(sockets)


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
