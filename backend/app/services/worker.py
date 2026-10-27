"""کارگر arq پایه؛ jobهای محصولی در فازهای مربوطه اضافه می‌شوند."""

from arq.connections import RedisSettings

from app.core.config import get_settings

settings = get_settings()


async def worker_probe(ctx: dict[str, object]) -> dict[str, str]:
    """job بررسی پایه است و هیچ مدل سنگینی بارگذاری نمی‌کند."""
    return {"status": "ok"}


class WorkerSettings:
    """پیکربندی worker arq برای jobهای async."""
    functions = [worker_probe]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 300
