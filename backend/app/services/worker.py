"""کارگر arq پایه؛ jobهای محصولی در فازهای مربوطه اضافه می‌شوند."""

import logging
from datetime import UTC, datetime, timedelta

from arq.connections import RedisSettings
from arq.cron import cron
from sqlalchemy import select

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ORPHAN_MESSAGE_STALE_MINUTES = 2
RESERVATION_DEADLINE_MINUTES = 15
STREAM_LEASE_EXPIRY_SECONDS = 60.0


def _terminal_status_for_recovery(reservation_status: str, billable_seen: bool) -> str:
    """نگاشت نتیجهٔ مالی ← وضعیت terminal پیام (ADR-039).

    - settled → completed (نهایی/پرداخت‌شده)
    - released + billable → partial (late-completion طبق D-07)
    - released + بدون billable → cancelled
    """
    if reservation_status == "settled":
        return "completed"
    if reservation_status == "released":
        return "partial" if billable_seen else "cancelled"
    return "cancelled"


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


async def recover_orphan_stream_messages(ctx: dict[str, object]) -> dict[str, int]:
    """بازیابی durable پیام‌های assistant که پس از Crash در حالت streaming مانده‌اند.

    تشخیص orphan بر پایه **Lease ضربان** است (heartbeat_at)، نه صرفاً updated_at:
    فقط پیام‌هایی که heartbeat آنها از `STREAM_LEASE_EXPIRY_SECONDS` گذشته باشد و همچنان
    streaming باشند، orphan فرض می‌شوند. یک Stream فعال که در انتظار Provider بدون Delta
    است، heartbeat خود را به‌روز می‌کند و توسط Recovery آزاد نمی‌شود.

    - رزرو pendingِ عبورکرده از مهلت مالی (۱۵ دقیقه) فقط از طریق FinanceService.release آزاد
      می‌شود؛ هیچ ledger/balance مستقیماً دستکاری نمی‌شود.
    - نگاشت پیام با `_terminal_status_for_recovery` (settled→completed؛ released+billable→partial؛
      released بدون billable→cancelled).
    - تغییر پیام فقط با شرط `status='streaming'` (fencing) انجام می‌شود؛ idempotent.
    """
    from sqlalchemy import text

    from app.db.session import SessionFactory
    from app.models.message import Message
    from app.repositories import reservations as res_repo
    from app.services.reservation import FinanceService

    raw_limit = ctx.get("batch_limit", 200)
    batch_limit = int(str(raw_limit)) if raw_limit is not None else 200
    lease_cutoff = datetime.now(UTC) - timedelta(seconds=STREAM_LEASE_EXPIRY_SECONDS)
    recovered = 0

    # کاندیداها فقط برای انتخاب خوانده می‌شوند (بدون قفل).
    async with SessionFactory() as select_session:
        orphans = (
            await select_session.execute(
                select(Message).where(
                    Message.role == "assistant",
                    Message.status == "streaming",
                    Message.reservation_id.is_not(None),
                    (Message.heartbeat_at.is_(None)) | (Message.heartbeat_at < lease_cutoff),
                ).order_by(Message.reservation_id.asc(), Message.id.asc()).limit(batch_limit)
            )
        ).scalars().all()

    # هر کاندیدا در یک session/تراکنش مستقل (هیچ قفلی بین کاندیداها زنده نمی‌ماند):
    # ترتیب قفل جهانی Reservation → Message → Financial mutation → Commit.
    for msg in orphans:
        if msg.reservation_id is None:
            continue
        async with SessionFactory() as cand_session:
            try:
                reservation = await res_repo.get_by_id_for_update(cand_session, msg.reservation_id)
                if reservation is None:
                    continue
                final_status: str | None = None
                if reservation.status == "pending":
                    overdue = (datetime.now(UTC) - reservation.created_at) > timedelta(
                        minutes=RESERVATION_DEADLINE_MINUTES
                    )
                    if not overdue:
                        continue
                    final_status = _terminal_status_for_recovery("released", msg.billable_output_seen)
                else:
                    final_status = _terminal_status_for_recovery(reservation.status, msg.billable_output_seen)

                claimed_row = (
                    await cand_session.execute(
                        text(
                            "UPDATE messages SET status = :status, stream_terminated = true, "
                            "stream_owner_token = NULL "
                            "WHERE id = :id AND status = 'streaming' "
                            "AND (heartbeat_at IS NULL OR heartbeat_at < :lease_cutoff) "
                            "AND stream_owner_token IS NOT DISTINCT FROM :observed_owner "
                            "RETURNING id"
                        ),
                        {
                            "status": final_status,
                            "id": str(msg.id),
                            "lease_cutoff": lease_cutoff,
                            "observed_owner": msg.stream_owner_token,
                        },
                    )
                ).first()
                if claimed_row is None:
                    await cand_session.rollback()
                    continue
                if reservation.status == "pending":
                    await FinanceService(cand_session).release(reservation.id, reason="crash_recovery")
                await cand_session.commit()
                recovered += 1
            except Exception:  # noqa: BLE001 - isolate per-candidate failure
                await cand_session.rollback()
                logger.debug("recovery_per_message_skipped")
    return {"recovered": recovered}


class WorkerSettings:
    """پیکربندی worker arq برای jobهای async."""
    functions = [worker_probe]
    # بازیابی رزروهای stale + پیام‌های orphan به‌عنوان آخرین لایه recovery پس از
    # shutdown/تصادف. cadence = هر ۶۰ ثانیه، + اجرا در startup.
    cron_jobs = [
        cron(
            expire_reservation_deadlines,
            name="release-stale-reservations",
            second={0},
            run_at_startup=True,
        ),
        cron(
            recover_orphan_stream_messages,
            name="recover-orphan-stream-messages",
            second={0},
            run_at_startup=True,
        ),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 300
