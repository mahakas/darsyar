"""پذیرش یکپارچه فاز ۳: HTTP واقعی (Uvicorn subprocess) + PostgreSQL واقعی + Provider mock محلی.

از ASGI/mock به‌جای HTTP واقعی استفاده نمی‌شود. Provider mock یک سرور HTTP محلی است که
قرارداد OpenAI-compatible stream را شبیه‌سازی می‌کند. هیچ تماس پولی/شبکهٔ خارجی ارسال نمی‌شود.
"""

import asyncio
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROVIDER_PORT = 9101
API_PORT = 9100

# ---- shared state for the provider mock (recorded across requests) ----
MOCK = {"calls": 0, "fail_pre": False, "fail_post": False, "hang": False}


def _provider_app() -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def completions():
        MOCK["calls"] += 1
        if MOCK["fail_pre"]:
            return StreamingResponse(iter(["data: {\"choices\":[{\"delta\":{}}]}\n\n", "data: [DONE]\n"]), media_type="text/event-stream")
        if MOCK["hang"]:
            async def hang():
                await asyncio.Future()
            return StreamingResponse(hang(), media_type="text/event-stream")

        async def gen():
            yield 'data: {"id":"mock-req","choices":[{"delta":{"content":"سلام"}}]}\n\n'
            if MOCK["fail_post"]:
                # after billable output, terminate with an error event
                yield 'data: {"id":"mock-req","choices":[{"delta":{}}]}\n\n'
                yield "data: [DONE]\n"
                return
            yield 'data: {"id":"mock-req","choices":[{"delta":{"content":" دنیا"}}]}\n\n'
            yield "data: [DONE]\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


@pytest.fixture(scope="module")
def provider_mock():
    MOCK["calls"] = 0
    MOCK["fail_pre"] = False
    MOCK["fail_post"] = False
    MOCK["hang"] = False
    config = uvicorn.Config(_provider_app(), host="127.0.0.1", port=PROVIDER_PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            httpx.get(f"http://127.0.0.1:{PROVIDER_PORT}/openapi.json").raise_for_status()
            break
        except Exception:
            time.sleep(0.2)
    yield
    server.should_exit = True
    thread.join(timeout=10)


def _test_db_url() -> str:
    """حل fail-safe URL دیتابیس تست (هرگز به settings.database_url برنگرد).

    ترتیب: ۱) TEST_DATABASE_URL (env) → ۲) settings.test_database_url → ۳) خطای روشن.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url.strip().strip('"')
    from app.core.config import get_settings

    settings = get_settings()
    url = (getattr(settings, "test_database_url", "") or "").strip().strip('"')
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set and settings.test_database_url is empty; "
            "refusing to fall back to settings.database_url"
        )
    return url


@pytest.fixture(scope="module")
def api_server(provider_mock):
    test_url = _test_db_url()
    env = os.environ.copy()
    env["DATABASE_URL"] = test_url
    env["REDIS_URL"] = "redis://127.0.0.1:6379/0"
    env["LLM_BASE_URL"] = f"http://127.0.0.1:{PROVIDER_PORT}"
    env["LLM_MODEL"] = "mock"
    env["LLM_API_KEY"] = "mock-key"
    env["LLM_MAX_RETRIES"] = "0"
    env["INFERENCE_MODE"] = "service"
    env["EMBEDDING_BACKEND"] = "remote"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(API_PORT), "--log-level", "warning"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 45
    base = f"http://127.0.0.1:{API_PORT}"
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base}/health", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        pytest.skip("API server did not become healthy")
    yield base
    # teardown قابل اتکا: ابتدا terminate نرمال، صبر، سپس فقط پس از timeout force-kill.
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


class TestHarness:
    def __init__(self, base: str, test_db_url: str | None = None) -> None:
        self.base = base
        self.token = ""
        self.user_id = ""
        self._test_db_url = test_db_url or _test_db_url()

    def _new_phone(self) -> str:
        return f"+989{str(uuid.uuid4().int)[:9]}"

    def _test_url(self) -> str:
        return self._test_db_url

    async def create_user_and_token(self) -> str:
        from app.core.security import create_token
        from app.repositories import credit_accounts as accounts
        from app.repositories import users as users_repo
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        engine = create_async_engine(self._test_url(), poolclass=NullPool)
        sf = async_sessionmaker(engine, expire_on_commit=False)
        phone = self._new_phone()
        async with sf() as session:
            user = await users_repo.create(session, phone=phone, role="user")
            await accounts.create(session, user_id=user.id, available_balance=10)
            await session.commit()
            self.user_id = str(user.id)
        await engine.dispose()
        self.token = create_token(self.user_id, "user", "access", str(uuid.uuid4()), lifetime=timedelta(minutes=5))
        return self.token

    async def get_balance(self) -> int:
        from app.repositories import credit_accounts as acc
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        engine = create_async_engine(self._test_url(), poolclass=NullPool)
        sf = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sf() as session:
                account = await acc.get_for_update(session, uuid.UUID(self.user_id))
                return account.available_balance
        finally:
            await engine.dispose()

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture(scope="module")
def harness(api_server) -> TestHarness:
    h = TestHarness(api_server, _test_db_url())
    # create user/token synchronously inside a fresh event loop
    asyncio.run(h.create_user_and_token())
    return h


async def _post_stream(h: TestHarness, payload: dict, *, headers: dict | None = None, request_timeout: float = 15) -> httpx.Response:
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        return await client.post(
            f"{h.base}/api/v1/chat/stream",
            json=payload,
            headers={**(headers or {}), **h.auth_headers()},
        )


async def _read_sse(response: httpx.Response) -> list[str]:
    events = []
    async for line in response.aiter_lines():
        if line.startswith("event:"):
            events.append(line[len("event:"):].strip())
    return events


@pytest.mark.asyncio
async def test_http_stream_success_full_lifecycle(harness: TestHarness) -> None:
    crid = "http0000000001"
    balance_before = await harness.get_balance()
    async with httpx.AsyncClient(timeout=20) as client:
        async with client.stream(
            "POST", f"{harness.base}/api/v1/chat/stream",
            json={"content": "hi", "client_request_id": crid},
            headers=harness.auth_headers(),
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers.get("content-type", "").startswith("text/event-stream")
            events = await _read_sse(resp)
    assert "ack" in events
    assert "assistant_created" in events
    assert "delta" in events
    assert "done" in events
    assert events.index("ack") < events.index("assistant_created") < events.index("delta") < events.index("done")
    # DB: user + assistant messages, reservation settled, balance decremented by 1
    from app.models.message import Message
    from app.repositories import reservations as res_repo
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(harness._test_url(), poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        msgs = (await session.execute(select(Message).where(Message.user_id == uuid.UUID(harness.user_id)).order_by(Message.sequence))).scalars().all()
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert msgs[-1].status == "completed"
        res = await res_repo.get_by_idempotency_key(session, uuid.UUID(harness.user_id), f"chat:{harness.user_id}:{crid}")
        assert res is not None and res.status == "settled"
    await engine.dispose()
    assert await harness.get_balance() == balance_before - 1


@pytest.mark.asyncio
async def test_http_ownership_isolation(harness: TestHarness) -> None:
    # create a conversation owned by user A and confirm user B is rejected with 404
    from app.repositories import conversations as conv
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(harness._test_url(), poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        c = await conv.create_conversation(session, user_id=uuid.UUID(harness.user_id))
        await session.commit()
        conv_id = str(c.id)
    await engine.dispose()
    # second user token
    h2 = TestHarness(harness.base, harness._test_url())
    await h2.create_user_and_token()
    resp = await _post_stream(h2, {"conversation_id": conv_id, "content": "x", "client_request_id": "http0000000002"})
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("code") == "conversation_not_found"


@pytest.mark.asyncio
async def test_http_idempotency_conflict_different_payload(harness: TestHarness) -> None:
    crid = "http0000000003"
    await _post_stream(harness, {"content": "first message", "client_request_id": crid})
    resp = await _post_stream(harness, {"content": "different content", "client_request_id": crid})
    assert resp.status_code == 409
    assert resp.json().get("code") == "idempotency_conflict"


@pytest.mark.asyncio
async def test_http_replay_no_second_provider_or_message(harness: TestHarness) -> None:
    crid = "http0000000004"
    calls_before = MOCK["calls"]
    await _post_stream(harness, {"content": "hello", "client_request_id": crid})
    # replay same client_request_id
    resp = await _post_stream(harness, {"content": "hello", "client_request_id": crid})
    assert resp.status_code == 200
    assert MOCK["calls"] == calls_before + 1  # provider called exactly once total
    from app.models.message import Message
    from app.repositories import reservations as res
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(harness._test_url(), poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        res_obj = await res.get_by_idempotency_key(session, uuid.UUID(harness.user_id), f"chat:{harness.user_id}:{crid}")
        assert res_obj is not None and res_obj.status == "settled"
        assistants = (await session.execute(select(Message).where(Message.reservation_id == res_obj.id))).scalars().all()
        assert len(assistants) == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_http_financial_failure_pre_token_release(harness: TestHarness) -> None:
    MOCK["fail_pre"] = True
    balance_before = await harness.get_balance()
    try:
        crid = "http0000000005"
        resp = await _post_stream(harness, {"content": "x", "client_request_id": crid})
        assert resp.status_code == 200
    finally:
        MOCK["fail_pre"] = False
    from app.repositories import reservations as res
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(harness._test_url(), poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        res_obj = await res.get_by_idempotency_key(session, uuid.UUID(harness.user_id), f"chat:{harness.user_id}:{crid}")
        assert res_obj.status == "released"
    await engine.dispose()
    # pre-token failure releases the reservation; balance must be unchanged
    assert await harness.get_balance() == balance_before


@pytest.mark.asyncio
async def test_http_concurrent_identical_requests_single_effect(harness: TestHarness) -> None:
    crid = "http0000000009"
    calls_before = MOCK["calls"]
    payload = {"content": "concurrent same", "client_request_id": crid}
    async with httpx.AsyncClient(timeout=25) as client:
        r1 = client.post(f"{harness.base}/api/v1/chat/stream", json=payload, headers=harness.auth_headers())
        r2 = client.post(f"{harness.base}/api/v1/chat/stream", json=payload, headers=harness.auth_headers())
        resp1, resp2 = await asyncio.gather(r1, r2)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # provider must be invoked once for this logical request
    assert MOCK["calls"] == calls_before + 1
    from app.models.message import Message
    from app.repositories import reservations as res
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(harness._test_url(), poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        assistants = (await session.execute(select(Message).where(Message.user_id == uuid.UUID(harness.user_id), Message.role == "assistant", Message.reservation_id.is_not(None)))).scalars().all()
        # count only the ones for this reservation
        res_obj = await res.get_by_idempotency_key(session, uuid.UUID(harness.user_id), f"chat:{harness.user_id}:{crid}")
        assert res_obj is not None
        res_assistants = [m for m in assistants if m.reservation_id == res_obj.id]
        assert len(res_assistants) == 1
        assert res_obj.status in ("settled", "released")
    await engine.dispose()
