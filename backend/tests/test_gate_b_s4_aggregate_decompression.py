"""Gate B-S4 — Experiment A: aggregate document-level decompression budget (synthetic-only).

Investigates whether an aggregate decompression ceiling can be enforced *during*
decoding with pypdf 6.21.3 by driving each content-stream decode under a scoped
Configuration whose effective per-stream limit is:

    effective_stream_limit = min(per_stream_limit, remaining_document_budget)

All fixtures are synthetic and in-memory. No pilot PDF, no production code change,
p rendering/extraction of real content.
"""

from __future__ import annotations

import io
import time
import tracemalloc
import zlib
from dataclasses import dataclass
from typing import Any

import pypdf
from pypdf._configuration import Configuration, apply_configuration
from pypdf.errors import LimitReachedError, PyPdfError
from pypdf.generic import ArrayObject, EncodedStreamObject

# Approved per-stream candidate (GB-03). Laboratory aggregate budgets are small;
# a 256 MiB boundary fixture is exercised separately.
PER_STREAM_LIMIT = 32 * 1024 * 1024  # 32 MiB
LAB_AGGREGATE = 4 * 1024 * 1024  # planning lab budget (not an approved GB-04 value)
GB04_CANDIDATE = 256 * 1024 * 1024  # 256 MiB unapproved candidate


@dataclass(frozen=True)
class AggregateResult:
    ok: bool
    total_decoded: int
    remaining: int
    streams: tuple[tuple[str, int], ...]
    rejected_index: int | None = None
    reason: str = ""
    elapsed_s: float = 0.0
    peak_bytes: int = 0


def _payload(size: int) -> bytes:
    """Deterministic, compressible synthetic content of exactly `size` bytes."""
    unit = b"Tj 0 0 Td "
    return (unit * ((size // len(unit)) + 1))[:size]


def _stream_part(num: int, payload: bytes) -> bytes:
    compressed = zlib.compress(payload)
    body = (
        f"{num} 0 obj\n<< /Length {len(compressed)} /Filter /FlateDecode >>\n".encode()
        + b"stream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )
    return body


def _assemble(objects: list[tuple[int, bytes]]) -> bytes:
    """Minimal syntactically valid PDF with a correct xref table."""
    header = b"%PDF-1.4\n% synthetic s4\n"
    body = header
    offsets = [len(header)]
    for _num, part in objects:
        offsets.append(len(body))
        body += part
    n = len(objects) + 1
    xref = b"xref\n0 " + str(n).encode() + b"\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = b"trailer\n<< /Root 1 0 R /Size " + str(n).encode() + b" >>\nstartxref\n"
    trailer += str(len(body)).encode() + b"\n%%EOF\n"
    return body + xref + trailer


def build_multistream_pdf(payloads: list[bytes]) -> bytes:
    """One page per independent FlateDecode content stream."""
    n = len(payloads)
    objects: list[tuple[int, bytes]] = []
    kids = b"".join(f"{3 + i} 0 R ".encode() for i in range(n))
    objects.append((1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"))
    objects.append((2, b"2 0 obj\n<< /Type /Pages /Kids [" + kids + b"] /Count " + str(n).encode() + b" >>\nendobj\n"))
    for i in range(n):
        page_num = 3 + i
        stream_num = 3 + n + i
        objects.append(
            (
                page_num,
                f"{page_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents {stream_num} 0 R >>\nendobj\n".encode(),
            )
        )
    for i, payload in enumerate(payloads):
        stream_num = 3 + n + i
        objects.append((stream_num, _stream_part(stream_num, payload)))
    return _assemble(objects)


def build_repeated_reference_pdf(payload: bytes) -> bytes:
    """Two pages referencing the same stream object (object 4) — accounting probe."""
    objects: list[tuple[int, bytes]] = [
        (1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"),
        (2, b"2 0 obj\n<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>\nendobj\n"),
        (3, b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>\nendobj\n"),
        (5, b"5 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>\nendobj\n"),
    ]
    objects.append((4, _stream_part(4, payload)))
    # preserve numeric order for xref
    objects.sort(key=lambda t: t[0])
    return _assemble(objects)


def build_malformed_stream_pdf() -> bytes:
    """A stream whose zlib payload is corrupt (valid structure, invalid data)."""
    bad = b"\x78\x9c\x00\x01\x02\x03\x04"  # not a valid zlib stream
    stream = b"4 0 obj\n<< /Length " + str(len(bad)).encode() + b" /Filter /FlateDecode >>\nstream\n" + bad + b"\nendstream\nendobj\n"
    objects: list[tuple[int, bytes]] = [
        (1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"),
        (2, b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"),
        (3, b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>\nendobj\n"),
        (4, stream),
    ]
    return _assemble(objects)


def decode_with_aggregate_budget(
    data: bytes,
    *,
    per_stream_limit: int = PER_STREAM_LIMIT,
    aggregate_budget: int = LAB_AGGREGATE,
) -> AggregateResult:
    """Drive per-stream decode under an effective = min(per_stream, remaining).

    Enforcement model: the budget decrements *per actual decode operation*; repeated
    references to an already-decoded indirect object reuse cached output and do NOT
    reconsume budget. A failed/partial decode aborts (rejects) and consumes no
    successful bytes.
    """
    start = time.perf_counter()
    tracemalloc.start()
    reader = pypdf.PdfReader(io.BytesIO(data), strict=False)
    decoded_by_obj: dict[int, int] = {}
    total = 0
    remaining = aggregate_budget
    streams: list[tuple[str, int]] = []

    try:
        for page in reader.pages:
            contents = page.get("/Contents")
            if contents is None:
                continue
            items: list[Any] = contents if isinstance(contents, ArrayObject) else [contents]
            for cand in items:
                obj = cand.get_object()
                if not isinstance(obj, EncodedStreamObject):
                    continue
                filters = obj.get("/Filter")
                names = [f.get_object() for f in filters] if isinstance(filters, ArrayObject) else ([filters.get_object()] if filters is not None else [])
                if not any("FlateDecode" in str(n) for n in names):
                    continue
                oid = id(obj)
                if oid in decoded_by_obj:
                    # Repeated reference to an already-decoded stream: reuse cache.
                    streams.append(("repeat", decoded_by_obj[oid]))
                    continue
                effective = min(per_stream_limit, remaining)
                if effective <= 0:
                    return _finish(start, False, total, remaining, streams, len(streams), "aggregate_budget_exhausted")
                try:
                    with apply_configuration(Configuration(zlib_maximum_output_length=effective)):
                        decoded = obj.get_data()
                except LimitReachedError:
                    return _finish(start, False, total, remaining, streams, len(streams), "limit_reached_stream_or_remaining")
                except PyPdfError:
                    return _finish(start, False, total, remaining, streams, len(streams), "malformed_stream")
                except Exception:  # noqa: BLE001 - synthetic malformed fixture
                    return _finish(start, False, total, remaining, streams, len(streams), "malformed_stream")
                ndec = len(decoded)
                decoded_by_obj[oid] = ndec
                streams.append(("decoded", ndec))
                total += ndec
                remaining -= ndec
                if remaining < 0:
                    return _finish(start, False, total, remaining, streams, len(streams) - 1, "budget_overshoot")
    finally:
        reader.close() if hasattr(reader, "close") else None

    return _finish(start, True, total, remaining, streams, None, "")


def _finish(
    start: float,
    ok: bool,
    total: int,
    remaining: int,
    streams: list[tuple[str, int]],
    rejected_index: int | None,
    reason: str,
) -> AggregateResult:
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return AggregateResult(
        ok=ok,
        total_decoded=total,
        remaining=remaining,
        streams=tuple(streams),
        rejected_index=rejected_index,
        reason=reason,
        elapsed_s=time.perf_counter() - start,
        peak_bytes=peak,
    )


# --- tests ---

def test_one_stream_below_per_stream_limit() -> None:
    data = build_multistream_pdf([_payload(1 * 1024 * 1024)])
    r = decode_with_aggregate_budget(data, per_stream_limit=PER_STREAM_LIMIT, aggregate_budget=LAB_AGGREGATE)
    assert r.ok, r.reason
    assert r.total_decoded == 1 * 1024 * 1024
    assert r.remaining == LAB_AGGREGATE - 1 * 1024 * 1024


def test_multiple_streams_aggregate_exceeds_lab_budget() -> None:
    # 4 streams x 2 MiB each (each < 32 MiB), aggregate 8 MiB > lab 4 MiB.
    data = build_multistream_pdf([_payload(2 * 1024 * 1024)] * 4)
    r = decode_with_aggregate_budget(data, per_stream_limit=PER_STREAM_LIMIT, aggregate_budget=LAB_AGGREGATE)
    assert not r.ok
    assert r.reason == "aggregate_budget_exhausted"
    assert r.total_decoded == LAB_AGGREGATE  # stopped exactly at budget
    assert r.remaining == 0


def test_aggregate_below_budget_ok() -> None:
    data = build_multistream_pdf([_payload(2 * 1024 * 1024)] * 2)
    r = decode_with_aggregate_budget(data, per_stream_limit=PER_STREAM_LIMIT, aggregate_budget=LAB_AGGREGATE)
    assert r.ok
    assert r.total_decoded == 4 * 1024 * 1024
    assert r.remaining == 0


def test_stream_exceeds_per_stream_limit() -> None:
    data = build_multistream_pdf([_payload(3 * 1024 * 1024)])
    r = decode_with_aggregate_budget(data, per_stream_limit=1 * 1024 * 1024, aggregate_budget=LAB_AGGREGATE)
    assert not r.ok
    assert r.reason == "limit_reached_stream_or_remaining"


def test_aggregate_overflow_last_stream() -> None:
    # 3 MiB + 3 MiB with per-stream 32 MiB, aggregate budget 5 MiB.
    data = build_multistream_pdf([_payload(3 * 1024 * 1024), _payload(3 * 1024 * 1024)])
    r = decode_with_aggregate_budget(data, per_stream_limit=PER_STREAM_LIMIT, aggregate_budget=5 * 1024 * 1024)
    assert not r.ok
    assert r.reason == "limit_reached_stream_or_remaining"
    assert r.total_decoded == 3 * 1024 * 1024  # second (last) stream rejected
    assert r.rejected_index == 1


def test_repeated_reference_counts_once() -> None:
    data = build_repeated_reference_pdf(_payload(2 * 1024 * 1024))
    r = decode_with_aggregate_budget(data, per_stream_limit=PER_STREAM_LIMIT, aggregate_budget=LAB_AGGREGATE)
    assert r.ok
    assert r.total_decoded == 2 * 1024 * 1024  # counted once, not twice
    assert r.remaining == LAB_AGGREGATE - 2 * 1024 * 1024
    decoded = [n for kind, n in r.streams if kind == "decoded"]
    repeats = [n for kind, n in r.streams if kind == "repeat"]
    assert len(decoded) == 1
    assert len(repeats) == 1
    assert repeats[0] == decoded[0]


def test_malformed_stream_cleanup() -> None:
    data = build_malformed_stream_pdf()
    r = decode_with_aggregate_budget(data, per_stream_limit=PER_STREAM_LIMIT, aggregate_budget=LAB_AGGREGATE)
    # pypdf may tolerate a corrupt stream and yield zero bytes, or raise. Either
    # way the accounting must not count partial bytes and the run must stay within
    # budget with no leaked decode.
    assert r.total_decoded == 0
    assert r.ok or r.reason in ("malformed_stream", "limit_reached_stream_or_remaining")


def test_gb04_candidate_256mib_boundary() -> None:
    """Exercise the 256 MiB unapproved candidate (8 x 32 MiB streams).

    Runs only when the environment can afford it; bounded per-stream decode keeps
    peak memory low. This is a scaled experiment, not a production validation.
    """
    payloads = [_payload(32 * 1024 * 1024) for _ in range(8)]
    data = build_multistream_pdf(payloads)
    r = decode_with_aggregate_budget(data, per_stream_limit=PER_STREAM_LIMIT, aggregate_budget=GB04_CANDIDATE)
    assert r.ok, r.reason
    assert r.total_decoded == GB04_CANDIDATE
    assert r.remaining == 0
    assert r.peak_bytes < 512 * 1024 * 1024  # bounded decode keeps peak moderate
