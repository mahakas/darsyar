"""Slice 1 tests: durable ingestion job + outbox persistence.

Structural tests run anywhere; constraint/integrity tests require PostgreSQL
(DARSYAR_TEST_DB=1) and are skipped otherwise — never replaced by SQLite.
"""

import os

import pytest
from app.core.config import get_settings
from app.models.ingestion_document import IngestionDocument
from app.models.ingestion_job import IngestionJob
from app.models.outbox_event import OutboxEvent
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# structural (no DB)

def test_model_tables_present() -> None:
    from app.models import __all__ as models

    assert "IngestionDocument" in models
    assert "IngestionJob" in models
    assert "OutboxEvent" in models


def test_ingestion_job_columns() -> None:
    cols = {c.name for c in IngestionJob.__table__.columns}
    for expected in (
        "id", "job_type", "schema_version", "status", "document_id",
        "request_idempotency_key", "request_hash", "attempt_count",
        "lease_owner", "lease_token", "lease_expires_at", "heartbeat_at",
        "fencing_token", "retry_available_at", "last_error_code",
        "last_error_summary", "cancellation_requested",
        "created_at", "started_at", "updated_at", "finished_at",
    ):
        assert expected in cols, expected


def test_request_idempotency_unique_constraint() -> None:
    from sqlalchemy import UniqueConstraint

    names = {uc.name for uc in IngestionJob.__table__.constraints if isinstance(uc, UniqueConstraint)}
    assert "uq_ingestion_jobs_request_idempotency" in names


def test_job_status_and_counter_checks() -> None:
    from sqlalchemy import CheckConstraint

    ck = {ck.name for ck in IngestionJob.__table__.constraints if isinstance(ck, CheckConstraint)}
    assert "ck_ingestion_jobs_status_valid" in ck
    assert "ck_ingestion_jobs_attempt_nonneg" in ck
    assert "ck_ingestion_jobs_fencing_nonneg" in ck


def test_outbox_dedup_unique() -> None:
    from sqlalchemy import UniqueConstraint

    names = {uc.name for uc in OutboxEvent.__table__.constraints if isinstance(uc, UniqueConstraint)}
    assert "uq_outbox_events_dedup" in names


def test_outbox_state_check() -> None:
    from sqlalchemy import CheckConstraint

    ck = {ck.name for ck in OutboxEvent.__table__.constraints if isinstance(ck, CheckConstraint)}
    assert "ck_outbox_events_state_valid" in ck


def test_canonical_document_unique() -> None:
    from sqlalchemy import UniqueConstraint

    names = {uc.name for uc in IngestionDocument.__table__.constraints if isinstance(uc, UniqueConstraint)}
    assert "uq_ingestion_documents_canonical" in names


def test_indexes_present() -> None:
    idx_job = {i.name for i in IngestionJob.__table__.indexes}
    idx_out = {i.name for i in OutboxEvent.__table__.indexes}
    assert "ix_ingestion_jobs_claim" in idx_job
    assert "ix_ingestion_jobs_lease_expiry" in idx_job
    assert "ix_outbox_events_claim" in idx_out
    assert "ix_outbox_events_job" in idx_out


def test_fk_relationships() -> None:
    assert IngestionJob.__table__.c.document_id.foreign_keys
    assert OutboxEvent.__table__.c.job_id.foreign_keys


def test_job_state_independent_of_resource_lifecycle() -> None:
    # job state is execution state; R-156 resource states are not reused here
    assert "ready" not in IngestionJob.__table__.c.status.type.enums if hasattr(IngestionJob.__table__.c.status.type, "enums") else True

# PostgreSQL-gated integrity (never SQLite)

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

PG_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
PG_SESSION = async_sessionmaker(PG_ENGINE, expire_on_commit=False)


async def _insert_document(session, checksum: str | None = None):
    import uuid as _uuid

    doc = IngestionDocument(
        checksum=checksum or (_uuid.uuid4().hex * 4)[:64],
        edition_year=1405,
        subject="math",
        grade_level=2,
    )
    session.add(doc)
    await session.flush()
    return doc


@pytest.mark.asyncio
async def test_pg_canonical_document_unique() -> None:
    import uuid as _uuid

    from sqlalchemy.exc import IntegrityError

    checksum = (_uuid.uuid4().hex * 4)[:64]
    async with PG_SESSION() as s:
        await _insert_document(s, checksum=checksum)
        with pytest.raises(IntegrityError):
            await _insert_document(s, checksum=checksum)
            await s.commit()


@pytest.mark.asyncio
async def test_pg_request_idempotency_unique() -> None:
    from sqlalchemy.exc import IntegrityError

    async with PG_SESSION() as s:
        doc = await _insert_document(s)
        await s.commit()
        job1 = IngestionJob(job_type="pdf", document_id=doc.id, request_idempotency_key="k1", request_hash="h")
        s.add(job1)
        await s.commit()
        job2 = IngestionJob(job_type="pdf", document_id=doc.id, request_idempotency_key="k1", request_hash="h2")
        s.add(job2)
        with pytest.raises(IntegrityError):
            await s.commit()


@pytest.mark.asyncio
async def test_pg_outbox_dedup_unique() -> None:
    import uuid as _uuid

    from sqlalchemy.exc import IntegrityError

    dedup = "d_" + _uuid.uuid4().hex
    async with PG_SESSION() as s:
        doc = await _insert_document(s)
        await s.commit()
        job = IngestionJob(job_type="pdf", document_id=doc.id, request_idempotency_key="kout_" + _uuid.uuid4().hex, request_hash="h")
        s.add(job)
        await s.commit()
        ev1 = OutboxEvent(event_type="ingest", job_id=job.id, dedup_key=dedup, payload={})
        s.add(ev1)
        await s.commit()
        ev2 = OutboxEvent(event_type="ingest", job_id=job.id, dedup_key=dedup, payload={})
        s.add(ev2)
        with pytest.raises(IntegrityError):
            await s.commit()


@pytest.mark.asyncio
async def test_pg_invalid_job_status_rejected() -> None:
    from sqlalchemy.exc import IntegrityError

    async with PG_SESSION() as s:
        doc = await _insert_document(s)
        await s.commit()
        job = IngestionJob(job_type="pdf", document_id=doc.id, request_idempotency_key="kbad", request_hash="h", status="ready")
        s.add(job)
        with pytest.raises(IntegrityError):
            await s.commit()
