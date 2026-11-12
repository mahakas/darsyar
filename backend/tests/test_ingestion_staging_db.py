"""Synthetic tests for fenced staging, integrity and immutable artifact publication."""

import datetime as dt
import hashlib
import os
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.core.metrics import METRICS
from app.models.ingestion_document import IngestionDocument
from app.services.ingestion_creation import create_ingestion_job
from app.services.ingestion_jobs import IngestionJobLease, claim_next_ingestion_job
from app.services.ingestion_staging import (
    ArtifactMetadata,
    StagingArtifactError,
    StagingArtifactStore,
    StaleArtifactAttemptError,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)


async def _new_lease() -> tuple[IngestionJobLease, dt.datetime, str]:
    job_type = f"staging_{uuid.uuid4().hex[:16]}"
    now = dt.datetime.now(dt.UTC)
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
        created.job.retry_available_at = now - dt.timedelta(seconds=1)
        await session.commit()
        job_id = created.job.id

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
    return lease, now, job_type


def test_stage_verify_and_explicit_max_bytes(tmp_path: Path) -> None:
    store = StagingArtifactStore(tmp_path / "artifacts")
    job_id = uuid.uuid4()
    data = b"synthetic-artifact"
    before_staged = METRICS.ingestion_artifact_operation_attempts.snapshot().get(
        (("operation", "stage"), ("outcome", "success")), 0
    )
    before_verified = METRICS.ingestion_artifact_operation_attempts.snapshot().get(
        (("operation", "verify"), ("outcome", "success")), 0
    )
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
    assert METRICS.ingestion_artifact_operation_attempts.snapshot()[
        (("operation", "stage"), ("outcome", "success"))
    ] == before_staged + 1
    assert METRICS.ingestion_artifact_operation_attempts.snapshot()[
        (("operation", "verify"), ("outcome", "success"))
    ] == before_verified + 1

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


def test_verify_rejects_symlinked_attempt_directory_even_inside_root(tmp_path: Path) -> None:
    store = StagingArtifactStore(tmp_path / "artifacts")
    job_id = uuid.uuid4()
    other_job_id = uuid.uuid4()
    fencing_token = 1
    target = store.root / "staging" / str(other_job_id) / str(fencing_token)
    target.mkdir(parents=True)
    data = b"other-attempt"
    (target / "same-name.bin").write_bytes(data)
    alias = store.root / "staging" / str(job_id)
    alias.symlink_to(store.root / "staging" / str(other_job_id), target_is_directory=True)
    metadata = ArtifactMetadata(
        job_id=job_id,
        fencing_token=fencing_token,
        artifact_name="same-name.bin",
        relative_path=f"staging/{job_id}/{fencing_token}/same-name.bin",
        byte_length=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        media_type="application/octet-stream",
    )

    with pytest.raises(StagingArtifactError, match="symlink"):
        store.verify_artifact(metadata, max_bytes=64)


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
    lease, now, job_type = await _new_lease()
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
async def test_stale_fenced_attempt_cannot_publish_after_reclaim(tmp_path: Path) -> None:
    lease, _now, job_type = await _new_lease()
    store = StagingArtifactStore(tmp_path / "artifacts")
    metadata = store.stage_artifact(
        job_id=lease.job_id,
        fencing_token=lease.fencing_token,
        artifact_name="old-attempt.json",
        data=b"stale",
        media_type="application/json",
        max_bytes=64,
    )
    reclaim_at = lease.lease_expires_at + dt.timedelta(microseconds=1)
    async with SESSION_FACTORY() as session:
        replacement = await claim_next_ingestion_job(
            session,
            job_type=job_type,
            worker_id="replacement-worker",
            now=reclaim_at,
            lease_duration=dt.timedelta(minutes=2),
        )
        assert replacement is not None
        assert replacement.job_id == lease.job_id
        assert replacement.fencing_token == lease.fencing_token + 1
        await session.commit()

    async with SESSION_FACTORY() as session:
        with pytest.raises(StaleArtifactAttemptError, match="stale"):
            await store.publish_staged_artifact(
                session,
                lease=lease,
                metadata=metadata,
                now=reclaim_at,
                max_bytes=64,
            )
        await session.rollback()

    assert not (store.root / "published" / str(lease.job_id) / str(lease.fencing_token)).exists()


def test_attempt_directory_symlink_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    store = StagingArtifactStore(root)
    outside = tmp_path / "outside"
    outside.mkdir()
    staging = root / "staging"
    staging.mkdir()
    job_parent = staging / str(uuid.uuid4())
    job_parent.symlink_to(outside, target_is_directory=True)

    with pytest.raises(StagingArtifactError, match="symlink"):
        store.stage_artifact(
            job_id=uuid.UUID(job_parent.name),
            fencing_token=1,
            artifact_name="escape.bin",
            data=b"no",
            media_type="application/octet-stream",
            max_bytes=8,
        )


@pytest.mark.asyncio
async def test_expired_lease_cannot_publish_and_rollback_orphan_can_be_discarded(tmp_path: Path) -> None:
    lease, now, _job_type = await _new_lease()
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
