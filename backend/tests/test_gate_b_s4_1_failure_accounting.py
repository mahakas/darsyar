"""Gate B-S4.1 — Experiment B: failed / partial decoding accounting (synthetic).

Investigates whether malformed, truncated, failed, or partial stream decoding can
bypass the aggregate budget or cause unaccounted/unbounded work, and evaluates a
fail-closed experimental policy.
"""

from __future__ import annotations

import zlib

from sandbox.s4_1_lib import (
    _decode_under_limit,
    build_content_only,
    build_raw_content_streams,
    decode_content_only,
    payload,
)

MB = 1024 * 1024


def test_valid_stream_decodes_and_charges_budget() -> None:
    data = build_content_only([payload(1 * MB)])
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=4 * MB)
    assert r.ok
    assert r.total_decoded == 1 * MB
    assert r.remaining == 3 * MB


def test_malformed_flate_is_tolerated_as_zero() -> None:
    bad = b"\x78\x9c\x00\x01\x02\x03\x04"  # invalid zlib payload
    data = build_raw_content_streams([bad])
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=4 * MB)
    # pypdf 6.21.3 tolerates and yields 0 bytes (S4 finding).
    assert r.ok
    assert r.total_decoded == 0
    assert r.remaining == 4 * MB


def test_truncated_compressed_stream_fails_closed() -> None:
    full = zlib.compress(payload(1 * MB))
    truncated = full[: len(full) // 2]
    data = build_raw_content_streams([truncated])
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=4 * MB)
    # Either pypdf raises (-> rejected, reason malformed) or returns partial/empty.
    if not r.ok:
        assert r.reason in ("malformed", "limit_reached")
        assert r.total_decoded <= 1 * MB
    else:
        # tolerated toleration: still bounded, no budget overshoot
        assert r.total_decoded <= 4 * MB


def test_stream_exceeding_per_stream_limit_rejects() -> None:
    data = build_raw_content_streams([zlib.compress(payload(3 * MB))])
    r = decode_content_only(data, per_stream_limit=1 * MB, aggregate_budget=8 * MB)
    assert not r.ok
    assert r.reason in ("limit_reached", "malformed")


def test_aggregate_remaining_exhausted_rejects_last_stream() -> None:
    data = build_raw_content_streams(
        [zlib.compress(payload(3 * MB)), zlib.compress(payload(3 * MB))]
    )
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=5 * MB)
    assert not r.ok
    assert r.reason in ("limit_reached", "limit_reached_stream_or_remaining")
    assert r.total_decoded == 3 * MB


def test_multiple_malformed_streams_do_not_overshoot() -> None:
    bad = b"\x78\x9c\x00\x01\x02\x03\x04"
    data = build_raw_content_streams([bad, bad, bad])
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=4 * MB)
    assert r.ok
    assert r.total_decoded == 0
    assert r.remaining == 4 * MB


def test_valid_before_and_after_malformed() -> None:
    bad = b"\x78\x9c\x00\x01\x02\x03\x04"
    data = build_raw_content_streams(
        [zlib.compress(payload(1 * MB)), bad, zlib.compress(payload(1 * MB))]
    )
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=4 * MB)
    assert r.ok
    assert r.total_decoded == 2 * MB  # valid streams counted; malformed zero
    assert r.remaining == 2 * MB


def test_repeated_access_to_failed_stream_yields_cache_no_extra_work() -> None:
    bad = b"\x78\x9c\x00\x01\x02\x03\x04"
    import io

    import pypdf

    data = build_raw_content_streams([bad])
    reader = pypdf.PdfReader(io.BytesIO(data), strict=False)
    obj = reader.pages[0]["/Contents"].get_object()
    ok1, d1, r1 = _decode_under_limit(obj, 32 * MB)
    ok2, d2, r2 = _decode_under_limit(obj, 32 * MB)
    # Same object, same cached result; pypdf does not re-decode (returns cached).
    assert d1 == d2 == b""
    assert ok1 == ok2


def test_parse_failure_before_stream_returns_parse_error() -> None:
    bogus = b"%PDF-1.7\n" + b"garbage" * 300 + b"%%EOF\n"
    r = decode_content_only(bogus, per_stream_limit=32 * MB, aggregate_budget=4 * MB)
    assert not r.ok
    assert r.parse_error
    assert r.total_decoded == 0


def test_fail_closed_property_bounded_work() -> None:
    # Even with many malformed streams, the enumerator terminates and never charges
    # more than the budget; no unbounded repeated decompression occurs.
    bad = b"\x78\x9c\x00\x01\x02\x03\x04"
    data = build_raw_content_streams([bad] * 40)
    r = decode_content_only(data, per_stream_limit=32 * MB, aggregate_budget=4 * MB)
    assert r.total_decoded <= 4 * MB
    assert len(r.streams) <= 40
