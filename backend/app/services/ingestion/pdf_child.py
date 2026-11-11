"""Isolated PDF Child process (Gate B-S1 prototype).

Spawned by the Parent Supervisor as a separate OS process. It reads a minimal
versioned JSON request from stdin, applies an explicit scoped pypdf Configuration,
parses synthetic PDF bytes, optionally decodes a selected content stream, and
writes a structured JSON result to stdout.

Security invariants:
- The child receives only synthetic document bytes + explicit test-supplied limits.
- It never receives database/Redis credentials, application secrets, session
  objects, or infrastructure clients, and it never connects to any network or
  database.
- It does not print PDF bytes, secrets, or full environment values.

This module is expected to run as: `python -m app.services.ingestion.pdf_child`
"""

from __future__ import annotations

import io
import sys

import pypdf
from pypdf._configuration import Configuration, apply_configuration
from pypdf.errors import LimitReachedError, PyPdfError

from app.services.ingestion.parent_child_contract import (
    PARENT_CHILD_CONTRACT_VERSION,
    ChildErrorCategory,
    ChildProcessingOutcome,
    ParentChildRequest,
    ParentChildResult,
)

FLATE_ZLIB_LIMIT_KEY = "zlib_maximum_output_length"


def _read_request() -> ParentChildRequest:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("empty request")
    return ParentChildRequest.from_json(raw)


def _memory_bytes() -> int | None:
    """Best-effort RSS measurement (POSIX). Returns None where unsupported."""
    try:
        import importlib

        resource = importlib.import_module("resource")
        maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(maxrss) * 1024  # KB -> bytes
    except (ImportError, AttributeError, OSError, TypeError):
        return None


def _find_first_flate_stream(reader: pypdf.PdfReader) -> pypdf.generic.EncodedStreamObject | None:
    """Return the first page content stream whose filter chain includes FlateDecode."""
    for page in reader.pages:
        contents = page.get("/Contents")
        if contents is None:
            continue
        candidates = contents if isinstance(contents, pypdf.generic.ArrayObject) else [contents]
        for cand in candidates:
            obj = cand.get_object()
            if not isinstance(obj, pypdf.generic.EncodedStreamObject):
                continue
            filters = obj.get("/Filter")
            if isinstance(filters, pypdf.generic.ArrayObject):
                names = [f.get_object() for f in filters]
            else:
                names = [filters.get_object()] if filters is not None else []
            if any("FlateDecode" in str(n) for n in names):
                return obj
    return None


def process_request(request: ParentChildRequest) -> ParentChildResult:
    outcome = ChildProcessingOutcome.SUCCESS
    error = ChildErrorCategory.NONE
    page_count: int | None = None
    decoded_len: int | None = None

    zlib_limit = int(request.limits.get(FLATE_ZLIB_LIMIT_KEY, 75_000_000)) if request.limits else 75_000_000
    scoped = Configuration(zlib_maximum_output_length=zlib_limit)

    try:
        with apply_configuration(scoped):
            reader = pypdf.PdfReader(io.BytesIO(request.document_bytes), strict=False)
            if reader.is_encrypted:
                outcome = ChildProcessingOutcome.FAILED
                error = ChildErrorCategory.ENCRYPTED
                return _result(request, outcome, error)
            page_count = len(reader.pages)
            if request.mode == "decode_stream":
                stream = _find_first_flate_stream(reader)
                if stream is None:
                    outcome = ChildProcessingOutcome.FAILED
                    error = ChildErrorCategory.MALFORMED
                else:
                    # Explicitly decode the content stream (exercises the limit).
                    decoded = stream.get_data()
                    decoded_len = len(decoded)
    except LimitReachedError:
        outcome = ChildProcessingOutcome.FAILED
        error = ChildErrorCategory.RESOURCE_LIMIT
    except PyPdfError:
        outcome = ChildProcessingOutcome.FAILED
        error = ChildErrorCategory.MALFORMED
    except Exception:  # noqa: BLE001 - child must always return a typed result
        outcome = ChildProcessingOutcome.FAILED
        error = ChildErrorCategory.INTERNAL

    return _result(request, outcome, error, page_count, decoded_len)


def _result(
    request: ParentChildRequest,
    outcome: ChildProcessingOutcome,
    error: ChildErrorCategory,
    page_count: int | None = None,
    decoded_len: int | None = None,
) -> ParentChildResult:
    return ParentChildResult(
        contract_version=PARENT_CHILD_CONTRACT_VERSION,
        attempt_id=request.attempt_id,
        outcome=outcome,
        error_category=error,
        page_count=page_count,
        decoded_stream_length=decoded_len,
        pypdf_version=pypdf.__version__,
        memory_bytes=_memory_bytes(),
    )


def main() -> int:
    try:
        request = _read_request()
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"BAD_REQUEST {type(exc).__name__}\n")
        return 2

    if request.mode == "hang":
        # Simulate a child that ignores graceful termination.
        while True:
            pass

    result = process_request(request)
    sys.stdout.write(result.to_json() + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
