"""Gate B-S4.1 — Experiment C: concurrent document isolation (synthetic).

Demonstrates that two documents with different per-stream/aggregate budgets do
not interfere under the tested concurrency models (threads, async tasks). Process
isolation is trivially provided by the S1 child model and not re-tested here.
"""

from __future__ import annotations

import asyncio
import threading
import zlib
from collections.abc import Callable

from pypdf._configuration import Configuration, apply_configuration, get_configuration

from sandbox.s4_1_lib import (
    build_content_only,
    build_raw_content_streams,
    decode_content_only,
    payload,
)

MB = 1024 * 1024

# Document A: smaller aggregate budget.
DOC_A = build_content_only([payload(1 * MB), payload(1 * MB)])
PER_A = 32 * MB
AGG_A = 4 * MB

# Document B: larger aggregate budget, different stream sequence.
DOC_B = build_content_only([payload(1 * MB), payload(1 * MB), payload(1 * MB)])
PER_B = 16 * MB
AGG_B = 8 * MB

Result = dict[str, int | bool]


def _result_of(ok: bool, total: int, remaining: int) -> Result:
    return {"ok": ok, "total": total, "remaining": remaining}


def _run(data: bytes, per: int, agg: int) -> Result:
    r = decode_content_only(data, per_stream_limit=per, aggregate_budget=agg, measure=False)
    return _result_of(r.ok, r.total_decoded, r.remaining)


def _baseline_A() -> Result:
    return _run(DOC_A, PER_A, AGG_A)


def _baseline_B() -> Result:
    return _run(DOC_B, PER_B, AGG_B)


def test_sequential_isolation_baselines() -> None:
    a = _baseline_A()
    b = _baseline_B()
    assert a == {"ok": True, "total": 2 * MB, "remaining": 2 * MB}
    assert b == {"ok": True, "total": 3 * MB, "remaining": 5 * MB}


def _run_threads(fn: Callable[[str, bytes, int, int], None]) -> None:
    t1 = threading.Thread(target=fn, args=("A", DOC_A, PER_A, AGG_A))
    t2 = threading.Thread(target=fn, args=("B", DOC_B, PER_B, AGG_B))
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def test_thread_concurrency_isolation() -> None:
    base_a = _baseline_A()
    base_b = _baseline_B()
    results: dict[str, Result] = {}
    lock = threading.Lock()

    def run(tag: str, data: bytes, per: int, agg: int) -> None:
        r = _run(data, per, agg)
        with lock:
            results[tag] = r

    _run_threads(run)
    assert results["A"] == base_a
    assert results["B"] == base_b


def test_interleaved_threads_with_failure_in_A() -> None:
    doc_a_bad = build_raw_content_streams([zlib.compress(payload(3 * MB))])
    base_a_bad = _run(doc_a_bad, 1 * MB, 8 * MB)
    assert base_a_bad["ok"] is False
    base_b = _baseline_B()
    results: dict[str, Result] = {}
    lock = threading.Lock()

    def run(tag: str, data: bytes, per: int, agg: int) -> None:
        r = _run(data, per, agg)
        with lock:
            results[tag] = r

    t1 = threading.Thread(target=run, args=("A", doc_a_bad, 1 * MB, 8 * MB))
    t2 = threading.Thread(target=run, args=("B", DOC_B, PER_B, AGG_B))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert results["A"]["ok"] is False
    assert results["B"] == base_b  # B unaffected by A's failure


def test_async_task_isolation() -> None:
    base_a = _baseline_A()
    base_b = _baseline_B()

    async def run(tag: str, data: bytes, per: int, agg: int) -> tuple[str, Result]:
        # each asyncio task gets its own context -> independent scoped config
        return tag, _run(data, per, agg)

    async def main() -> dict[str, Result]:
        out = await asyncio.gather(
            run("A", DOC_A, PER_A, AGG_A),
            run("B", DOC_B, PER_B, AGG_B),
        )
        return dict(out)

    results = asyncio.run(main())
    assert results["A"] == base_a
    assert results["B"] == base_b


def test_exception_does_not_leave_stale_config() -> None:
    doc_bad = build_raw_content_streams([zlib.compress(payload(3 * MB))])
    r_bad = _run(doc_bad, 1 * MB, 8 * MB)
    assert r_bad["ok"] is False
    base_b = _baseline_B()
    assert _run(DOC_B, PER_B, AGG_B) == base_b


def test_no_global_budget_state_across_calls() -> None:
    r1 = _run(DOC_A, PER_A, AGG_A)
    r2 = _run(DOC_A, PER_A, AGG_A)
    assert r1 == r2 == {"ok": True, "total": 2 * MB, "remaining": 2 * MB}


def test_configuration_restored_after_context_exit() -> None:
    before = get_configuration().zlib_maximum_output_length
    with apply_configuration(Configuration(zlib_maximum_output_length=7)):
        assert get_configuration().zlib_maximum_output_length == 7
    assert get_configuration().zlib_maximum_output_length == before
