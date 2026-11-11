"""Gate B-S4.1 — Experiment A: stream discovery / decode coverage audit (synthetic).

Determines which stream categories the S4 experimental accounting observes and
whether pypdf 6.21.3 can decode them, using deterministic synthetic fixtures and
source-review classification for categories that cannot be safely synthesized.
"""

from __future__ import annotations

import inspect

from pypdf.generic import EncodedStreamObject

from sandbox.s4_1_lib import (
    DecodeRecord,
    assemble,
    build_content_only,
    build_with_xobjects,
    decode_content_only,
    decode_with_resource_walk,
    payload,
    stream_part,
)

MB = 1024 * 1024


def _assert_coverage_observed(record: DecodeRecord, kinds: list[str]) -> None:
    seen = [k for k, _ in record.streams]
    for k in kinds:
        assert k in seen, f"expected to observe {k}, saw {seen}"


def test_content_only_observes_page_content_streams() -> None:
    data = build_content_only([payload(1 * MB)])
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=4 * MB)
    assert r.ok
    _assert_coverage_observed(r, ["content"])
    assert r.total_decoded == 1 * MB


def test_content_only_does_not_observe_form_image_xobjects() -> None:
    # The page has a content stream plus Form and Image XObject streams. The S4
    # enumerator (content-only) must NOT observe the XObjects => coverage gap.
    data = build_with_xobjects(payload(1 * MB), payload(2 * MB), payload(3 * MB))
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=10 * MB)
    assert r.ok
    assert r.total_decoded == 1 * MB  # only content counted
    kinds = [k for k, _ in r.streams]
    assert not any(k.startswith("xobject:") for k in kinds)


def test_resource_walk_observes_form_and_image_xobjects() -> None:
    # The resource-walk enumerator also visits Form/Image XObjects; it can cover
    # them and enforce the aggregate budget across all three stream categories.
    data = build_with_xobjects(payload(1 * MB), payload(2 * MB), payload(3 * MB))
    r = decode_with_resource_walk(data, per_stream_limit=32 * MB, aggregate_budget=10 * MB)
    assert r.ok, r.reason
    _assert_coverage_observed(r, ["content", "xobject:/Fm1", "xobject:/Im1"])
    assert r.total_decoded == 6 * MB  # 1+2+3
    assert r.remaining == 4 * MB


def test_resource_walk_aggregate_budget_applies_across_xobjects() -> None:
    data = build_with_xobjects(payload(1 * MB), payload(4 * MB), payload(4 * MB))
    r = decode_with_resource_walk(data, per_stream_limit=32 * MB, aggregate_budget=6 * MB)
    # 1 + 4 = 5 <= 6, then image effective = min(32MB, 1MB); decode 4MB > 1MB -> rejected
    assert not r.ok
    assert r.reason == "limit_reached_stream_or_remaining" or r.reason == "limit_reached"
    assert r.total_decoded <= 5 * MB


def test_repeated_reference_in_content_observed_once() -> None:
    # Two pages referencing the same content stream object.
    payload_bytes = payload(2 * MB)
    stream = stream_part(4, payload_bytes)
    objects = [
        (1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"),
        (2, b"2 0 obj\n<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>\nendobj\n"),
        (3, b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>\nendobj\n"),
        (5, b"5 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>\nendobj\n"),
        (4, stream),
    ]
    objects.sort(key=lambda t: t[0])
    data = assemble(objects)
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=8 * MB)
    assert r.ok
    assert r.total_decoded == 2 * MB  # once, not twice
    decoded = [n for k, n in r.streams if k == "content"]
    repeats = [n for k, n in r.streams if k == "repeat:content"]
    assert len(decoded) == 1
    assert len(repeats) == 1
    assert repeats[0] == decoded[0]


def test_object_and_xref_streams_are_source_review_implicit_decode_paths() -> None:
    # Object streams and XRef streams are processed implicitly during reading via
    # pypdf internals; they are not enumerated by the experimental budget. Confirm
    # the methods exist (source review) — a synthetic fixture is not reliably
    # constructible here, so these are classified COVERED_SOURCE_REVIEW_ONLY /
    # NOT_COVERED rather than tested.
    import pypdf._reader as reader_mod

    src = inspect.getsource(reader_mod)
    assert "_get_object_from_stream" in src
    assert "_process_xref_stream" in src
    assert "_read_pdf15_xref_stream" in src


def test_encoded_stream_object_is_the_decodable_unit() -> None:
    assert hasattr(EncodedStreamObject, "get_data")
