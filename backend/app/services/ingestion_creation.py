"""Slice 2: transactional ingestion job + initial outbox creation.

Creates `IngestionJob` + `OutboxEvent` atomically in one PostgreSQL transaction.
Request idempotency is scoped to (document_id, request_idempotency_key).

PostgreSQL remains authoritative; Redis/ARQ are not touched. No publication happens here.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.ingestion_document import IngestionDocument
from app.models.ingestion_job import IngestionJob
from app.models.outbox_event import OutboxEvent

JOB_IDEMPOTENCY_UC = "uq_ingestion_jobs_request_idempotency"
OUTBOX_DEDUP_UC = "uq_outbox_events_dedup"
OUTBOX_EVENT_TYPE = "ingestion_create"
OUTBOX_SCHEMA_VERSION = 1


class IdempotencyConflictError(AppError):
    def __init__(self) -> None:
        super().__init__("idempotency_conflict", 409, "درخواست تکراری با محتوای متناقض.")


@dataclass(frozen=True)
class IngestionCreationResult:
    job: IngestionJob
    outbox: OutboxEvent
    created: bool


def _outbox_dedup_key(job_id: uuid.UUID) -> str:
    return f"create:{job_id}"


async def _get_creation_outbox(session: AsyncSession, job_id: uuid.UUID) -> OutboxEvent | None:
    result = await session.execute(
        select(OutboxEvent).where(
            OutboxEvent.job_id == job_id,
            OutboxEvent.dedup_key == _outbox_dedup_key(job_id),
        )
    )
    return result.scalar_one_or_none()


async def create_ingestion_job(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    request_idempotency_key: str,
    request_hash: str,
    job_type: str = "pdf",
    schema_version: int = 1,
    commit: bool = False,
) -> IngestionCreationResult:
    """یک job + یک outbox اولیه را اتمیک می‌سازد؛ یا job موجود را بازمی‌گرداند.

    - معادل (همان سند، همان کلید، همان hash) → job موجود + outbox ایجادشده بازگردانده می‌شود.
    - تضاد (همان سند، همان کلید، hash متفاوت) → IdempotencyConflictError.
    - سند متفاوت با همان کلید → مستقل (scope سند).
    - `commit=False` (پیش‌فرض): caller commit می‌کند (قرارداد موجود). `commit=True` برای تست‌های مستقل.
    """
    document = await session.get(IngestionDocument, document_id)
    if document is None:
        raise AppError("document_not_found", 404, "سند یافت نشد.")

    if not request_idempotency_key or not request_hash:
        raise AppError("invalid_idempotency_key", 422, "کلید idempotency نامعتبر است.")

    existing = (
        await session.execute(
            select(IngestionJob).where(
                IngestionJob.document_id == document_id,
                IngestionJob.request_idempotency_key == request_idempotency_key,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError()
        outbox = await _get_creation_outbox(session, existing.id)
        if outbox is None:
            raise AppError("invariant_violation_missing_outbox", 500, "job موجود بدون رویداد outbox اولیه.")
        return IngestionCreationResult(job=existing, outbox=outbox, created=False)

    job = IngestionJob(
        job_type=job_type,
        schema_version=schema_version,
        status="queued",
        document_id=document_id,
        request_idempotency_key=request_idempotency_key,
        request_hash=request_hash,
    )
    session.add(job)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _constraint_is(exc, JOB_IDEMPOTENCY_UC):
            return await _on_duplicate_job(session, document_id, request_idempotency_key, request_hash)
        raise

    outbox = OutboxEvent(
        event_type=OUTBOX_EVENT_TYPE,
        schema_version=OUTBOX_SCHEMA_VERSION,
        job_id=job.id,
        dedup_key=_outbox_dedup_key(job.id),
        payload={
            "job_id": str(job.id),
            "job_type": job_type,
            "schema_version": schema_version,
            "request_idempotency_key": request_idempotency_key,
        },
        publication_state="pending",
    )
    session.add(outbox)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _constraint_is(exc, OUTBOX_DEDUP_UC):
            # مسابقه: رویداد dedup یکسان از قبل در همان تراکنش/جاهای دیگر درج شد → invariant.
            raise AppError("invariant_violation_outbox_dedup", 500, "dedup رویداد outbox نامعتبر است.") from exc
        raise

    if commit:
        await session.commit()

    return IngestionCreationResult(job=job, outbox=outbox, created=True)


async def _on_duplicate_job(
    session: AsyncSession,
    document_id: uuid.UUID,
    key: str,
    request_hash: str,
) -> IngestionCreationResult:
    existing = (
        await session.execute(
            select(IngestionJob).where(
                IngestionJob.document_id == document_id,
                IngestionJob.request_idempotency_key == key,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        raise AppError("idempotency_race_recovered", 409, "مسابقه‌ی idempotency.")
    if existing.request_hash != request_hash:
        raise IdempotencyConflictError()
    outbox = await _get_creation_outbox(session, existing.id)
    if outbox is None:
        raise AppError("invariant_violation_missing_outbox", 500, "job موجود بدون رویداد outbox اولیه.")
    return IngestionCreationResult(job=existing, outbox=outbox, created=False)


def _constraint_is(exc: IntegrityError, constraint: str) -> bool:
    """بررسی نام constraint در جزئیات درایور (asyncpg)."""
    orig = getattr(exc, "orig", None)
    detail = getattr(orig, "constraint_name", None)
    if not detail:
        s: str = str(orig) if orig is not None else str(exc)
        return constraint in s
    matched: bool = detail == constraint
    return matched
