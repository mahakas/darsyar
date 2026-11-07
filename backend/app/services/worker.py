"""کارگر arq پایه؛ jobهای محصولی در فازهای مربوطه اضافه می‌شوند."""

from arq.connections import RedisSettings

from app.core.config import get_settings

settings = get_settings()


async def worker_probe(ctx: dict[str, object]) -> dict[str, str]:
    """job بررسی پایه است و هیچ مدل سنگینی بارگذاری نمی‌کند."""
    return {"status": "ok"}


async def expire_reservation_deadlines(ctx: dict[str, object]) -> dict[str, int]:
    """رهاسازی رزروهای عبورکرده از مهلت (OQ-027)."""
    from app.db.session import SessionFactory
    from app.services.reservation import FinanceService

    raw_limit = ctx.get("batch_limit", 200)
    batch_limit = int(str(raw_limit)) if raw_limit is not None else 200
    async with SessionFactory() as session:
        count = await FinanceService(session).expire_reservation_deadlines(batch_limit=batch_limit)
        await session.commit()
    return {"released": count}


async def expire_plan_entitlements(ctx: dict[str, object]) -> dict[str, int]:
    """انقضای اتمیک entitlementهای سررسیدشده؛ idempotent (ADR-052)."""
    from app.db.session import SessionFactory
    from app.services.plans import PlanService

    raw_limit = ctx.get("batch_limit", 200)
    batch_limit = int(str(raw_limit)) if raw_limit is not None else 200
    async with SessionFactory() as session:
        count = await PlanService(session).expire_due_entitlements(batch_limit=batch_limit)
        await session.commit()
    return {"expired": count}


class WorkerSettings:
    """پیکربندی worker arq برای jobهای async."""
    functions = [worker_probe]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 300
