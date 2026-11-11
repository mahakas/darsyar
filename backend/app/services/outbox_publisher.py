"""Slice 3: transactional outbox publisher (synthetic events only).

PostgreSQL Outbox → ARQ enqueue → message available in the dedicated queue (no consumer).
At-least-once delivery: PostgreSQL and Redis cannot join one atomic distributed
transaction, so exactly-once is never claimed. Deterministic ARQ job IDs reduce
duplicate queue entries; downstream idempotency remains required.

Concurrency: within a single short PostgreSQL transaction we atomically claim
rows with `FOR UPDATE SKIP LOCKED`, enqueue to Redis, then commit the
publication-state update. The row lock is held across the bounded Redis call.
This is chosen over a two-phase claim because the current outbox schema has no
lease columns, so a committed intermediate `publishing` state would be
unrecoverable without an invented staleness threshold (see implementation
spec, "Concurrency mechanism").
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from arq.connections import ArqRedis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import METRICS
from app.models.outbox_event import OutboxEvent
from app.repositories import outbox_events as outbox_repo

logger = get_logger(__name__)

INGESTION_EVENT_FUNCTION = "process_ingestion_event"
INGESTION_EVENT_QUEUE = "arq:queue:ingestion"
PUBLISH_CONTRACT_VERSION = 1
SUPPORTED_EVENT_TYPES = ("ingestion_create",)
SUPPORTED_SCHEMA_VERSIONS = (1,)
MAX_ERROR_DETAILS_CHARS = 2000


class UnsupportedEventContractError(Exception):
    """رویداد قرارداد پشتیبانی‌نشده دارد؛ به‌صورت دائمی `failed` می‌شود."""


class OutboxPublishCommitError(Exception):
    """درج حالت انتشار در PostgreSQL پس از enqueue با شکست مواجه شد."""


@dataclass(frozen=True)
class PublishResult:
    """نتیجهٔ ساختاریافتهٔ یک اجرای publisher/reconciliation."""

    published: int
    deferred: int
    failed: int


def _safe_error_details(exc: Exception) -> str:
    """خلاصهٔ امن خطا برای `last_error_details` (بدون خروجی/credential)."""
    summary = f"{type(exc).__name__}: {exc}"
    return summary[:MAX_ERROR_DETAILS_CHARS]


def _arq_job_id(dedup_key: str) -> str:
    """شناسهٔ پایدار و محدود ARQ از هویت dedup کن outbox.

    `dedup_key` قالب `create:<job_id>` دارد؛ شناسهٔ ARQ از همان مؤلفهٔ شغلی
    مشتق می‌شود تا بازانتشار با `_job_id` یکسان در صف dedup شود.
    """
    if ":" in dedup_key:
        ident = dedup_key.split(":", 1)[1]
    else:
        ident = hashlib.sha256(dedup_key.encode("utf-8")).hexdigest()
    return f"ingestion:{ident}"


def _event_message_kwargs(event: OutboxEvent) -> dict[str, Any]:
    """پیام ARQ حداقلی و نسخه‌دار؛ بدون راز، محتوای خام یا اطلاعات شخصی."""
    return {
        "event_id": str(event.id),
        "job_id": str(event.job_id),
        "dedup_key": event.dedup_key,
        "event_type": event.event_type,
        "schema_version": event.schema_version,
        "contract_version": PUBLISH_CONTRACT_VERSION,
    }


def _validate_event_contract(event: OutboxEvent) -> None:
    if event.event_type not in SUPPORTED_EVENT_TYPES:
        raise UnsupportedEventContractError(f"unsupported event_type: {event.event_type}")
    if event.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise UnsupportedEventContractError(f"unsupported schema_version: {event.schema_version}")


async def run_outbox_publisher(
    session: AsyncSession,
    redis: ArqRedis,
    *,
    batch_size: int,
    source: str,
) -> PublishResult:
    """هستهٔ مشترک publisher و reconciliation (یکی از مسیرهای انتشار)."""
    attempt_id = uuid.uuid4()
    base = {"source": source, "attempt_id": str(attempt_id), "batch_size": batch_size}
    logger.info("outbox_publisher_invoked", extra=base)
    METRICS.outbox_publisher_invocations.inc({"source": source})
    if source == "reconciliation":
        METRICS.outbox_reconciliation_attempts.inc()

    now = datetime.now(UTC)
    events = await outbox_repo.claim_eligible_events(session, limit=batch_size, now=now)
    logger.debug(
        "outbox_claim_result",
        extra={"claimed": len(events), "requested_batch": batch_size, "attempt_id": str(attempt_id)},
    )

    published = 0
    deferred = 0
    failed = 0

    for event in events:
        METRICS.outbox_events_discovered.inc()
        ev_extra = {
            "event_id": str(event.id),
            "job_id": str(event.job_id),
            "dedup_key": event.dedup_key,
            "arq_job_id": _arq_job_id(event.dedup_key),
            "attempt_id": str(attempt_id),
        }

        try:
            _validate_event_contract(event)
        except UnsupportedEventContractError as exc:
            await outbox_repo.record_permanent_failure(
                session, event.id, details=_safe_error_details(exc)
            )
            failed += 1
            logger.warning("outbox_permanent_failure", extra={**ev_extra, "reason": str(exc)})
            METRICS.outbox_events_failed.inc()
            continue

        try:
            job = await redis.enqueue_job(
                INGESTION_EVENT_FUNCTION,
                _job_id=_arq_job_id(event.dedup_key),
                _queue_name=INGESTION_EVENT_QUEUE,
                **_event_message_kwargs(event),
            )
        except (RedisError, OSError, TimeoutError) as exc:
            await outbox_repo.record_transient_failure(
                session, event.id, details=_safe_error_details(exc)
            )
            deferred += 1
            logger.warning("outbox_redis_failure_deferred", extra={**ev_extra, "error": _safe_error_details(exc)})
            METRICS.outbox_events_deferred.inc()
            continue

        if job is None:
            logger.info("outbox_duplicate_enqueue", extra=ev_extra)
            METRICS.outbox_duplicate_enqueue.inc()

        await outbox_repo.mark_published(session, event.id, now=now)
        published += 1
        METRICS.outbox_events_published.inc()

    try:
        await session.commit()
    except Exception as exc:
        logger.error(
            "outbox_pg_commit_failure_after_enqueue",
            extra={"source": source, "attempt_id": str(attempt_id)},
            exc_info=exc,
        )
        METRICS.outbox_pg_commit_failure_after_enqueue.inc()
        raise OutboxPublishCommitError("outbox_publish_commit_failed") from exc

    logger.info(
        "outbox_publisher_completed",
        extra={**base, "published": published, "deferred": deferred, "failed": failed},
    )
    return PublishResult(published=published, deferred=deferred, failed=failed)


async def publish_pending_outbox_events(
    session: AsyncSession,
    redis: ArqRedis,
    *,
    batch_size: int,
) -> PublishResult:
    """رویدادهای واجدشرایط را انتشار می‌دهد (یک‌بار اجرای خودسر)."""
    return await run_outbox_publisher(session, redis, batch_size=batch_size, source="publish")
