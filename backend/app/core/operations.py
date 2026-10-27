"""سامانهٔ سلامت و نسخه؛ endpointهای عملیاتی مستقل از API محصول."""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import ping_database

router = APIRouter(tags=["operations"])
settings = get_settings()


@router.get("/health")
async def health() -> dict[str, str]:
    """liveness را بدون بررسی dependency خارجی گزارش می‌کند."""
    return {"status": "ok", "service": settings.app_name}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """آمادگی DB، Redis و inference را بررسی می‌کند؛ جزئیات اتصال افشا نمی‌شوند."""
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


@router.get("/version")
async def version() -> dict[str, str]:
    """نسخهٔ build را گزارش می‌کند؛ commit در فرآیند CI/deployment تزریق می‌شود."""
    return {"version": settings.app_version, "commit": "unknown"}
