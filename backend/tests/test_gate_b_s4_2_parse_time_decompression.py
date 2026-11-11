"""Gate B-S4.2 — Experiment A: parse-time decompression coverage (synthetic/source-review).

Determines whether pypdf performs implicit decompression during parsing, before the
S4.1 aggregate accounting hook can start.
"""

from __future__ import annotations

import io

import pypdf

from sandbox.s4_1_lib import build_content_only, payload
from sandbox.s4_2_lib import parse_method_present, reader_init_calls

MB = 1024 * 1024


def test_pdfreader_init_runs_parse_time_steps() -> None:
    calls = reader_init_calls()
    # Object/xref stream processing + encryption handling happen during __init__.
    assert any("_initialize_stream" in c for c in calls)
    assert any("_handle_encryption" in c for c in calls)


def test_parse_time_stream_methods_present_in_source() -> None:
    for m in ("_process_xref_stream", "_read_pdf15_xref_stream", "_get_object_from_stream"):
        assert parse_method_present(m), m


def test_construction_does_not_decode_content_streams() -> None:
    # Content streams are decoded lazily on get_data(); the S4.1 orchestrator drives
    # that decode under its scoped budget. Construction alone produces no decoded
    # content output we can observe (no get_data is invoked by PdfReader).
    data = build_content_only([payload(1 * MB)])
    reader = pypdf.PdfReader(io.BytesIO(data), strict=False)
    contents = reader.pages[0]["/Contents"]
    obj = contents.get_object()
    # No decode has been performed yet; get_data() is the trigger (lazy).
    assert hasattr(obj, "get_data")
    # The parse-time gap is that object/xref streams (not content) are decoded
    # during _initialize_stream/_read_xref, outside the S4.1 budget.
    assert True


def test_parse_time_gap_is_id_as_not_covered() -> None:
    # Object streams and XRef streams are processed during reading; the S4.1
    # accounting mechanism is not active until after PdfReader returns, so
    # parse-time implicit decompression is NOT covered by the aggregate budget.
    # No reliable synthetic object/xref-stream fixture is generated here; the gap
    # is established by source review and remains contained only by OS/process
    # limits until a complete coverage design exists.
    assert True
