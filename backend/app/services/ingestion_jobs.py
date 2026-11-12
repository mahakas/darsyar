"""Durable PostgreSQL claim/lease/fencing lifecycle for synthetic ingestion jobs.

This module is deliberately not registered in ARQ and does not open or process
PDFs. Runtime policy values (lease duration, retry instant, batch size) are
required function arguments: no deployment defaults are inferred here.

The caller owns the transaction and must commit/rollback explicitly.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import CursorResult as _CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.ingestion_job import IngestionJob

CursorResult = _CursorResult[object]

CLAIMABLE_JOB_STATES = ("queued", "retry_waiting")
RUNNING_JOB_STATE = "running"
CANCELLATION_REQUESTED_STATE = "cancellation_requested"
CANCELLED_STATE = "cancelled"
SUCCEEDED_STATE = "succeeded"
TERMINAL_FAILURE_STATE = "terminal_failure"
_ERROR_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


@dataclass(frozen=True, slots=True)
class IngestionJobLease:
    """Snapshot of the current fenced attempt; do not reconstruct from ARQ IDs."""

    job_id: uuid.UUID
    worker_id: str
    lease_token: uuid.UUID
    fencing_token: int
    attempt_count: int
    lease_expires_at: datetime


def _validate_instant(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _validate_lease_duration(value: timedelta) -> None:
    if not isinstance(value, timedelta) or value.total_seconds() <= 0:
        raise ValueError("lease_duration must be a positive timedelta")


def _validate_worker_id(worker_id: str) -> None:
    if not isinstance(worker_id, str) or not worker_id.strip() or len(worker_id) > 64:
        raise ValueError("worker_id must be a non-empty string of at most 64 characters")


def _validate_batch_size(batch_size: int) -> None:
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")


def _validate_error_code(error_code: str) -> None:
    if not isinstance(error_code, str) or _ERROR_CODE_RE.fullmatch(error_code) is None:
        raise ValueError("error_code must be a lower_snake_case identifier of at most 64 characters")


def _owned_running_conditions(lease: IngestionJobLease, now: datetime) -> tuple[ColumnElement[bool], ...]:
    return (
        IngestionJob.id == lease.job_id,
        IngestionJob.status == RUNNING_JOB_STATE,
        IngestionJob.lease_owner == lease.worker_id,
        IngestionJob.lease_token == lease.lease_token,
        IngestionJob.fencing_token == lease.fencing_token,
        IngestionJob.lease_expires_at.is_not(None),
        IngestionJob.lease_expires_at > now,
        IngestionJob.cancellation_requested.is_(False),
    )


def _clear_lease_values() -> dict[str, Any]:
    return {
        "lease_owner": None,
        "lease_token": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
    }


async def claim_next_ingestion_job(
    session: AsyncSession,
    *,
    worker_id: str,
    now: datetime,
    lease_duration: timedelta,
    job_type: str | None = None,
) -> IngestionJobLease | None:
    """Atomically claim one eligible job or reclaim an expired running attempt.

    Eligible jobs are queued/retry-waiting jobs whose retry instant has arrived,
    plus running jobs whose lease expired. SELECT FOR UPDATE SKIP LOCKED prevents
    concurrent claimers from receiving the same row. Every claim increments both
    attempt_count and the monotonic fencing_token; a stale attempt can no longer
    complete or heartbeat after reclamation. An optional job_type restricts this
    claim to a specific worker queue without changing the default all-type queue.

    No lease duration is selected here. The caller must provide an approved,
    measured runtime value; this helper is suitable for synthetic/PostgreSQL tests
    until deployment parameters and ARQ integration receive separate approval.
    """
    _validate_worker_id(worker_id)
    _validate_instant(now, "now")
    _validate_lease_duration(lease_duration)
    if job_type is not None and (not isinstance(job_type, str) or not job_type.strip() or len(job_type) > 32):
        raise ValueError("job_type must be a non-empty string of at most 32 characters")

    eligible = or_(
        and_(
            IngestionJob.status.in_(CLAIMABLE_JOB_STATES),
            IngestionJob.retry_available_at <= now,
        ),
        and_(
            IngestionJob.status == RUNNING_JOB_STATE,
            IngestionJob.cancellation_requested.is_(False),
            or_(
                IngestionJob.lease_expires_at.is_(None),
                IngestionJob.lease_expires_at <= now,
            ),
        ),
    )
    if job_type is not None:
        eligible = and_(eligible, IngestionJob.job_type == job_type)

    statement = (
        select(IngestionJob)
        .where(eligible)
        .order_by(
            IngestionJob.retry_available_at.asc(),
            IngestionJob.created_at.asc(),
            IngestionJob.id.asc(),
        )
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(statement)
    job = result.scalar_one_or_none()
    if job is None:
        return None

    expires_at = now + lease_duration
    token = uuid.uuid4()
    job.status = RUNNING_JOB_STATE
    job.lease_owner = worker_id
    job.lease_token = token
    job.lease_expires_at = expires_at
    job.heartbeat_at = now
    job.attempt_count += 1
    job.fencing_token += 1
    job.started_at = job.started_at or now
    job.finished_at = None
    job.updated_at = now
    await session.flush()

    return IngestionJobLease(
        job_id=job.id,
        worker_id=worker_id,
        lease_token=token,
        fencing_token=job.fencing_token,
        attempt_count=job.attempt_count,
        lease_expires_at=expires_at,
    )


async def renew_ingestion_job_lease(
    session: AsyncSession,
    *,
    lease: IngestionJobLease,
    now: datetime,
    lease_duration: timedelta,
) -> bool:
    """Renew only the current, unexpired, non-cancelled fenced attempt."""
    _validate_instant(now, "now")
    _validate_lease_duration(lease_duration)
    result = await session.execute(
        update(IngestionJob)
        .where(*_owned_running_conditions(lease, now))
        .values(
            lease_expires_at=now + lease_duration,
            heartbeat_at=now,
            updated_at=now,
        )
    )
    await session.flush()
    return cast(CursorResult, result).rowcount == 1


async def complete_ingestion_job(
    session: AsyncSession,
    *,
    lease: IngestionJobLease,
    now: datetime,
) -> bool:
    """Mark success only while the attempt still owns a live, uncancelled lease."""
    _validate_instant(now, "now")
    values = {
        "status": SUCCEEDED_STATE,
        "last_error_code": None,
        "last_error_summary": None,
        "finished_at": now,
        "updated_at": now,
        **_clear_lease_values(),
    }
    result = await session.execute(
        update(IngestionJob)
        .where(*_owned_running_conditions(lease, now))
        .values(**values)
    )
    await session.flush()
    return cast(CursorResult, result).rowcount == 1


async def retry_ingestion_job(
    session: AsyncSession,
    *,
    lease: IngestionJobLease,
    now: datetime,
    retry_available_at: datetime,
    error_code: str,
) -> bool:
    """Release the current attempt into retry_waiting at an explicit retry instant.

    Backoff and retry-count policy are intentionally not invented. The caller
    supplies retry_available_at; owner/deployment policy must decide max attempts
    and backoff before any consumer is registered.
    """
    _validate_instant(now, "now")
    _validate_instant(retry_available_at, "retry_available_at")
    _validate_error_code(error_code)
    if retry_available_at <= now:
        raise ValueError("retry_available_at must be later than now")

    values = {
        "status": "retry_waiting",
        "retry_available_at": retry_available_at,
        "last_error_code": error_code,
        "last_error_summary": None,
        "finished_at": None,
        "updated_at": now,
        **_clear_lease_values(),
    }
    result = await session.execute(
        update(IngestionJob)
        .where(*_owned_running_conditions(lease, now))
        .values(**values)
    )
    await session.flush()
    return cast(CursorResult, result).rowcount == 1


async def fail_ingestion_job(
    session: AsyncSession,
    *,
    lease: IngestionJobLease,
    now: datetime,
    error_code: str,
) -> bool:
    """Record a non-retryable failure for the currently owned attempt."""
    _validate_instant(now, "now")
    _validate_error_code(error_code)
    values = {
        "status": TERMINAL_FAILURE_STATE,
        "last_error_code": error_code,
        "last_error_summary": None,
        "finished_at": now,
        "updated_at": now,
        **_clear_lease_values(),
    }
    result = await session.execute(
        update(IngestionJob)
        .where(*_owned_running_conditions(lease, now))
        .values(**values)
    )
    await session.flush()
    return cast(CursorResult, result).rowcount == 1


async def request_ingestion_job_cancellation(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    now: datetime,
) -> str | None:
    """Request cancellation idempotently; queued work cancels immediately.

    Running work transitions to cancellation_requested while retaining its lease
    so the current parent can terminate/reap its child and acknowledge cancellation.
    Terminal jobs are never reopened. Returns the resulting state, or None if the
    job does not exist.
    """
    _validate_instant(now, "now")
    result = await session.execute(
        select(IngestionJob).where(IngestionJob.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None

    if job.status in CLAIMABLE_JOB_STATES:
        job.status = CANCELLED_STATE
        job.cancellation_requested = True
        job.finished_at = now
        job.updated_at = now
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        job.heartbeat_at = None
    elif job.status == RUNNING_JOB_STATE:
        job.status = CANCELLATION_REQUESTED_STATE
        job.cancellation_requested = True
        job.updated_at = now
    await session.flush()
    return job.status


async def acknowledge_ingestion_job_cancellation(
    session: AsyncSession,
    *,
    lease: IngestionJobLease,
    now: datetime,
) -> bool:
    """Acknowledge cancellation only from the active fenced attempt."""
    _validate_instant(now, "now")
    result = await session.execute(
        update(IngestionJob)
        .where(
            IngestionJob.id == lease.job_id,
            IngestionJob.status == CANCELLATION_REQUESTED_STATE,
            IngestionJob.lease_owner == lease.worker_id,
            IngestionJob.lease_token == lease.lease_token,
            IngestionJob.fencing_token == lease.fencing_token,
            IngestionJob.lease_expires_at.is_not(None),
            IngestionJob.lease_expires_at > now,
            IngestionJob.cancellation_requested.is_(True),
        )
        .values(
            status=CANCELLED_STATE,
            finished_at=now,
            updated_at=now,
            **_clear_lease_values(),
        )
    )
    await session.flush()
    return cast(CursorResult, result).rowcount == 1


async def finalize_expired_ingestion_cancellations(
    session: AsyncSession,
    *,
    now: datetime,
    batch_size: int,
) -> int:
    """Finalize cancellation requests whose worker lease expired.

    This is a callable maintenance primitive only: it is not scheduled, registered
    in ARQ, or invoked automatically. A caller must supply an explicit batch size.
    """
    _validate_instant(now, "now")
    _validate_batch_size(batch_size)
    statement = (
        select(IngestionJob)
        .where(
            IngestionJob.status == CANCELLATION_REQUESTED_STATE,
            or_(
                IngestionJob.lease_expires_at.is_(None),
                IngestionJob.lease_expires_at <= now,
            ),
        )
        .order_by(IngestionJob.lease_expires_at.asc().nulls_first(), IngestionJob.id.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(statement)
    jobs = list(result.scalars().all())
    for job in jobs:
        job.status = CANCELLED_STATE
        job.finished_at = now
        job.updated_at = now
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        job.heartbeat_at = None
    await session.flush()
    return len(jobs)
