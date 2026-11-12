"""Synthetic end-to-end PostgreSQL → Parent/Child → artifact publication tests.

The test PDF is built from bytes in this module. No real textbook, pilot PDF,
network, ARQ consumer, or production storage path is used.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import uuid
import zlib
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.models.ingestion_document import IngestionDocument
from app.models.ingestion_job import IngestionJob
from app.services.ingestion.parent_child_contract import (
    PARENT_CHILD_CONTRACT_VERSION,
    ChildErrorCategory,
    ChildProcessingOutcome,
    ParentChildRequest,
)
from app.services.ingestion.parent_supervisor import run_child
from app.services.ingestion_creation import create_ingestion_job
from app.services.ingestion_jobs import (
    IngestionJobLease,
    claim_next_ingestion_job,
    complete_ingestion_job,
    fail_ingestion_job,
)
from app.services.ingestion_staging import StagingArtifactStore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
SESSION_FACTORY = async_sessionmaker(ENGINE, expire_on_commit=False)
BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_PYPDF = "7.0.1"


def _synthetic_pdf(payload: bytes = b"BT /F1 12 Tf 72 720 Td (synthetic) Tj ET") -> bytes:
    """Build a minimal one-page FlateDecode PDF in memory; never reads a file."""
    compressed = zlib.compress(payload)

    def obj(body: bytes) -> bytes:
        return body + b"\nendobj\n"

    catalog = obj(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>")
    pages = obj(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    page = obj(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>")
    stream = (
        b"4 0 obj\n<< /Length "
        + str(len(compressed)).encode()
        + b" /Filter /FlateDecode >>\nstream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )
    parts = (catalog, pages, page, stream)
    header = b"%PDF-1.4\n% synthetic-e2e\n"
    body = header + b"".join(parts)
    offsets = [0]
    pos = len(header)
    for part in parts:
        offsets.append(pos)
        pos += len(part)
    xref = b"xref\n0 5\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        xref += f"{offset:010d} 00000 n \n".encode()
    trailer = (
        b"trailer\n<< /Root 1 0 R /Size 5 >>\nstartxref\n"
        + str(len(body) + len(xref)).encode()
        + b"\n%%EOF\n"
    )
    return body + xref + trailer


async def _create_claimed_job(*, now: dt.datetime, job_type: str) -> IngestionJobLease:
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
            request_idempotency_key=f"e2e-{uuid.uuid4().hex}",
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
            worker_id="synthetic-e2e-parent",
            now=now,
            lease_duration=dt.timedelta(minutes=2),
        )
        assert lease is not None
        assert lease.job_id == job_id
        await session.commit()
    return lease


@pytest.mark.asyncio
async def test_synthetic_job_child_artifact_publish_and_complete(tmp_path: Path) -> None:
    now = dt.datetime.now(dt.UTC)
    lease = await _create_claimed_job(now=now, job_type=f"e2e_{uuid.uuid4().hex[:16]}")
    pdf_bytes = _synthetic_pdf()
    request = ParentChildRequest(
        contract_version=PARENT_CHILD_CONTRACT_VERSION,
        attempt_id=str(uuid.uuid4()),
        document_bytes=pdf_bytes,
        limits={"zlib_maximum_output_length": 16_384},
        mode="normal",
    )

    child_run = run_child(request, timeout_seconds=20, cwd=str(BACKEND_DIR))
    assert child_run.ok
    assert child_run.forbidden_env_seen == []
    assert child_run.result is not None
    assert child_run.result.outcome is ChildProcessingOutcome.SUCCESS
    assert child_run.result.page_count == 1
    assert child_run.result.pypdf_version == EXPECTED_PYPDF

    # The parent writes only safe metadata; raw PDF bytes/content never enter the artifact.
    artifact_bytes = json.dumps(
        {
            "contract_version": child_run.result.contract_version,
            "attempt_id": child_run.result.attempt_id,
            "outcome": child_run.result.outcome.value,
            "page_count": child_run.result.page_count,
            "pypdf_version": child_run.result.pypdf_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    store = StagingArtifactStore(tmp_path / "synthetic-artifacts")
    metadata = store.stage_artifact(
        job_id=lease.job_id,
        fencing_token=lease.fencing_token,
        artifact_name="child-result.json",
        data=artifact_bytes,
        media_type="application/json",
        max_bytes=4096,
        expected_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
    )

    async with SESSION_FACTORY() as session:
        published = await store.publish_staged_artifact(
            session,
            lease=lease,
            metadata=metadata,
            now=now + dt.timedelta(seconds=1),
            max_bytes=4096,
        )
        assert published.relative_path.startswith("published/")
        assert await complete_ingestion_job(
            session,
            lease=lease,
            now=now + dt.timedelta(seconds=2),
        )
        await session.commit()

    assert store.verify_artifact(published, max_bytes=4096) == published
    artifact_path = store.root / published.relative_path
    assert json.loads(artifact_path.read_text(encoding="utf-8"))["page_count"] == 1
    assert pdf_bytes not in artifact_path.read_bytes()

    async with SESSION_FACTORY() as session:
        result = await session.execute(select(IngestionJob).where(IngestionJob.id == lease.job_id))
        job = result.scalar_one()
        assert job.status == "succeeded"
        assert job.fencing_token == lease.fencing_token
        assert job.lease_token is None


@pytest.mark.asyncio
async def test_synthetic_child_failure_never_publishes_an_artifact(tmp_path: Path) -> None:
    now = dt.datetime.now(dt.UTC)
    lease = await _create_claimed_job(now=now, job_type=f"e2efail_{uuid.uuid4().hex[:12]}")
    request = ParentChildRequest(
        contract_version=PARENT_CHILD_CONTRACT_VERSION,
        attempt_id=str(uuid.uuid4()),
        document_bytes=b"%PDF-1.4\n" + b"malformed-synthetic-input " * 32 + b"%%EOF\n",
        limits={"zlib_maximum_output_length": 4096},
        mode="decode_stream",
    )
    child_run = run_child(request, timeout_seconds=20, cwd=str(BACKEND_DIR))
    assert child_run.ok
    assert child_run.result is not None
    assert child_run.result.outcome is ChildProcessingOutcome.FAILED
    assert child_run.result.error_category in {
        ChildErrorCategory.MALFORMED,
        ChildErrorCategory.TRUNCATED,
    }

    store = StagingArtifactStore(tmp_path / "synthetic-artifacts")
    async with SESSION_FACTORY() as session:
        assert await fail_ingestion_job(
            session,
            lease=lease,
            now=now + dt.timedelta(seconds=1),
            error_code="child_malformed",
        )
        await session.commit()

    published_attempt = store.root / "published" / str(lease.job_id) / str(lease.fencing_token)
    assert not published_attempt.exists()
    async with SESSION_FACTORY() as session:
        result = await session.execute(select(IngestionJob).where(IngestionJob.id == lease.job_id))
        job = result.scalar_one()
        assert job.status == "terminal_failure"
        assert job.last_error_code == "child_malformed"


