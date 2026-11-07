"""تست‌های Slice F: متریک‌ها، drain و lifecycle خاموشی تدریجی (بدون تماس شبکهٔ واقعی)."""

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from app.api.deps import get_current_user, get_db
from app.api.v1.chat import router as chat_router
from app.core.errors import install_error_handlers
from app.core.metrics import Counter, Gauge, Histogram, MetricsRegistry
from app.core.shutdown import SHUTDOWN_STATE
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def test_counter_and_gauge_accumulate() -> None:
    c = Counter("c", "h")
    c.inc({"outcome": "settled"})
    c.inc({"outcome": "settled"})
    c.inc({"outcome": "released"})
    snap = c.snapshot()
    assert snap[(("outcome", "settled"),)] == 2
    assert snap[(("outcome", "released"),)] == 1

    g = Gauge("g", "h")
    g.inc()
    g.inc()
    g.dec()
    assert g.snapshot()[()] == 1.0


def test_histogram_observe_buckets() -> None:
    h = Histogram("h", "help")
    h.observe(0.2)
    h.observe(2.0)
    h.observe(50.0)
    snap = h.snapshot()
    assert snap["count"][()] == 3
    assert snap["sum"][()] == pytest.approx(52.2)


def test_metrics_low_cardinality_no_identifiers() -> None:
    # فقط چک می‌کنیم که خروجی متن، labelهای مجاز را دارد و هیچ id کاربری ندارد.
    reg = MetricsRegistry()
    reg.chat_started.inc({"operation": "stream"})
    reg.financial_outcome.inc({"outcome": "settled"})
    text = reg.as_prometheus_text()
    assert "chat_streams_started" in text
    assert "chat_financial_outcome" in text
    assert "user_id" not in text.lower().replace("_", "")
    assert "conversation" not in text.lower()


def test_registry_prometheus_text_renders() -> None:
    reg = MetricsRegistry()
    reg.chat_started.inc({"operation": "stream"})
    reg.chat_active.inc()
    reg.financial_outcome.inc({"outcome": "settled"})
    text = reg.as_prometheus_text()
    assert "chat_streams_started{operation=\"stream\"} 1" in text
    assert "chat_streams_active 1.0" in text
    assert "chat_financial_outcome{outcome=\"settled\"} 1" in text


def test_shutdown_state_draining_flag() -> None:
    SHUTDOWN_STATE.draining = True
    assert SHUTDOWN_STATE.draining is True
    SHUTDOWN_STATE.draining = False


@pytest.mark.asyncio
async def test_shutdown_state_active_streams_drained() -> None:
    async def fake_stream() -> None:
        await asyncio.sleep(0.05)

    task = asyncio.create_task(fake_stream())
    SHUTDOWN_STATE.active_streams.add(task)
    await asyncio.wait({task}, timeout=0.5)
    SHUTDOWN_STATE.active_streams.discard(task)
    assert SHUTDOWN_STATE.active_streams == set()
    # after cancellation cleanup, no leaked tasks
    assert not SHUTDOWN_STATE.active_streams


@pytest.mark.asyncio
async def test_drain_rejects_new_stream_before_reservation() -> None:
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(chat_router)

    fake_user = SimpleNamespace(id=uuid.uuid4(), role="user")

    def override_current_user():
        return fake_user

    async def override_get_db():
        yield None  # in drain path never used; no DB/redis touch

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_get_db

    SHUTDOWN_STATE.draining = True
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat/stream",
                json={"content": "hi", "client_request_id": "slicef0001"},
            )
        assert response.status_code == 503
        body = response.json()
        assert body.get("code") == "service_draining"
    finally:
        SHUTDOWN_STATE.draining = False


@pytest.mark.asyncio
async def test_ready_reports_not_ready_while_draining() -> None:
    app = FastAPI()
    install_error_handlers(app)
    from app.core.operations import router as ops_router

    app.include_router(ops_router)
    SHUTDOWN_STATE.draining = True
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}
    finally:
        SHUTDOWN_STATE.draining = False
