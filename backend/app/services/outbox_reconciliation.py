"""Slice 3: reconciliation یک‌بارمصرف outbox (idempotent).

از همان قرارداد publisher استفاده می‌کند: رویدادهای واجدشرایط (pending) را از
PostgreSQL می‌خواند و انتشار را دوباره تلاش می‌کند. بازانتشار با `_job_id`
قطعی ARQ dedup می‌شود؛ رکوردهای `published` بازانتشار نمی‌شوند. هیچ حذف یا
آرشیوی انجام نمی‌شود و اجرای تکراری نتیجهٔ امن دارد.

زمان‌بندی دوره‌ای این سرویس به تصمیم مالک موکول است و در این برش تنظیم نمی‌شود.
"""

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.outbox_publisher import PublishResult, run_outbox_publisher

__all__ = ["reconcile_pending_outbox_events", "PublishResult"]


async def reconcile_pending_outbox_events(
    session: AsyncSession,
    redis: ArqRedis,
    *,
    batch_size: int,
) -> PublishResult:
    """رسیدگی به رویدادهای منتشرنشدهٔ واجدشرایط با همان قرارداد انتشار."""
    return await run_outbox_publisher(session, redis, batch_size=batch_size, source="reconciliation")
