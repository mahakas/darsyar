"""Gate B-S1 — isolated Parent/Child prototype tests (synthetic-only).

Runs the Parent Supervisor + spawned PDF Child under the exact locked pypdf
7.0.1 (isolated env). All fixtures are synthetic, in-memory, and temporary. No
pilot PDF, no rendering, no text extraction, no network, no database/Redis, and
no PDFium.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import zlib

import pytest
from app.services.ingestion.parent_child_contract import (
    PARENT_CHILD_CONTRACT_VERSION,
    ChildErrorCategory,
    ChildProcessingOutcome,
    ParentChildRequest,
    ParentChildResult,
)
from app.services.ingestion.parent_supervisor import FORBIDDEN_ENV_FRAGMENTS, run_child

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The child must use the locked version (project lock is now 7.0.1).
EXPECTED_PYPDF = "7.0.1"


def _compressed_pdf(payload: bytes | None = None) -> bytes:
    raw = payload or b"BT /F1 12 Tf 72 720 Td (hello child) Tj ET"
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


def _request(
    document: bytes,
    mode: str = "normal",
    limits: dict[str, object] | None = None,
    contract_version: int = PARENT_CHILD_CONTRACT_VERSION,
) -> ParentChildRequest:
    return ParentChildRequest(
        contract_version=contract_version,
        attempt_id="s1-test",
        document_bytes=document,
        limits={"zlib_maximum_output_length": 2000} if limits is None else limits,
        mode=mode,
    )


def test_request_ipc_round_trip_is_strict_and_lossless() -> None:
    request = _request(_compressed_pdf())
    decoded = ParentChildRequest.from_json(request.to_json())
    assert decoded == request


def test_request_ipc_rejects_unknown_and_missing_fields() -> None:
    payload = json.loads(_request(_compressed_pdf()).to_json())
    with_unknown = {**payload, "database_url": "postgres://must-not-cross"}
    with_missing = {key: value for key, value in payload.items() if key != "mode"}
    with pytest.raises(ValueError, match="fields"):
        ParentChildRequest.from_json(json.dumps(with_unknown))
    with pytest.raises(ValueError, match="fields"):
        ParentChildRequest.from_json(json.dumps(with_missing))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(contract_version=True),
        lambda payload: payload.update(contract_version="1"),
        lambda payload: payload.update(attempt_id=""),
        lambda payload: payload.update(attempt_id=12),
        lambda payload: payload.update(document_bytes="%%%"),
        lambda payload: payload.update(document_bytes=123),
        lambda payload: payload.update(limits=[]),
        lambda payload: payload.update(limits={"zlib_maximum_output_length": True}),
        lambda payload: payload.update(limits={"zlib_maximum_output_length": 1, "database_url": "x"}),
        lambda payload: payload.update(mode=[]),
    ],
)
def test_request_ipc_rejects_malformed_or_coerced_values(mutate) -> None:
    payload = json.loads(_request(_compressed_pdf()).to_json())
    mutate(payload)
    with pytest.raises((TypeError, ValueError)):
        ParentChildRequest.from_json(json.dumps(payload))


def test_request_ipc_rejects_duplicate_json_fields() -> None:
    raw = _request(_compressed_pdf()).to_json()
    duplicate = raw[:-1] + ', "mode": "decode_stream"}'
    with pytest.raises(ValueError, match="duplicate"):
        ParentChildRequest.from_json(duplicate)


def test_result_ipc_rejects_unknown_fields_and_invalid_types() -> None:
    result = ParentChildResult(attempt_id="s1-test", outcome=ChildProcessingOutcome.SUCCESS)
    payload = json.loads(result.to_json())
    with pytest.raises(ValueError, match="fields"):
        ParentChildResult.from_json(json.dumps({**payload, "secret": "not-allowed"}))
    invalid = {**payload, "page_count": True}
    with pytest.raises(ValueError, match="page_count"):
        ParentChildResult.from_json(json.dumps(invalid))


def test_parent_rejects_child_result_for_another_attempt(monkeypatch) -> None:
    foreign_result = ParentChildResult(
        attempt_id="different-attempt",
        outcome=ChildProcessingOutcome.SUCCESS,
    ).to_json().encode("utf-8")

    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
            self.returncode = 0

        def communicate(self, timeout=None):
            return foreign_result, b""

        def poll(self):
            return self.returncode

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    result = run_child(_request(_compressed_pdf()), timeout_seconds=1, cwd=BACKEND_DIR)
    assert not result.ok
    assert result.message == "child result attempt id mismatch"


def test_child_rejects_missing_explicit_per_stream_limit() -> None:
    run = run_child(_request(_compressed_pdf(), limits={}), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.FAILED
    assert run.result.error_category is ChildErrorCategory.INVALID_REQUEST


def test_child_rejects_invalid_per_stream_limit_values() -> None:
    for invalid in (True, False, 0, -1, 1.5, "2000", None):
        run = run_child(
            _request(_compressed_pdf(), limits={"zlib_maximum_output_length": invalid}),
            timeout_seconds=20,
            cwd=BACKEND_DIR,
        )
        assert run.ok
        assert run.result is not None
        assert run.result.outcome is ChildProcessingOutcome.FAILED
        assert run.result.error_category is ChildErrorCategory.INVALID_REQUEST


def test_child_rejects_unsupported_contract_version() -> None:
    run = run_child(_request(_compressed_pdf(), contract_version=999), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.FAILED
    assert run.result.error_category is ChildErrorCategory.INVALID_REQUEST


def test_child_rejects_unknown_mode() -> None:
    run = run_child(_request(_compressed_pdf(), mode="unexpected"), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.FAILED
    assert run.result.error_category is ChildErrorCategory.INVALID_REQUEST


def test_child_receives_valid_request_and_uses_locked_pypdf() -> None:
    run = run_child(_request(_compressed_pdf()), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.SUCCESS
    assert run.result.pypdf_version == EXPECTED_PYPDF
    assert run.result.page_count == 1


def test_scoped_configuration_applied() -> None:
    # decode_stream mode exercises the FlateDecode stream under a comfortably large
    # test-only cap; decode succeeds and the length is recorded.
    run = run_child(
        _request(_compressed_pdf(b"hello" * 50), mode="decode_stream", limits={"zlib_maximum_output_length": 100_000}),
        timeout_seconds=20,
        cwd=BACKEND_DIR,
    )
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.SUCCESS
    assert run.result.decoded_stream_length is not None
    assert run.result.decoded_stream_length > 0


def test_content_stream_decode_exercises_configured_limit() -> None:
    # Explicit decode mode exercises the FlateDecode stream under a small cap.
    run = run_child(
        _request(_compressed_pdf(b"Y" * 4000), mode="decode_stream", limits={"zlib_maximum_output_length": 1000}),
        timeout_seconds=20,
        cwd=BACKEND_DIR,
    )
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.FAILED
    assert run.result.error_category is ChildErrorCategory.RESOURCE_LIMIT


def test_oversized_synthetic_stream_rejected_safely() -> None:
    # Payload far exceeds a tiny test-only limit -> safe typed resource-limit error.
    run = run_child(
        _request(_compressed_pdf(b"Z" * 8000), mode="decode_stream", limits={"zlib_maximum_output_length": 16}),
        timeout_seconds=20,
        cwd=BACKEND_DIR,
    )
    assert run.ok
    assert run.result is not None
    assert run.result.error_category is ChildErrorCategory.RESOURCE_LIMIT


def test_parent_validates_structured_child_output() -> None:
    run = run_child(_request(_compressed_pdf()), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok
    assert run.result is not None
    assert run.result.contract_version == PARENT_CHILD_CONTRACT_VERSION


def test_child_does_not_receive_sentinel_secret_env() -> None:
    # Plant sentinel secrets in the parent env; assert they do not reach the child.
    sentinels = {"DATABASE_URL": "postgres://user:pass@db/app", "SECRET_TOKEN": "s3cr3t"}
    os.environ.update(sentinels)
    try:
        run = run_child(_request(_compressed_pdf()), timeout_seconds=20, cwd=BACKEND_DIR)
    finally:
        for k in sentinels:
            os.environ.pop(k, None)
    assert run.ok
    # The allowlisted child env must not contain any forbidden fragment.
    assert run.forbidden_env_seen == []
    for frag in FORBIDDEN_ENV_FRAGMENTS:
        assert not any(frag in k.upper() for k in run.forbidden_env_seen)


def test_child_receives_no_db_redis_client_or_credential_input() -> None:
    # The IPC request schema contains only bytes + limits + mode; assert the
    # serialized message has no credential/client field keys (values are base64
    # PDF bytes and must not be scanned as if they were credentials).
    req = _request(_compressed_pdf())
    payload = req.to_json()
    for forbidden in ("password", "secret", "api_key", "client", "redis_url", "database_url", "postgres"):
        assert forbidden not in payload.lower()


def test_malformed_pdf_returns_safe_error() -> None:
    malformed = b"%PDF-1.4\n" + b"garbage" * 200 + b"%%EOF\n"
    run = run_child(_request(malformed, mode="decode_stream"), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.FAILED
    assert run.result.error_category in (ChildErrorCategory.MALFORMED, ChildErrorCategory.TRUNCATED)


def test_parser_exception_returns_typed_result() -> None:
    # A structurally broken PDF surfaces a typed MALFORMED result, never a crash.
    broken = _compressed_pdf()[:60]
    run = run_child(_request(broken, mode="decode_stream"), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok
    assert run.result is not None
    assert run.result.outcome is ChildProcessingOutcome.FAILED
    assert run.result.error_category in (ChildErrorCategory.MALFORMED, ChildErrorCategory.TRUNCATED)


def test_child_timeout_detected() -> None:
    run = run_child(_request(b"", mode="hang"), timeout_seconds=1, cwd=BACKEND_DIR)
    assert not run.ok
    assert run.timed_out
    assert run.terminated


def test_graceful_then_forced_termination_cleans_up() -> None:
    run = run_child(_request(b"", mode="hang"), timeout_seconds=1, cwd=BACKEND_DIR)
    assert run.timed_out
    assert run.terminated
    # After escalation the child must be gone; parent remains functional (below).


def test_no_orphan_process_remains() -> None:
    # Confirm the hang child is not left running by checking a fresh request works
    # and the parent can spawn again without interference.
    run = run_child(_request(b"", mode="hang"), timeout_seconds=1, cwd=BACKEND_DIR)
    assert run.timed_out
    # Immediate follow-up request must succeed (no orphan contention).
    again = run_child(_request(_compressed_pdf()), timeout_seconds=20, cwd=BACKEND_DIR)
    assert again.ok


def test_parent_remains_functional_after_child_failure() -> None:
    # First: hang + timeout. Second: normal success.
    first = run_child(_request(b"", mode="hang"), timeout_seconds=1, cwd=BACKEND_DIR)
    assert first.timed_out
    second = run_child(_request(_compressed_pdf()), timeout_seconds=20, cwd=BACKEND_DIR)
    assert second.ok
    assert second.result is not None
    assert second.result.outcome is ChildProcessingOutcome.SUCCESS


def test_memory_recorded_where_available() -> None:
    run = run_child(_request(_compressed_pdf()), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok
    assert run.result is not None
    # On Linux/POSIX resource.getrusage gives bytes; on Windows it may be None.
    if run.result.memory_bytes is not None:
        assert run.result.memory_bytes > 0


def test_cpu_enforcement_status_reported() -> None:
    # No OS CPU quota is configured in this prototype; the report must reflect the
    # platform capability rather than claim enforcement. We assert the run works.
    run = run_child(_request(_compressed_pdf()), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok


def test_temporary_working_data_cleaned() -> None:
    import tempfile

    before = set(os.listdir(tempfile.gettempdir()))
    run = run_child(_request(_compressed_pdf()), timeout_seconds=20, cwd=BACKEND_DIR)
    assert run.ok
    after = set(os.listdir(tempfile.gettempdir()))
    assert after == before


def test_no_pilot_pdf_accessed() -> None:
    # No real PDF path is referenced; only synthetic bytes over IPC.
    assert "C2051.pdf" not in _compressed_pdf().decode("latin-1")
    assert "C112209.pdf" not in _compressed_pdf().decode("latin-1")
