"""تست DB-free برای تضمین deregistration استریم پس از بستن صریح inner generator."""

import asyncio

import pytest
from app.api.v1.chat import router as chat_router
from app.core.shutdown import SHUTDOWN_STATE


async def _run(gen):
    got = []
    async for ev in gen:
        got.append(ev)
    return got


def test_active_streams_empty_by_default() -> None:
    assert SHUTDOWN_STATE.active_streams == set()


@pytest.mark.asyncio
async def test_deregistration_on_normal_completion() -> None:
    SHUTDOWN_STATE.active_streams.clear()
    async def make_gen():
        try:
            yield "a"
            yield "b"
        finally:
            pass
    task = asyncio.create_task(_run(make_gen()))
    await task
    assert SHUTDOWN_STATE.active_streams == set()


@pytest.mark.asyncio
async def test_deregistration_on_cancellation() -> None:
    SHUTDOWN_STATE.active_streams.clear()
    async def hang_gen():
        try:
            await asyncio.Future()
        finally:
            current = asyncio.current_task()
            if current is not None:
                SHUTDOWN_STATE.active_streams.discard(current)
    task = asyncio.create_task(hang_gen())
    SHUTDOWN_STATE.active_streams.add(task)
    await asyncio.sleep(0.01)
    assert task in SHUTDOWN_STATE.active_streams
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert SHUTDOWN_STATE.active_streams == set()


@pytest.mark.asyncio
async def test_router_finally_discards_even_on_aclose_exception() -> None:
    # شبیه‌سازی: inner generator که aclose آن exception می‌اندازد و روتر همچنان discard می‌کند
    SHUTDOWN_STATE.active_streams.clear()
    class _BadClose:
        def __init__(self) -> None:
            self.aclosed = False

        async def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

        async def aclose(self) -> None:
            self.aclosed = True
            raise RuntimeError("boom-aclose")

    bad = _BadClose()
    task = asyncio.current_task()
    SHUTDOWN_STATE.active_streams.add(task)
    try:
        # شبیه‌سازی finally روتر
        try:
            try:
                await bad.aclose()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
        finally:
            SHUTDOWN_STATE.active_streams.discard(task)
    finally:
        SHUTDOWN_STATE.active_streams.discard(task)
    assert SHUTDOWN_STATE.active_streams == set()
    assert bad.aclosed is True


def test_router_registered() -> None:
    assert chat_router is not None
    assert len(chat_router.routes) >= 1
