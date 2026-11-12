"""Synthetic tests for fenced staging, integrity and immutable artifact publication."""

import datetime as dt
import hashlib
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.models.ingestion_document import IngestionDocument
from app.services.ingestion_creation import create_ingestion_job
from app.services.ingestion_jobs import claim_next_ingestion_job
from app.services.ingestion_staging import (
    ArtifactMetadata,
    StagingArtifactError,
    StagingArtifactStore,
    StaleArtifactAttemptError,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    __import__("os").environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)


async def _new_lease():
    job_type = f"staging_{uuid.uuid4().hex[:16]}"
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
            request_idempotency_key=f"staging-{uuid.uuid4().hex}",
            job_type=job_type,
            request_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        )
        await session.commit()
        job_id = created.job.id

    now = dt.datetime.now(dt.UTC)
    async with SESSION_FACTORY() as session:
        lease = await claim_next_ingestion_job(
            session,
            job_type=job_type,
            worker_id="staging-test-worker",
            now=now,
            lease_duration=dt.timedelta(minutes=2),
        )
        assert lease is not None and lease.job_id == job_id
        await session.commit()
    return lease, now


def test_stage_verify_and_explicit_max_bytes(tmp_path: Path) -> None:
    store = StagingArtifactStore(tmp_path / "artifacts")
    job_id = uuid.uuid4()
    data = b"synthetic-artifact"
    metadata = store.stage_artifact(
        job_id=job_id,
        fencing_token=1,
        artifact_name="pages.json",
        data=data,
        media_type="application/json",
        max_bytes=128,
        expected_sha256=hashlib.sha256(data).hexdigest(),
    )
    assert metadata.byte_length == len(data)
    assert metadata.sha256 == hashlib.sha256(data).hexdigest()
    assert store.verify_artifact(metadata, max_bytes=128) == metadata

    with pytest.raises(StagingArtifactError, match="max_bytes"):
        store.stage_artifact(
            job_id=uuid.uuid4(),
            fencing_token=1,
            artifact_name="too-large.bin",
            data=b"x" * 9,
            media_type="application/octet-stream",
            max_bytes=8,
        )


@pytest.mark.parametrize("name", ["../escape", "folder/file.pdf", ".hidden", "bad\\name", ""])
def test_artifact_name_rejects_path_syntax(tmp_path: Path, name: str) -> None:
    store = StagingArtifactStore(tmp_path / "artifacts")
    with pytest.raises(StagingArtifactError, match="artifact_name"):
        store.stage_artifact(
            job_id=uuid.uuid4(),
            fencing_token=1,
            artifact_name=name,
            data=b"x",
            media_type="application/octet-stream",
            max_bytes=8,
        )


def test_rejects_checksum_mismatch_and_immutable_overwrite(tmp_path: Path) -> None:
    store = StagingArtifactStore(tmp_path / "artifacts")
    job_id = uuid.uuid4()
    with pytest.raises(StagingArtifactError, match="checksum"):
        store.stage_artifact(
            job_id=job_id,
            fencing_token=1,
            artifact_name="page.bin",
            data=b"one",
            media_type="application/octet-stream",
            max_bytes=8,
            expected_sha256="0" * 64,
        )
    metadata = store.stage_artifact(
        job_id=job_id,
        fencing_token=1,
        artifact_name="page.bin",
        data=b"one",
        media_type="application/octet-stream",
        max_bytes=8,
    )
    with pytest.raises(StagingArtifactError, match="already exists"):
        store.stage_artifact(
            job_id=job_id,
            fencing_token=1,
            artifact_name="page.bin",
            data=b"two",
            media_type="application/octet-stream",
            max_bytes=8,
        )
    path = store.root / metadata.relative_path
    path.write_bytes(b"tampered")
    with pytest.raises(StagingArtifactError, match="byte_length|checksum"):
        store.verify_artifact(metadata, max_bytes=8)


def test_metadata_path_must_match_attempt_and_name(tmp_path: Path) -> None:
    store = StagingArtifactStore(tmp_path / "artifacts")
    metadata = ArtifactMetadata(
        job_id=uuid.uuid4(),
        fencing_token=2,
        artifact_name="one.bin",
        relative_path="staging/../../escape",
        byte_length=1,
        sha256=hashlib.sha256(b"x").hexdigest(),
        media_type="application/octet-stream",
    )
    with pytest.raises(StagingArtifactError, match="relative_path"):
        store.verify_artifact(metadata, max_bytes=8)


def test_discard_attempt_is_idempotent_and_scoped(tmp_path: Path) -> None:
    store = StagingArtifactStore(tmp_path / "artifacts")
    job_id = uuid.uuid4()
    metadata = store.stage_artifact(
        job_id=job_id,
        fencing_token=4,
        artifact_name="result.json",
        data=b"{}",
        media_type="application/json",
        max_bytes=16,
    )
    store.discard_attempt(job_id=job_id, fencing_token=4, remove_published=False)
    store.discard_attempt(job_id=job_id, fencing_token=4, remove_published=False)
    assert not (store.root / metadata.relative_path).exists()
    assert store.root.exists()


@pytest.mark.asyncio
async def test_publish_requires_current_live_fenced_lease_and_is_idempotent(tmp_path: Path) -> None:
    lease, now = await _new_lease()
    store = StagingArtifactStore(tmp_path / "artifacts")
    metadata = store.stage_artifact(
        job_id=lease.job_id,
        fencing_token=lease.fencing_token,
        artifact_name="synthetic-manifest.json",
        data=b'{"pages":1}',
        media_type="application/json",
        max_bytes=128,
    )
    async with SESSION_FACTORY() as session:
        published = await store.publish_staged_artifact(
            session, lease=lease, metadata=metadata, now=now, max_bytes=128
        )
        await session.commit()
    assert published.relative_path.startswith("published/")
    assert store.verify_artifact(published, max_bytes=128) == published

    async with SESSION_FACTORY() as session:
        again = await store.publish_staged_artifact(
            session, lease=lease, metadata=metadata, now=now, max_bytes=128
        )
        assert again == published
        await session.rollback()

    stale = replace(lease, fencing_token=lease.fencing_token + 1)
    async with SESSION_FACTORY() as session:
        with pytest.raises(StaleArtifactAttemptError, match="metadata"):
            await store.publish_staged_artifact(
                session, lease=stale, metadata=metadata, now=now, max_bytes=128
            )
        await session.rollback()


@pytest.mark.asyncio
async def test_expired_lease_cannot_publish_and_rollback_orphan_can_be_discarded(tmp_path: Path) -> None:
    lease, now = await _new_lease()
    store = StagingArtifactStore(tmp_path / "artifacts")
    metadata = store.stage_artifact(
        job_id=lease.job_id,
        fencing_token=lease.fencing_token,
        artifact_name="artifact.bin",
        data=b"synthetic",
        media_type="application/octet-stream",
        max_bytes=64,
    )
    async with SESSION_FACTORY() as session:
        with pytest.raises(StaleArtifactAttemptError, match="stale"):
            await store.publish_staged_artifact(
                session,
                lease=lease,
                metadata=metadata,
                now=lease.lease_expires_at + dt.timedelta(microseconds=1),
                max_bytes=64,
            )
        await session.rollback()

    async with SESSION_FACTORY() as session:
        published = await store.publish_staged_artifact(
            session, lease=lease, metadata=metadata, now=now, max_bytes=64
        )
        await session.rollback()
    assert store.verify_artifact(published, max_bytes=64) == published
    store.discard_attempt(
        job_id=lease.job_id,
        fencing_token=lease.fencing_token,
        remove_published=True,
    )
    store.discard_attempt(
        job_id=lease.job_id,
        fencing_token=lease.fencing_token,
        remove_published=True,
    )
    with pytest.raises(StagingArtifactError):
        store.verify_artifact(published, max_bytes=64)
