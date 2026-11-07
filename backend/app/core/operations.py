"""سامانهٔ سلامت و نسخه؛ endpointهای عملیاتی مستقل از API محصول."""

import ipaddress

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.metrics import METRICS
from app.core.shutdown import SHUTDOWN_STATE
from app.db.session import ping_database


def _metrics_peer_allowed(client_host: str | None, allowed_networks: list[str]) -> bool:
    """فقط همسایهٔ فوری (socket peer) با XFF قابل جعل بررسی می‌شود.

    وجود X-Forwarded-For به‌تنهایی هرگز ملاک نیست (کلاینت می‌تواند آن را جعل کند).
    """
    if not client_host:
        return False
    try:
        peer = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    if peer.is_loopback:
        return True
    for network in allowed_networks:
        try:
            if peer in ipaddress.ip_network(network, strict=False):
                return True
        except ValueError:
            continue
    return False

router = APIRouter(tags=["operations"])
settings = get_settings()


@router.get("/health")
async def health() -> dict[str, str]:
    """liveness را بدون بررسی dependency خارجی گزارش می‌کند."""
    return {"status": "ok", "service": settings.app_name}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """آمادگی را گزارش می‌کند؛ هنگام draining (خاموشی) همیشه not_ready است."""
    if SHUTDOWN_STATE.draining:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    try:
        await ping_database()
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is None:
            raise RuntimeError("Redis client unavailable")
        await redis_client.ping()
        if settings.inference_mode == "service":
            async with httpx.AsyncClient(timeout=settings.inference_timeout_seconds) as client:
                inference_response = await client.get(f"{settings.inference_url.rstrip('/')}/ready")
                inference_response.raise_for_status()
    except (SQLAlchemyError, RedisError, OSError, RuntimeError, TimeoutError, httpx.HTTPError):
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return JSONResponse(status_code=200, content={"status": "ready"})


@router.get("/metrics")
async def metrics(request: Request) -> JSONResponse:
    """متریک‌های داخلی؛ فقط از همسایهٔ فوری «/شبکهٔ داخلی مجاز.

    هدر X-Forwarded-For قابل جعل است و ملاک دسترسی نیست؛ فقط
    `request.client.host` (peer واقعی socket) با شبکه‌های مجاز مقایسه می‌شود.
    """
    peer = request.client.host if request.client else None
    if not _metrics_peer_allowed(peer, get_settings().metrics_allowed_networks):
        return JSONResponse(status_code=403, content={"detail": "forbidden"})
    return JSONResponse(content={"text": METRICS.as_prometheus_text()})


@router.get("/version")
async def version() -> dict[str, str]:
    """نسخهٔ build را گزارش می‌کند؛ commit در فرآیند CI/deployment تزریق می‌شود."""
    return {"version": settings.app_version, "commit": "unknown"}
