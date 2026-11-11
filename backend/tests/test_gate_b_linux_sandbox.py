"""Gate B-S2 — Linux OS-level sandbox prototype tests (synthetic-only).

These tests exercise OS-level enforcement provided by the restricted sandbox
container (see `backend/tests/sandbox/Dockerfile.sandbox`). On a host where the
container fences are absent, enforcement probes are marked `NOT_TESTED` (skipped
with reason) rather than weakened.

No pilot PDF, no rendering/extraction, no network to external services, no
database/Redis, no PDFium.
"""

from __future__ import annotations

import os
import zlib

import pytest
from app.services.ingestion.linux_sandbox import (
    is_linux,
    probe_cpu_quota,
    probe_docker_socket_absent,
    probe_filesystem_readonly,
    probe_host_secrets_unreadable,
    probe_memory_exhaustion,
    probe_network_isolation,
    probe_process_limit,
    run_sandboxed_child,
    sandbox_probe_active,
)
from app.services.ingestion.parent_child_contract import (
    PARENT_CHILD_CONTRACT_VERSION,
    ChildErrorCategory,
    ChildProcessingOutcome,
    ParentChildRequest,
)
from app.services.ingestion.parent_supervisor import FORBIDDEN_ENV_FRAGMENTS

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED_PYPDF = "6.21.3"

ENFORCEMENT_AVAILABLE = is_linux() and sandbox_probe_active()

pytestmark = pytest.mark.skipif(
    not ENFORCEMENT_AVAILABLE,
    reason="Linux sandbox enforcement requires the restricted Linux container (DARSYAR_SANDBOX_PROBE=1)",
)


def _compressed_pdf(payload: bytes | None = None) -> bytes:
    raw = payload or b"BT /F1 12 Tf 72 720 Td (sandbox child) Tj ET"
    compressed = zlib.compress(raw)

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
    body = b"%PDF-1.4\n% synthetic\n" + catalog + pages + page + stream
    offsets = [0]
    pos = 0
    for part in (catalog, pages, page, stream):
        offsets.append(pos)
        pos += len(part)
    xref = b"xref\n0 5\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = b"trailer\n<< /Root 1 0 R /Size 5 >>\nstartxref\n" + str(len(body) + len(xref)).encode() + b"\n%%EOF\n"
    return body + xref + trailer


def _request(document: bytes, mode: str = "normal") -> ParentChildRequest:
    return ParentChildRequest(
        contract_version=PARENT_CHILD_CONTRACT_VERSION,
        attempt_id="s2-linux",
        document_bytes=document,
        limits={"zlib_maximum_output_length": 5000},
        mode=mode,
    )


# --- 1. Network isolation ---
def test_network_isolation_blocked() -> None:
    r = probe_network_isolation()
    assert r.enforced, r.detail


# --- 2. Filesystem isolation ---
def test_filesystem_readonly_enforced() -> None:
    r = probe_filesystem_readonly()
    assert r.enforced, r.detail


def test_docker_socket_not_exposed() -> None:
    r = probe_docker_socket_absent()
    assert r.enforced, r.detail


def test_host_secrets_not_readable() -> None:
    r = probe_host_secrets_unreadable()
    assert r.enforced, r.detail


# --- 3. Resource limits ---
def test_memory_limit_enforced() -> None:
    # Probe attempts an allocation well above the container's hard memory limit.
    r = probe_memory_exhaustion(2048)
    assert r.enforced, r.detail


def test_cpu_quota_applied() -> None:
    r = probe_cpu_quota(2_000_000)
    assert r.enforced, r.detail
    assert r.detail.startswith("busy loop completed")


def test_pid_limit_enforced() -> None:
    r = probe_process_limit(200)
    assert r.enforced, r.detail


# --- 4. Parent/Child IPC + synthetic PDF behavior inside sandbox ---
def test_sandboxed_child_parses_synthetic_pdf() -> None:
    run = run_sandboxed_child(_request(_compressed_pdf()), timeout_seconds=20)
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.SUCCESS
    assert run.result.pypdf_version == EXPECTED_PYPDF
    assert run.result.page_count == 1


def test_sandboxed_child_rejects_malformed() -> None:
    malformed = b"%PDF-1.4\n" + b"garbage" * 200 + b"%%EOF\n"
    run = run_sandboxed_child(_request(malformed, mode="decode_stream"), timeout_seconds=20)
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.FAILED
    assert run.result.error_category in (ChildErrorCategory.MALFORMED, ChildErrorCategory.TRUNCATED)


def test_sandboxed_child_rejects_oversized_synthetic_stream() -> None:
    run = run_sandboxed_child(
        _request(_compressed_pdf(b"Z" * 8000), mode="decode_stream"),
        timeout_seconds=20,
    )
    assert run.ok
    assert run.result is not None
    assert run.result.error_category is ChildErrorCategory.RESOURCE_LIMIT


def test_sandboxed_child_timeout_and_forced_termination() -> None:
    run = run_sandboxed_child(_request(b"", mode="hang"), timeout_seconds=1)
    assert not run.ok
    assert run.timed_out
    assert run.terminated


def test_sandbox_parent_recovers_after_child_failure() -> None:
    first = run_sandboxed_child(_request(b"", mode="hang"), timeout_seconds=1)
    assert first.timed_out
    second = run_sandboxed_child(_request(_compressed_pdf()), timeout_seconds=20)
    assert second.ok
    assert second.result is not None
    assert second.result.outcome is ChildProcessingOutcome.SUCCESS


def test_sandboxed_child_env_allowlist_excludes_sentinels() -> None:
    sentinels = {"DATABASE_URL": "postgres://u:p@db/app", "SECRET_TOKEN": "s3cr3t"}
    os.environ.update(sentinels)
    try:
        run = run_sandboxed_child(_request(_compressed_pdf()), timeout_seconds=20)
    finally:
        for k in sentinels:
            os.environ.pop(k, None)
    assert run.ok
    assert run.forbidden_env_seen == []
    for frag in FORBIDDEN_ENV_FRAGMENTS:
        assert not any(frag in k.upper() for k in run.forbidden_env_seen)
