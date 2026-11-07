"""نقطهٔ ورود API زیرساختی درسیار؛ قابلیت‌های محصول در فازهای مربوطه اضافه می‌شوند."""

import asyncio
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from redis.asyncio import Redis
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.metrics import METRICS
from app.core.operations import router as operations_router
from app.core.shutdown import SHUTDOWN_STATE
from app.db.session import engine, verify_schema_revision

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._:-]{1,100}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """منابع process را ایجاد و در پایان آزاد می‌کند؛ migration اجرا نمی‌شود.

    خاموشی تدریجی: علامت‌گذاری draining، غیرفعال‌کردن readiness، توقف پذیرش جریان‌های
    جدید، انتظار تا مهلت برای جریان‌های فعال، و سپس لغو کنترل‌شده + پاک‌سازی مالی
    (بقایای reserve در `finally` سرویس چت به‌صورت idempotent settle/release می‌شوند).
    """
    app.state.redis = Redis.from_url(
        settings.redis_url, decode_responses=True, max_connections=settings.redis_max_connections,
        socket_connect_timeout=3, socket_timeout=3,
    )
    try:
        await verify_schema_revision()
        yield
    finally:
        SHUTDOWN_STATE.draining = True
        logger.info("shutdown_started")
        grace = settings.chat_stream_shutdown_grace_seconds
        drain_started = time.monotonic()
        if SHUTDOWN_STATE.active_streams:
            pending_set = set(SHUTDOWN_STATE.active_streams)
            await asyncio.wait(pending_set, timeout=grace)
            remaining = [t for t in SHUTDOWN_STATE.active_streams if not t.done()]
        else:
            remaining = []
        if remaining:
            logger.warning("shutdown_grace_timeout", extra={"active_streams": len(remaining)})
            for task in remaining:
                task.cancel()
                METRICS.shutdown_forced_cancellations.inc()
            await asyncio.gather(*remaining, return_exceptions=True)
        METRICS.shutdown_drain.observe(time.monotonic() - drain_started)
        await app.state.redis.aclose()
        await engine.dispose()
        logger.info("shutdown_completed")


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
if settings.trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", settings.request_id_header, "Idempotency-Key", "X-CSRF-Token", "Last-Event-ID"],
)
install_error_handlers(app)
app.include_router(operations_router)
app.include_router(api_router)


@app.middleware("http")
async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """شناسهٔ درخواست و مدت پاسخ را در state، header و لاگ ثبت می‌کند."""
    supplied = request.headers.get(settings.request_id_header, "")
    request_id = supplied if _REQUEST_ID_RE.fullmatch(supplied) else str(uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", extra={"request_id": request_id, "path": request.url.path, "method": request.method})
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers[settings.request_id_header] = request_id
    logger.info("request_complete", extra={"request_id": request_id, "path": request.url.path, "method": request.method, "status_code": response.status_code, "duration_ms": duration_ms})
    return response
