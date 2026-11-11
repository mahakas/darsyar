"""Gate B-S4.2 — Experiment B: one isolated child process per document.

Reuses the production `run_child` as a library to spawn a separate OS process per
synthetic document. No production module is modified.
"""

from __future__ import annotations

import os
import threading
import zlib

from app.services.ingestion.parent_child_contract import ChildErrorCategory, ChildProcessingOutcome

from sandbox.s4_1_lib import build_content_only, build_raw_content_streams, payload
from sandbox.s4_2_lib import run_doc_child

MB = 1024 * 1024

DOC_A = build_content_only([payload(1 * MB)])
DOC_B = build_content_only([payload(1 * MB), payload(1 * MB)])
DOC_BAD = build_raw_content_streams([zlib.compress(payload(3 * MB))])
DOC_MALFORMED = b"%PDF-1.4\n" + b"garbage" * 200 + b"%%EOF\n"


def test_two_normal_docs_sequential_separate_children() -> None:
    ra = run_doc_child(DOC_A)
    rb = run_doc_child(DOC_B)
    assert ra.ok and ra.result is not None and ra.result.outcome is ChildProcessingOutcome.SUCCESS
    assert rb.ok and rb.result is not None and rb.result.outcome is ChildProcessingOutcome.SUCCESS
    assert ra.result.pypdf_version == "6.21.3"
    assert ra.result.page_count == 1
    assert rb.result.page_count == 2


def test_concurrent_separate_children() -> None:
    results: dict[str, object] = {}
    lock = threading.Lock()

    def run(tag: str, doc: bytes) -> None:
        r = run_doc_child(doc)
        with lock:
            results[tag] = (r.ok, r.result.outcome if r.result else None)

    t1 = threading.Thread(target=run, args=("A", DOC_A))
    t2 = threading.Thread(target=run, args=("B", DOC_B))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert results["A"] == (True, ChildProcessingOutcome.SUCCESS)
    assert results["B"] == (True, ChildProcessingOutcome.SUCCESS)


def test_one_child_exhausts_budget_other_succeeds() -> None:
    r_bad = run_doc_child(DOC_BAD, zlib_limit=16, mode="decode_stream")
    r_good = run_doc_child(DOC_A)
    res_bad = r_bad.result
    assert r_bad.ok
    assert res_bad is not None
    assert res_bad.outcome is ChildProcessingOutcome.FAILED
    assert res_bad.error_category is ChildErrorCategory.RESOURCE_LIMIT
    assert r_good.ok
    assert r_good.result is not None
    assert r_good.result.outcome is ChildProcessingOutcome.SUCCESS


def test_malformed_child_fails_other_healthy() -> None:
    r_bad = run_doc_child(DOC_MALFORMED, mode="decode_stream")
    r_good = run_doc_child(DOC_A)
    res_bad = r_bad.result
    assert r_bad.ok
    assert res_bad is not None
    assert res_bad.outcome is ChildProcessingOutcome.FAILED
    assert res_bad.error_category in (ChildErrorCategory.MALFORMED, ChildErrorCategory.TRUNCATED)
    assert r_good.ok


def test_child_timeout_and_termination() -> None:
    r = run_doc_child(b"", timeout_seconds=1, mode="hang")
    assert not r.ok
    assert r.timed_out
    assert r.terminated


def test_parent_survives_and_subsequent_doc_succeeds() -> None:
    r1 = run_doc_child(b"", timeout_seconds=1, mode="hang")
    assert r1.timed_out
    r2 = run_doc_child(DOC_A)
    assert r2.ok
    assert r2.result is not None
    assert r2.result.outcome is ChildProcessingOutcome.SUCCESS


def test_no_orphan_child_remains() -> None:
    run_doc_child(b"", timeout_seconds=1, mode="hang")
    # A subsequent request must work; orphan child would contend/leak resources.
    assert run_doc_child(DOC_A).ok


def test_credentials_never_reach_child() -> None:
    sentinels = {"DATABASE_URL": "postgres://u:p@db/app", "SECRET_TOKEN": "s3cr3t"}
    os.environ.update(sentinels)
    try:
        r = run_doc_child(DOC_A)
    finally:
        for k in sentinels:
            os.environ.pop(k, None)
    assert r.ok
    assert r.forbidden_env_seen == []
