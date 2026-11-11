"""Slice 3 PostgreSQL + Redis integration tests: outbox publisher & reconciliation.

Synthetic events only. Uses the disposable `darsyar_test` database (real
PostgreSQL, no SQLite) and a dedicated isolated Redis queue namespace
(`arq:queue:ingestion`). Only test-owned Redis keys are cleaned; nothing is
flushed and the general application Worker queue is never touched.
"""

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.models.ingestion_document import IngestionDocument
from app.models.ingestion_job import IngestionJob
from app.models.outbox_event import OutboxEvent
from app.services.outbox_publisher import (
    INGESTION_EVENT_FUNCTION,
    INGESTION_EVENT_QUEUE,
    OutboxPublishCommitError,
    _arq_job_id,
    publish_pending_outbox_events,
)
from app.services.outbox_reconciliation import reconcile_pending_outbox_events
from arq.connections import RedisSettings, create_pool
from redis.exceptions import RedisError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)
TEST_REDIS_URL = os.environ.get("REDIS_TEST_URL", "redis://localhost:6379/15")

_TRACKED_ARQ_JOB_IDS: list[str] = []


def _hex() -> str:
    return uuid.uuid4().hex * 4


async def _doc(session: AsyncSession) -> IngestionDocument:
    d = IngestionDocument(checksum=_hex()[:64], edition_year=1405, subject="math", grade_level=2)
    session.add(d)
    await session.commit()
    return d


async def _job(session: AsyncSession, doc_id: uuid.UUID, key: str) -> IngestionJob:
    job = IngestionJob(
        job_type="pdf",
        status="queued",
        document_id=doc_id,
        request_idempotency_key=key,
        request_hash="h",
    )
    session.add(job)
    await session.flush()
    return job


async def _outbox(
    session: AsyncSession,
    job: IngestionJob,
    *,
    event_type: str = "ingestion_create",
    schema_version: int = 1,
    state: str = "pending",
) -> OutboxEvent:
    ev = OutboxEvent(
        event_type=event_type,
        schema_version=schema_version,
        job_id=job.id,
        dedup_key=f"create:{job.id}",
        payload={"job_id": str(job.id), "job_type": job.job_type, "schema_version": schema_version},
        publication_state=state,
    )
    session.add(ev)
    await session.commit()
    _TRACKED_ARQ_JOB_IDS.append(_arq_job_id(ev.dedup_key))
    return ev


async def _event_state(session: AsyncSession, event_id: uuid.UUID) -> OutboxEvent | None:
    result = await session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
    return result.scalar_one_or_none()


async def _queue_member(redis, arq_job_id: str) -> float | None:
    return await redis.zscore(INGESTION_EVENT_QUEUE, arq_job_id)


class BrokenRedis:
    """Simulates Redis being unavailable: every enqueue raises."""

    async def enqueue_job(self, *args: object, **kwargs: object):
        raise RedisError("simulated redis outage")


@pytest_asyncio.fixture(autouse=True)
async def _clean_synthetic_tables() -> None:
    async with SESSION_FACTORY() as s:
        await s.execute(text("TRUNCATE outbox_events, ingestion_jobs, ingestion_chunks, ingestion_documents"))
        await s.commit()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_redis_keys() -> None:
    yield
    if not _TRACKED_ARQ_JOB_IDS:
        return
    pool = await create_pool(RedisSettings.from_dsn(TEST_REDIS_URL))
    try:
        await pool.zrem(INGESTION_EVENT_QUEUE, *_TRACKED_ARQ_JOB_IDS)
        for job_id in _TRACKED_ARQ_JOB_IDS:
            await pool.delete(f"arq:job:{job_id}", f"arq:result:{job_id}")
    finally:
        await pool.aclose()


@pytest_asyncio.fixture
async def redis_pool():
    pool = await create_pool(RedisSettings.from_dsn(TEST_REDIS_URL))
    try:
        yield pool
    finally:
        await pool.aclose()


async def _publish(session: AsyncSession, redis, batch_size: int = 20):
    return await publish_pending_outbox_events(session, redis, batch_size=batch_size)


async def _reconcile(session: AsyncSession, redis, batch_size: int = 20):
    return await reconcile_pending_outbox_events(session, redis, batch_size=batch_size)


@pytest.mark.asyncio
async def test_one_pending_event_is_discovered_and_published(redis_pool) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-publish")
        ev = await _outbox(s, job)
        res = await _publish(s, redis_pool)
        assert res.published == 1 and res.deferred == 0 and res.failed == 0
        after = await _event_state(s, ev.id)
        assert after is not None
        assert after.publication_state == "published"
        assert after.published_at is not None
        assert after.attempt_count == 1
        assert await _queue_member(redis_pool, _arq_job_id(ev.dedup_key)) is not None


@pytest.mark.asyncio
async def test_successful_enqueue_is_followed_by_publication_state_commit(redis_pool) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-commit")
        ev = await _outbox(s, job)
        res = await _publish(s, redis_pool)
        assert res.published == 1
        after = await _event_state(s, ev.id)
        assert after is not None and after.publication_state == "published"
        assert await _queue_member(redis_pool, _arq_job_id(ev.dedup_key)) is not None


@pytest.mark.asyncio
async def test_reconciliation_does_not_republish_completed_events(redis_pool) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-recon")
        ev = await _outbox(s, job)
        res1 = await _publish(s, redis_pool)
        assert res1.published == 1
        before = await _queue_member(redis_pool, _arq_job_id(ev.dedup_key))
        res2 = await _reconcile(s, redis_pool)
        assert res2.published == 0
        after = await _queue_member(redis_pool, _arq_job_id(ev.dedup_key))
        assert after == before
        state = await _event_state(s, ev.id)
        assert state is not None and state.publication_state == "published"


@pytest.mark.asyncio
async def test_stable_dedup_yields_stable_arq_job_id() -> None:
    dedup = f"create:{uuid.uuid4()}"
    assert _arq_job_id(dedup) == _arq_job_id(dedup)
    assert _arq_job_id(dedup).startswith("ingestion:")
    other = f"create:{uuid.uuid4()}"
    assert _arq_job_id(dedup) != _arq_job_id(other)


@pytest.mark.asyncio
async def test_redis_unavailable_leaves_event_recoverable(redis_pool) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-redisdown")
        ev = await _outbox(s, job)
        res = await _publish(s, BrokenRedis())
        assert res.deferred == 1 and res.published == 0

    async with SESSION_FACTORY() as s2:
        after = await _event_state(s2, ev.id)
        assert after is not None and after.publication_state == "pending"
        assert after.attempt_count == 1
        assert after.last_error_details
        assert await _queue_member(redis_pool, _arq_job_id(ev.dedup_key)) is None
        # recoverable via reconciliation with the healthy pool
        res2 = await _reconcile(s2, redis_pool)
        assert res2.published == 1
        final = await _event_state(s2, ev.id)
        assert final.publication_state == "published"
        assert await _queue_member(redis_pool, _arq_job_id(ev.dedup_key)) is not None


@pytest.mark.asyncio
async def test_pg_commit_failure_does_not_report_false_success(redis_pool, monkeypatch) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-pgdown")
        ev = await _outbox(s, job)

    async def _boom(self) -> None:
        raise ConnectionError("simulated db commit failure")

    monkeypatch.setattr(AsyncSession, "commit", _boom)
    async with SESSION_FACTORY() as s:
        with pytest.raises(OutboxPublishCommitError):
            await _publish(s, redis_pool)
    monkeypatch.undo()

    async with SESSION_FACTORY() as s:
        after = await _event_state(s, ev.id)
        assert after is not None and after.publication_state == "pending"
        res = await _reconcile(s, redis_pool)
        assert res.published == 1
        final = await _event_state(s, ev.id)
        assert final.publication_state == "published"
        assert await _queue_member(redis_pool, _arq_job_id(ev.dedup_key)) is not None


@pytest.mark.asyncio
async def test_enqueue_success_then_db_commit_failure_is_recoverable(redis_pool, monkeypatch) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-commitfail")
        ev = await _outbox(s, job)

    async def _boom(self) -> None:
        raise ConnectionError("simulated db commit failure")

    monkeypatch.setattr(AsyncSession, "commit", _boom)
    async with SESSION_FACTORY() as s:
        with pytest.raises(OutboxPublishCommitError):
            await _publish(s, redis_pool)
    monkeypatch.undo()

    async with SESSION_FACTORY() as s:
        arq_id = _arq_job_id(ev.dedup_key)
        assert await _queue_member(redis_pool, arq_id) is not None
        res = await _reconcile(s, redis_pool)
        assert res.published == 1
        members = await redis_pool.zrange(INGESTION_EVENT_QUEUE, 0, -1)
        assert members.count(arq_id.encode()) == 1


@pytest.mark.asyncio
async def test_duplicate_delivery_is_tolerated(redis_pool) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-dup")
        ev = await _outbox(s, job)
        arq_id = _arq_job_id(ev.dedup_key)
        # simulate a prior enqueue that succeeded but whose DB commit was lost
        await redis_pool.enqueue_job(
            INGESTION_EVENT_FUNCTION,
            _job_id=arq_id,
            _queue_name=INGESTION_EVENT_QUEUE,
            event_id=str(ev.id),
            job_id=str(job.id),
            dedup_key=ev.dedup_key,
            event_type=ev.event_type,
            schema_version=ev.schema_version,
            contract_version=1,
        )
        res = await _publish(s, redis_pool)
        assert res.published == 1
        members = await redis_pool.zrange(INGESTION_EVENT_QUEUE, 0, -1)
        assert members.count(arq_id.encode()) == 1


@pytest.mark.asyncio
async def test_concurrent_publishers_safely_coordinate(redis_pool) -> None:
    events: list[tuple[str, uuid.UUID]] = []
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        for i in range(6):
            job = await _job(s, doc.id, f"k-conc-{i}")
            ev = await _outbox(s, job)
            events.append((_arq_job_id(ev.dedup_key), ev.id))

    async def one() -> int:
        async with SESSION_FACTORY() as s:
            res = await _publish(s, redis_pool, batch_size=20)
            return res.published

    published = await asyncio.gather(one(), one())
    assert sum(published) == 6

    async with SESSION_FACTORY() as s:
        states = [await _event_state(s, eid) for _, eid in events]
        assert all(st is not None and st.publication_state == "published" for st in states)
    members = await redis_pool.zrange(INGESTION_EVENT_QUEUE, 0, -1)
    assert len(set(members)) == len(members)
    for arq_id, _ in events:
        assert arq_id.encode() in members


@pytest.mark.asyncio
async def test_published_events_do_not_return_to_pending(redis_pool) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-final")
        ev = await _outbox(s, job)
        res = await _publish(s, redis_pool)
        assert res.published == 1
        res2 = await _reconcile(s, redis_pool)
        assert res2.published == 0
        after = await _event_state(s, ev.id)
        assert after is not None and after.publication_state == "published"


@pytest.mark.asyncio
async def test_malformed_unsupported_contract_fails_safely(redis_pool) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-bad")
        ev = await _outbox(s, job, event_type="unsupported_type")
        res = await _publish(s, redis_pool)
        assert res.failed == 1 and res.published == 0
        after = await _event_state(s, ev.id)
        assert after is not None and after.publication_state == "failed"
        assert await _queue_member(redis_pool, _arq_job_id(ev.dedup_key)) is None


@pytest.mark.asyncio
async def test_no_job_or_outbox_deletion(redis_pool) -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-nodel")
        ev = await _outbox(s, job)
        before = await s.execute(text("SELECT count(*) FROM outbox_events"))
        before_jobs = await s.execute(text("SELECT count(*) FROM ingestion_jobs"))
        res = await _publish(s, redis_pool)
        assert res.published == 1
        res2 = await _reconcile(s, redis_pool)
        assert res2.published == 0
        after = await s.execute(text("SELECT count(*) FROM outbox_events"))
        after_jobs = await s.execute(text("SELECT count(*) FROM ingestion_jobs"))
        assert before.scalar() == after.scalar()
        assert before_jobs.scalar() == after_jobs.scalar()
        state = await _event_state(s, ev.id)
        assert state is not None and state.publication_state == "published"


@pytest.mark.asyncio
async def test_existing_application_worker_functions_unchanged() -> None:
    from app.services.worker import WorkerSettings

    function_names = [f.__name__ for f in WorkerSettings.functions]
    assert function_names == ["worker_probe"]
    cron_names = [c.name for c in WorkerSettings.cron_jobs]
    assert cron_names == ["release-stale-reservations", "recover-orphan-stream-messages"]
    assert INGESTION_EVENT_QUEUE != "arq:queue"
    assert not any("ingestion" in name for name in function_names)
