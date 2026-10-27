"""مسیر سازگاری liveness در API v1؛ endpointهای عملیاتی canonical در app.core.operations هستند."""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health-compatibility"])
settings = get_settings()


@router.get("/live")
async def live() -> dict[str, str]:
    """برای سازگاری با رابط توسعه، وضعیت process را نشان می‌دهد."""
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}
