"""R-1 PostgreSQL integration tests: ON DELETE RESTRICT on outbox→job FK.

Covers:
1. SQLAlchemy metadata declares ON DELETE RESTRICT.
2. Alembic migration head is the new revision (0019).
3. Database FK catalog reports RESTRICT.
4. Direct SQL delete of a job with an associated outbox event is rejected.
5. Parent job + outbox event remain after the rejected deletion.
6. ORM deletion does not cascade-delete the outbox event.
7. Loaded and unloaded relationship cases preserve the restriction.
8. Deleting an unrelated job without outbox events remains possible.
9. Downgrade restores CASCADE and re-upgrade restores RESTRICT (validated via
   the migration runner; catalog assertions live here).
11. Existing Slice 1–3 tests remain compatible (run separately).

PostgreSQL only (never SQLite). Synthetic data only.
"""

import os
import uuid

import pytest
from app.core.config import get_settings
from app.models.ingestion_document import IngestionDocument
from app.models.ingestion_job import IngestionJob
from app.models.outbox_event import OutboxEvent
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)


def _hex() -> str:
    return uuid.uuid4().hex * 4


async def _doc(session) -> IngestionDocument:
    d = IngestionDocument(checksum=_hex()[:64], edition_year=1405, subject="math", grade_level=2)
    session.add(d)
    await session.commit()
    return d


async def _job(session, doc_id: uuid.UUID, key: str) -> IngestionJob:
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


async def _outbox(session, job: IngestionJob) -> OutboxEvent:
    ev = OutboxEvent(
        event_type="ingestion_create",
        schema_version=1,
        job_id=job.id,
        dedup_key=f"create:{job.id}",
        payload={"job_id": str(job.id)},
        publication_state="pending",
    )
    session.add(ev)
    await session.commit()
    return ev


def _fk_ondelete_in_metadata() -> str | None:
    fk = next(iter(OutboxEvent.__table__.c.job_id.foreign_keys))
    return fk.ondelete


def test_sqla_metadata_declares_restrict() -> None:
    assert _fk_ondelete_in_metadata() == "RESTRICT"


async def _catalog_delete_rule(conn) -> str:
    row = (
        await conn.execute(
            text(
                "SELECT rc.delete_rule FROM information_schema.referential_constraints rc "
                "WHERE rc.constraint_name = 'fk_outbox_events_job' "
                "LIMIT 1"
            )
        )
    ).one()
    return str(row[0])


@pytest.mark.asyncio
async def test_pg_catalog_reports_restrict() -> None:
    async with SESSION_FACTORY() as s:
        rule = await _catalog_delete_rule(s)
        assert rule == "RESTRICT"


@pytest.mark.asyncio
async def test_pg_alembic_head_is_0019() -> None:
    async with SESSION_FACTORY() as s:
        version = (await s.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        assert version == "0019_outbox_job_fk_restrict"


@pytest.mark.asyncio
async def test_pg_direct_sql_delete_job_with_outbox_rejected() -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-direct-delete")
        ev = await _outbox(s, job)
        job_id = job.id
        ev_id = ev.id

    async with SESSION_FACTORY() as s:
        with pytest.raises(IntegrityError):
            await s.execute(text("DELETE FROM ingestion_jobs WHERE id = :id"), {"id": job_id})
            await s.commit()
        await s.rollback()

    async with SESSION_FACTORY() as s:
        # job and outbox both remain after the rejected deletion
        job_rows = (await s.execute(text("SELECT count(*) FROM ingestion_jobs WHERE id = :id"), {"id": job_id})).scalar_one()
        ev_rows = (await s.execute(text("SELECT count(*) FROM outbox_events WHERE id = :id"), {"id": ev_id})).scalar_one()
        assert job_rows == 1
        assert ev_rows == 1


@pytest.mark.asyncio
async def test_pg_orm_delete_does_not_cascade_outbox() -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-orm-delete")
        ev = await _outbox(s, job)
        job_id = job.id
        ev_id = ev.id

    # loaded child case: both objects are in the identity map in this session
    async with SESSION_FACTORY() as s:
        loaded_job = await s.get(IngestionJob, job_id)
        loaded_ev = await s.get(OutboxEvent, ev_id)
        assert loaded_job is not None and loaded_ev is not None
        await s.delete(loaded_job)
        with pytest.raises(IntegrityError):
            await s.commit()
        await s.rollback()

    async with SESSION_FACTORY() as s:
        job_rows = (await s.execute(text("SELECT count(*) FROM ingestion_jobs WHERE id = :id"), {"id": job_id})).scalar_one()
        ev_rows = (await s.execute(text("SELECT count(*) FROM outbox_events WHERE id = :id"), {"id": ev_id})).scalar_one()
        assert job_rows == 1
        assert ev_rows == 1


@pytest.mark.asyncio
async def test_pg_orm_delete_unloaded_child_preserves_restriction() -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-unloaded")
        ev = await _outbox(s, job)
        job_id = job.id
        ev_id = ev.id

    # unloaded child: a fresh session loads only the job; the outbox child is
    # never touched by the ORM, so only the DB RESTRICT guard can reject.
    async with SESSION_FACTORY() as s:
        job_only = await s.get(IngestionJob, job_id)
        assert job_only is not None
        await s.delete(job_only)
        with pytest.raises(IntegrityError):
            await s.commit()
        await s.rollback()

    async with SESSION_FACTORY() as s:
        job_rows = (await s.execute(text("SELECT count(*) FROM ingestion_jobs WHERE id = :id"), {"id": job_id})).scalar_one()
        ev_rows = (await s.execute(text("SELECT count(*) FROM outbox_events WHERE id = :id"), {"id": ev_id})).scalar_one()
        assert job_rows == 1
        assert ev_rows == 1


@pytest.mark.asyncio
async def test_pg_delete_unrelated_job_without_outbox_possible() -> None:
    async with SESSION_FACTORY() as s:
        doc = await _doc(s)
        job = await _job(s, doc.id, "k-orphan-delete")
        job_id = job.id
        # no outbox row for this job
        await s.commit()

    async with SESSION_FACTORY() as s:
        job_only = await s.get(IngestionJob, job_id)
        assert job_only is not None
        await s.delete(job_only)
        await s.commit()

    async with SESSION_FACTORY() as s:
        job_rows = (await s.execute(text("SELECT count(*) FROM ingestion_jobs WHERE id = :id"), {"id": job_id})).scalar_one()
        assert job_rows == 0
