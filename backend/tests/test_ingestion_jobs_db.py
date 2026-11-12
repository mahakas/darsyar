"""Slice 4 PostgreSQL tests for durable claim, lease, fencing and cancellation.

All tests use synthetic rows in the disposable PostgreSQL test database. They do
not register an ARQ consumer or read/process any textbook PDF.
"""

import asyncio
import datetime as dt
import hashlib
import os
import uuid

import pytest
from app.core.config import get_settings
from app.models.ingestion_document import IngestionDocument
from app.models.ingestion_job import IngestionJob
from app.services.ingestion_creation import create_ingestion_job
from app.services.ingestion_jobs import (
    IngestionJobLease,
    acknowledge_ingestion_job_cancellation,
    claim_next_ingestion_job,
    complete_ingestion_job,
    fail_ingestion_job,
    finalize_expired_ingestion_cancellations,
    renew_ingestion_job_lease,
    request_ingestion_job_cancellation,
    retry_ingestion_job,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)
NOW = dt.datetime.now(dt.UTC)
TEST_JOB_TYPE = "synthetic_test"


async def _new_job() -> uuid.UUID:
    async with SESSION_FACTORY() as session:
        document = IngestionDocument(
            checksum=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            edition_year=1405,
            subject="math",
            grade_level=2,
        )
        session.add(document)
        await session.flush()
        created = await create_ingestion_job(
            session,
            document_id=document.id,
            request_idempotency_key=f"test-{uuid.uuid4().hex}",
            job_type=TEST_JOB_TYPE,
            request_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        )
        created.job.retry_available_at = NOW - dt.timedelta(seconds=1)
        await session.commit()
        return created.job.id


async def _job(job_id: uuid.UUID) -> IngestionJob:
    async with SESSION_FACTORY() as session:
        job = await session.get(IngestionJob, job_id)
        assert job is not None
        return job


@pytest.mark.asyncio
async def test_claim_queued_job_assigns_lease_and_increments_fence() -> None:
    job_id = await _new_job()
    async with SESSION_FACTORY() as session:
        lease = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="synthetic-worker-a",
            now=NOW,
            lease_duration=dt.timedelta(seconds=60),
        )
        assert lease is not None
        assert lease.job_id == job_id
        assert lease.worker_id == "synthetic-worker-a"
        assert lease.fencing_token == 1
        assert lease.attempt_count == 1
        assert lease.lease_expires_at == NOW + dt.timedelta(seconds=60)
        await session.commit()

    job = await _job(job_id)
    assert job.status == "running"
    assert job.lease_token == lease.lease_token
    assert job.lease_owner == "synthetic-worker-a"
    assert job.fencing_token == 1
    assert job.attempt_count == 1
    assert job.heartbeat_at == NOW


@pytest.mark.asyncio
async def test_concurrent_claimers_never_receive_same_job() -> None:
    job_id = await _new_job()

    async def _claim(worker_id: str) -> IngestionJobLease | None:
        async with SESSION_FACTORY() as session:
            lease = await claim_next_ingestion_job(
                session,
                job_type=TEST_JOB_TYPE,
                worker_id=worker_id,
                now=NOW,
                lease_duration=dt.timedelta(minutes=1),
            )
            await session.commit()
            return lease

    first, second = await asyncio.gather(_claim("worker-one"), _claim("worker-two"))
    claimed = [lease for lease in (first, second) if lease is not None]
    assert len(claimed) == 1
    assert claimed[0].job_id == job_id
    async with SESSION_FACTORY() as session:
        assert await complete_ingestion_job(
            session,
            lease=claimed[0],
            now=NOW + dt.timedelta(seconds=1),
        )
        await session.commit()


@pytest.mark.asyncio
async def test_expired_lease_reclaims_job_and_fences_stale_attempt() -> None:
    job_id = await _new_job()
    async with SESSION_FACTORY() as session:
        old_lease = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="worker-old",
            now=NOW,
            lease_duration=dt.timedelta(seconds=30),
        )
        assert old_lease is not None
        await session.commit()

    async with SESSION_FACTORY() as session:
        new_lease = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="worker-new",
            now=NOW + dt.timedelta(seconds=31),
            lease_duration=dt.timedelta(minutes=2),
        )
        assert new_lease is not None
        assert new_lease.job_id == job_id
        assert new_lease.lease_token != old_lease.lease_token
        assert new_lease.fencing_token == old_lease.fencing_token + 1
        assert new_lease.attempt_count == old_lease.attempt_count + 1
        stale_complete = await complete_ingestion_job(
            session,
            lease=old_lease,
            now=NOW + dt.timedelta(seconds=32),
        )
        assert stale_complete is False
        current_complete = await complete_ingestion_job(
            session,
            lease=new_lease,
            now=NOW + dt.timedelta(seconds=32),
        )
        assert current_complete is True
        await session.commit()

    job = await _job(job_id)
    assert job.status == "succeeded"
    assert job.fencing_token == 2
    assert job.lease_token is None
    assert job.finished_at == NOW + dt.timedelta(seconds=32)


@pytest.mark.asyncio
async def test_heartbeat_renews_only_current_live_lease() -> None:
    job_id = await _new_job()
    async with SESSION_FACTORY() as session:
        lease = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="heartbeat-worker",
            now=NOW,
            lease_duration=dt.timedelta(seconds=30),
        )
        assert lease is not None
        await session.commit()

    renewed_at = NOW + dt.timedelta(seconds=10)
    async with SESSION_FACTORY() as session:
        assert await renew_ingestion_job_lease(
            session,
            lease=lease,
            now=renewed_at,
            lease_duration=dt.timedelta(seconds=45),
        )
        await session.commit()

    job = await _job(job_id)
    assert job.lease_expires_at == renewed_at + dt.timedelta(seconds=45)
    assert job.heartbeat_at == renewed_at

    stale = IngestionJobLease(
        job_id=lease.job_id,
        worker_id=lease.worker_id,
        lease_token=uuid.uuid4(),
        fencing_token=lease.fencing_token,
        attempt_count=lease.attempt_count,
        lease_expires_at=lease.lease_expires_at,
    )
    async with SESSION_FACTORY() as session:
        assert not await renew_ingestion_job_lease(
            session,
            lease=stale,
            now=renewed_at + dt.timedelta(seconds=1),
            lease_duration=dt.timedelta(seconds=45),
        )
        assert await complete_ingestion_job(
            session,
            lease=lease,
            now=renewed_at + dt.timedelta(seconds=2),
        )
        await session.commit()


@pytest.mark.asyncio
async def test_retry_waits_until_explicit_retry_instant_then_can_fail_terminally() -> None:
    job_id = await _new_job()
    retry_at = NOW + dt.timedelta(minutes=5)
    async with SESSION_FACTORY() as session:
        first = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="retry-worker",
            now=NOW,
            lease_duration=dt.timedelta(minutes=1),
        )
        assert first is not None and first.job_id == job_id
        assert await retry_ingestion_job(
            session,
            lease=first,
            now=NOW + dt.timedelta(seconds=10),
            retry_available_at=retry_at,
            error_code="temporary_backend_failure",
        )
        await session.commit()

    job = await _job(job_id)
    assert job.status == "retry_waiting"
    assert job.last_error_code == "temporary_backend_failure"
    assert job.lease_token is None
    assert job.retry_available_at == retry_at

    async with SESSION_FACTORY() as session:
        not_yet = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="retry-worker",
            now=retry_at - dt.timedelta(microseconds=1),
            lease_duration=dt.timedelta(minutes=1),
        )
        assert not_yet is None
        second = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="retry-worker",
            now=retry_at,
            lease_duration=dt.timedelta(minutes=1),
        )
        assert second is not None and second.job_id == job_id
        assert second.attempt_count == 2
        assert await fail_ingestion_job(
            session,
            lease=second,
            now=retry_at + dt.timedelta(seconds=1),
            error_code="permanent_parse_failure",
        )
        await session.commit()

    job = await _job(job_id)
    assert job.status == "terminal_failure"
    assert job.last_error_code == "permanent_parse_failure"
    assert job.lease_token is None


@pytest.mark.asyncio
async def test_success_after_retry_clears_previous_error_metadata() -> None:
    job_id = await _new_job()
    retry_at = NOW + dt.timedelta(minutes=2)
    async with SESSION_FACTORY() as session:
        first = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="retry-success-worker",
            now=NOW,
            lease_duration=dt.timedelta(minutes=1),
        )
        assert first is not None and first.job_id == job_id
        assert await retry_ingestion_job(
            session,
            lease=first,
            now=NOW + dt.timedelta(seconds=1),
            retry_available_at=retry_at,
            error_code="temporary_backend_failure",
        )
        await session.commit()

    async with SESSION_FACTORY() as session:
        second = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="retry-success-worker",
            now=retry_at,
            lease_duration=dt.timedelta(minutes=1),
        )
        assert second is not None and second.job_id == job_id
        assert await complete_ingestion_job(
            session,
            lease=second,
            now=retry_at + dt.timedelta(seconds=1),
        )
        await session.commit()

    job = await _job(job_id)
    assert job.status == "succeeded"
    assert job.last_error_code is None
    assert job.last_error_summary is None


@pytest.mark.asyncio
async def test_queued_cancellation_is_immediate_and_idempotent() -> None:
    job_id = await _new_job()
    async with SESSION_FACTORY() as session:
        assert await request_ingestion_job_cancellation(
            session,
            job_id=job_id,
            now=NOW,
        ) == "cancelled"
        assert await request_ingestion_job_cancellation(
            session,
            job_id=job_id,
            now=NOW + dt.timedelta(seconds=1),
        ) == "cancelled"
        await session.commit()

    job = await _job(job_id)
    assert job.status == "cancelled"
    assert job.cancellation_requested is True
    assert job.finished_at == NOW


@pytest.mark.asyncio
async def test_running_cancellation_requires_current_worker_acknowledgement() -> None:
    job_id = await _new_job()
    async with SESSION_FACTORY() as session:
        lease = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="cancel-worker",
            now=NOW,
            lease_duration=dt.timedelta(minutes=1),
        )
        assert lease is not None
        await session.commit()

    async with SESSION_FACTORY() as session:
        assert await request_ingestion_job_cancellation(
            session,
            job_id=job_id,
            now=NOW + dt.timedelta(seconds=5),
        ) == "cancellation_requested"
        await session.commit()

    async with SESSION_FACTORY() as session:
        assert not await renew_ingestion_job_lease(
            session,
            lease=lease,
            now=NOW + dt.timedelta(seconds=6),
            lease_duration=dt.timedelta(minutes=1),
        )
        assert not await complete_ingestion_job(
            session,
            lease=lease,
            now=NOW + dt.timedelta(seconds=6),
        )
        assert await acknowledge_ingestion_job_cancellation(
            session,
            lease=lease,
            now=NOW + dt.timedelta(seconds=6),
        )
        await session.commit()

    job = await _job(job_id)
    assert job.status == "cancelled"
    assert job.lease_token is None


@pytest.mark.asyncio
async def test_expired_cancellation_can_be_finalized_without_a_worker() -> None:
    job_id = await _new_job()
    async with SESSION_FACTORY() as session:
        lease = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="crashed-worker",
            now=NOW,
            lease_duration=dt.timedelta(seconds=20),
        )
        assert lease is not None
        await session.commit()

    async with SESSION_FACTORY() as session:
        assert await request_ingestion_job_cancellation(
            session,
            job_id=job_id,
            now=NOW + dt.timedelta(seconds=1),
        ) == "cancellation_requested"
        await session.commit()

    async with SESSION_FACTORY() as session:
        finalized = await finalize_expired_ingestion_cancellations(
            session,
            now=NOW + dt.timedelta(seconds=21),
            batch_size=10,
        )
        assert finalized == 1
        await session.commit()

    job = await _job(job_id)
    assert job.status == "cancelled"
    assert job.lease_token is None
    assert job.lease_expires_at is None


@pytest.mark.asyncio
async def test_expired_attempt_cannot_heartbeat_or_complete() -> None:
    job_id = await _new_job()
    async with SESSION_FACTORY() as session:
        lease = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="expired-worker",
            now=NOW,
            lease_duration=dt.timedelta(seconds=5),
        )
        assert lease is not None and lease.job_id == job_id
        await session.commit()

    expired_at = NOW + dt.timedelta(seconds=6)
    async with SESSION_FACTORY() as session:
        assert not await renew_ingestion_job_lease(
            session,
            lease=lease,
            now=expired_at,
            lease_duration=dt.timedelta(seconds=5),
        )
        assert not await complete_ingestion_job(session, lease=lease, now=expired_at)
        await session.commit()

    async with SESSION_FACTORY() as session:
        reclaimed = await claim_next_ingestion_job(
            session,
            job_type=TEST_JOB_TYPE,
            worker_id="recovery-worker",
            now=expired_at + dt.timedelta(seconds=1),
            lease_duration=dt.timedelta(minutes=1),
        )
        assert reclaimed is not None and reclaimed.job_id == job_id
        assert reclaimed.fencing_token == lease.fencing_token + 1
        assert await complete_ingestion_job(
            session,
            lease=reclaimed,
            now=expired_at + dt.timedelta(seconds=2),
        )
        await session.commit()

    job = await _job(job_id)
    assert job.status == "succeeded"
    assert job.fencing_token == lease.fencing_token + 1


@pytest.mark.asyncio
async def test_service_rejects_unsafe_runtime_arguments() -> None:
    async with SESSION_FACTORY() as session:
        with pytest.raises(ValueError, match="worker_id"):
            await claim_next_ingestion_job(
                session,
                job_type=TEST_JOB_TYPE,
                worker_id=" ",
                now=NOW,
                lease_duration=dt.timedelta(seconds=1),
            )
        with pytest.raises(ValueError, match="job_type"):
            await claim_next_ingestion_job(
                session,
                job_type=TEST_JOB_TYPE,
                worker_id="valid-worker",
                now=NOW,
                lease_duration=dt.timedelta(seconds=1),
                job_type=" " + ("x" * 32),
            )
        with pytest.raises(ValueError, match="lease_duration"):
            await claim_next_ingestion_job(
                session,
                job_type=TEST_JOB_TYPE,
                worker_id="valid-worker",
                now=NOW,
                lease_duration=dt.timedelta(0),
            )
        with pytest.raises(ValueError, match="timezone-aware"):
            await claim_next_ingestion_job(
                session,
                job_type=TEST_JOB_TYPE,
                worker_id="valid-worker",
                now=dt.datetime(2026, 11, 12),
                lease_duration=dt.timedelta(seconds=1),
            )
