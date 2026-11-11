"""Gate B-S4.1 — test-only helpers for stream coverage / failure accounting / concurrency.

Reuses the synthetic PDF builders and the bounded per-stream decode model from
S4, and adds (a) a resource-walk orchestrator that also enumerates Form/Image
XObject streams and (b) record types for the experiments. Nothing here touches
production code.
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
from pypdf.generic import ArrayObject, DictionaryObject, EncodedStreamObject

PER_STREAM_DEFAULT = 32 * 1024 * 1024
AGGREGATE_DEFAULT = 4 * 1024 * 1024


@dataclass(frozen=True)
class DecodeRecord:
    ok: bool
    total_decoded: int
    remaining: int
    streams: tuple[tuple[str, int], ...]
    rejected_index: int | None = None
    reason: str = ""
    parse_error: bool = False
    elapsed_s: float = 0.0
    peak_bytes: int = 0


def payload(size: int) -> bytes:
    unit = b"Tj 0 0 Td "
    return (unit * ((size // len(unit)) + 1))[:size]


def stream_part(num: int, data: bytes) -> bytes:
    compressed = zlib.compress(data)
    return (
        f"{num} 0 obj\n<< /Length {len(compressed)} /Filter /FlateDecode >>\n".encode()
        + b"stream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )


def assemble(objects: list[tuple[int, bytes]]) -> bytes:
    header = b"%PDF-1.4\n% synthetic s4.1\n"
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


def build_content_only(payloads: list[bytes]) -> bytes:
    """One page per independent FlateDecode content stream (S4-style)."""
    n = len(payloads)
    kids = b"".join(f"{3 + i} 0 R ".encode() for i in range(n))
    objects: list[tuple[int, bytes]] = [
        (1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"),
        (2, b"2 0 obj\n<< /Type /Pages /Kids [" + kids + b"] /Count " + str(n).encode() + b" >>\nendobj\n"),
    ]
    for i in range(n):
        page_num = 3 + i
        stream_num = 3 + n + i
        objects.append(
            (
                page_num,
                f"{page_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents {stream_num} 0 R >>\nendobj\n".encode(),
            )
        )
    for i, pl in enumerate(payloads):
        stream_num = 3 + n + i
        objects.append((stream_num, stream_part(stream_num, pl)))
    return assemble(objects)


def build_with_xobjects(content_payload: bytes, form_payload: bytes, image_payload: bytes) -> bytes:
    """One page whose /Resources holds a Form XObject and an Image XObject, both
    FlateDecode streams, plus its own content stream. Object numbers:
    4=content, 5=form, 6=image.
    """
    page = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100]\n"
        b"  /Contents 4 0 R\n"
        b"  /Resources << /XObject << /Fm1 5 0 R /Im1 6 0 R >> >> >>\nendobj\n"
    )
    objects: list[tuple[int, bytes]] = [
        (1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"),
        (2, b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"),
        (3, page),
        (4, stream_part(4, content_payload)),
        (5, stream_part(5, form_payload)),
        (6, stream_part(6, image_payload)),
    ]
    return assemble(objects)


def build_raw_content_streams(streams_data: list[bytes]) -> bytes:
    """One page per FlateDecode stream whose encoded bytes are provided verbatim
    (used to inject malformed / truncated compressed payloads)."""
    n = len(streams_data)
    kids = b"".join(f"{3 + i} 0 R ".encode() for i in range(n))
    objects: list[tuple[int, bytes]] = [
        (1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"),
        (2, b"2 0 obj\n<< /Type /Pages /Kids [" + kids + b"] /Count " + str(n).encode() + b" >>\nendobj\n"),
    ]
    for i in range(n):
        page_num = 3 + i
        stream_num = 3 + n + i
        objects.append(
            (
                page_num,
                f"{page_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents {stream_num} 0 R >>\nendobj\n".encode(),
            )
        )
    for i, raw in enumerate(streams_data):
        stream_num = 3 + n + i
        stream = (
            f"{stream_num} 0 obj\n<< /Length {len(raw)} /Filter /FlateDecode >>\n".encode()
            + b"stream\n"
            + raw
            + b"\nendstream\nendobj\n"
        )
        objects.append((stream_num, stream))
    return assemble(objects)


def _flate_encoded(obj: Any) -> bool:
    if not isinstance(obj, EncodedStreamObject):
        return False
    filters = obj.get("/Filter")
    names = [f.get_object() for f in filters] if isinstance(filters, ArrayObject) else ([filters.get_object()] if filters is not None else [])
    return any("FlateDecode" in str(n) for n in names)


def _decode_under_limit(obj: Any, effective: int) -> tuple[bool, bytes, str]:
    """Attempt bounded decode. Returns (ok, data, reason)."""
    try:
        with apply_configuration(Configuration(zlib_maximum_output_length=effective)):
            data = obj.get_data()
        return True, data, ""
    except LimitReachedError:
        return False, b"", "limit_reached"
    except PyPdfError:
        return False, b"", "malformed"
    except Exception:  # noqa: BLE001
        return False, b"", "malformed"


def decode_content_only(
    data: bytes,
    *,
    per_stream_limit: int = PER_STREAM_DEFAULT,
    aggregate_budget: int = AGGREGATE_DEFAULT,
    measure: bool = True,
) -> DecodeRecord:
    """S4-identical: only page content streams are enumerated."""
    return _decode_generic(data, per_stream_limit=per_stream_limit, aggregate_budget=aggregate_budget, walk_resources=False, measure=measure)


def decode_with_resource_walk(
    data: bytes,
    *,
    per_stream_limit: int = PER_STREAM_DEFAULT,
    aggregate_budget: int = AGGREGATE_DEFAULT,
    measure: bool = True,
) -> DecodeRecord:
    """Also enumerate Form/Image XObject streams under /Resources."""
    return _decode_generic(data, per_stream_limit=per_stream_limit, aggregate_budget=aggregate_budget, walk_resources=True, measure=measure)


def _decode_generic(
    data: bytes,
    *,
    per_stream_limit: int,
    aggregate_budget: int,
    walk_resources: bool,
    measure: bool = True,
) -> DecodeRecord:
    start = time.perf_counter()
    if measure:
        tracemalloc.start()
    try:
        reader = pypdf.PdfReader(io.BytesIO(data), strict=False)
    except Exception:  # noqa: BLE001 - parse failure before any stream decoding
        if measure:
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        else:
            peak = 0
        return DecodeRecord(False, 0, aggregate_budget, (), parse_error=True, elapsed_s=time.perf_counter() - start, peak_bytes=peak)

    decoded_by_obj: dict[int, int] = {}
    total = 0
    remaining = aggregate_budget
    streams: list[tuple[str, int]] = []

    def _visit(obj: Any, kind: str) -> tuple[bool, str]:
        nonlocal total, remaining
        if not _flate_encoded(obj):
            return True, ""
        oid = id(obj)
        if oid in decoded_by_obj:
            streams.append(("repeat:" + kind, decoded_by_obj[oid]))
            return True, ""
        effective = min(per_stream_limit, remaining)
        if effective <= 0:
            return False, "aggregate_budget_exhausted"
        ok, decoded, reason = _decode_under_limit(obj, effective)
        if not ok:
            return False, reason
        ndec = len(decoded)
        decoded_by_obj[oid] = ndec
        streams.append((kind, ndec))
        total += ndec
        remaining -= ndec
        if remaining < 0:
            return False, "budget_overshoot"
        return True, ""

    def _walk_xobjects(page: Any) -> tuple[bool, str]:
        resources = page.get("/Resources")
        if resources is None:
            return True, ""
        resources = resources.get_object()
        xobjs = resources.get("/XObject") if isinstance(resources, DictionaryObject) else None
        if xobjs is None:
            return True, ""
        xobjs = xobjs.get_object()
        if not isinstance(xobjs, DictionaryObject):
            return True, ""
        for name in ("/Fm1", "/Im1", "/Image1", "/Im0"):
            ref = xobjs.get(name)
            if ref is None:
                continue
            obj = ref.get_object()
            ok, reason = _visit(obj, "xobject:" + name)
            if not ok:
                return False, reason
        return True, ""

    reason = ""
    rejected = None
    try:
        for page in reader.pages:
            contents = page.get("/Contents")
            if contents is not None:
                items = contents if isinstance(contents, ArrayObject) else [contents]
                for cand in items:
                    obj = cand.get_object()
                    ok, r = _visit(obj, "content")
                    if not ok:
                        reason = r
                        rejected = len(streams)
                        break
                if reason:
                    break
            if walk_resources:
                ok, r = _walk_xobjects(page)
                if not ok:
                    reason = r
                    rejected = len(streams)
                    break
            if reason:
                break
    finally:
        try:
            reader.close()
        except Exception:  # noqa: BLE001
            pass

    _, peak = tracemalloc.get_traced_memory() if measure else (0, 0)
    if measure:
        tracemalloc.stop()
    ok = not reason
    return DecodeRecord(ok, total, remaining, tuple(streams), rejected, reason, False, time.perf_counter() - start, peak)
