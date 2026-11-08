"""تست واحد مسیر cleanup کران‌دار چت (بدون نیاز به PostgreSQL).

پوشش سه فاز:
  - Phase 1: تکمیل عادی؛ تحمل لغو خارجی بدون cancel کردن cleanup.
  - Phase 1 timeout → Phase 2 (cancel + grace مستقل) → bounded.
  - Phase 2 grace timeout → Phase 3: ثبت در pending_cleanups (reference قوی) و fail-closed.
"""

import asyncio
import time

import pytest
from app.core.shutdown import SHUTDOWN_STATE
from app.services.chat_service import (
    _CLEANUP_CANCEL_GRACE_SECONDS,
    _CLEANUP_TIMEOUT_SECONDS,
    _bounded_cleanup_wait,
)


async def _make_cleanup_task(sleep_for: float, done_flag: list, fail: bool = False):
    async def work():
        if sleep_for:
            await asyncio.sleep(sleep_for)
        done_flag.append(1)
        if fail:
            raise RuntimeError("cleanup-failure")

    return asyncio.create_task(work())


def _clear_pending():
    SHUTDOWN_STATE.pending_cleanups.clear()


@pytest.mark.asyncio
async def test_phase1_success_completes_bounded() -> None:
    _clear_pending()
    done: list[int] = []
    task = await _make_cleanup_task(0.05, done)
    t0 = time.monotonic()
    cancelled = await _bounded_cleanup_wait(task, 1.0, 0.5)
    assert cancelled is False
    assert done == [1]
    assert task.done() is True
    assert time.monotonic() - t0 < 1.0
    assert SHUTDOWN_STATE.pending_cleanups == set()


@pytest.mark.asyncio
async def test_phase1_timeout_then_phase2_bounded() -> None:
    _clear_pending()
    done: list[int] = []
    # cleanup طولانی‌تر از phase1 → پس از phase1، cancel + phase2 محدود
    task = await _make_cleanup_task(0.5, done)
    t0 = time.monotonic()
    cancelled = await _bounded_cleanup_wait(task, 0.1, 0.4)
    elapsed = time.monotonic() - t0
    assert cancelled is False
    assert elapsed <= 1.0
    assert task.done() is True


async def _make_stubborn_cleanup_task() -> asyncio.Task:
    """cleanup غیر-همکار: پس از cancel به کار ادامه می‌دهد تا pending بماند."""

    async def work():
        try:
            await asyncio.Future()  # تا زمان لغو، معلق می‌ماند
        except asyncio.CancelledError:
            # از لغو چشم‌پوشی می‌کند و مدتی ادامه می‌دهد (بدون حلقه sleep)
            for _ in range(200):
                await asyncio.sleep(0.01)  # noqa: ASYNC110

    return asyncio.create_task(work())


@pytest.mark.asyncio
async def test_phase2_grace_timeout_registers_pending() -> None:
    _clear_pending()
    task = await _make_stubborn_cleanup_task()
    cancelled = await _bounded_cleanup_wait(task, 0.05, 0.1)
    assert cancelled is False
    assert task in SHUTDOWN_STATE.pending_cleanups
    assert not task.done()
    # پاک‌سازی برای عدم تداخل
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    _clear_pending()


@pytest.mark.asyncio
async def test_phase1_outer_cancellation_does_not_cancel_cleanup() -> None:
    _clear_pending()
    done: list[int] = []
    task = await _make_cleanup_task(0.2, done)

    async def run_with_cancel():
        try:
            return await _bounded_cleanup_wait(task, 1.0, 0.3)
        except asyncio.CancelledError:
            return "re-raised"

    waiter = asyncio.create_task(run_with_cancel())
    await asyncio.sleep(0.02)
    waiter.cancel()

    # cleanup نباید به‌دلیل لغو خارجی cancel شود
    assert not task.cancelled()
    # و باید در نهایت کامل شود (در همان بازه، بدون لغو شدن)
    assert await asyncio.wait_for(asyncio.shield(task), timeout=1.5) is None
    assert task.done() is True
    assert done == [1]

    try:
        await waiter
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_phase1_repeated_cancellation_keeps_cleanup_running() -> None:
    _clear_pending()
    done: list[int] = []
    task = await _make_cleanup_task(0.3, done)

    async def run_with_multiple_cancel():
        try:
            return await _bounded_cleanup_wait(task, 1.0, 0.3)
        except asyncio.CancelledError:
            return "re-raised"

    waiter = asyncio.create_task(run_with_multiple_cancel())
    await asyncio.sleep(0.02)
    waiter.cancel()
    await asyncio.sleep(0.02)
    waiter.cancel()
    await asyncio.sleep(0.02)
    waiter.cancel()

    # لغو تکراری نباید cleanup را cancel کند؛ cleanup باید هنوز در حال کار باشد.
    assert not task.cancelled()
    assert not task.done()
    # پس از توقف «طوفان لغو»، cleanup باید کامل شود
    assert await asyncio.wait_for(asyncio.shield(task), timeout=1.5) is None
    assert task.done() is True
    assert done == [1]

    try:
        await waiter
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_cleanup_result_and_exception_retrieved() -> None:
    _clear_pending()
    done: list[int] = []
    task = await _make_cleanup_task(0.05, done, fail=True)
    cancelled = await _bounded_cleanup_wait(task, 1.0, 0.3)
    assert cancelled is False
    assert task.done() is True
    assert done == [1]


@pytest.mark.asyncio
async def test_constants_reasonable() -> None:
    assert _CLEANUP_TIMEOUT_SECONDS >= 10
    assert 0 < _CLEANUP_CANCEL_GRACE_SECONDS <= 5
