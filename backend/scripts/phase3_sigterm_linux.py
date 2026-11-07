# ruff: noqa: ASYNC210,ASYNC221,ASYNC251,ASYNC110  (اسکریپت ارکستراسیون Linux CI؛ blocking عمدی است)
"""آزمون process-level Linux (GitHub CI): Open SSE + SIGTERM واقعی + تأیید مالی PostgreSQL.

دو سناریو:
  A) بدون خروجی billable → انتظار: reservation -> released (قبل از cron)
  B) پس از یک delta billable → انتظار: settle طبق ADR-039

سرور با `python -m app.core.run_server` (Uvicorn 0.54.0 + Early Draining) در subprocess
واقعی اجرا می‌شود؛ SIGTERM به PID اصلی ارسال می‌شود. هیچ تماس پولی ارسال نمی‌شود.
"""

import asyncio
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

BACKEND_DIR = Path(__file__).resolve().parent.parent
MOCK_PORT = 9191
DEV_SECRET = "ci-only-signing-secret-never-use-outside-tests-39"

MOCK = {"mode": "hang", "calls": 0}


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def provider_app() -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def completions():
        MOCK["calls"] += 1
        mode = MOCK["mode"]

        async def hang():
            while True:
                yield b""
                await asyncio.sleep(5)

        async def one_delta_then_hang():
            yield b'data: {"id":"mock","choices":[{"delta":{"content":"partial"}}]}\n\n'
            async for _ in hang():
                yield _

        if mode == "hang":
            return StreamingResponse(hang(), media_type="text/event-stream")
        return StreamingResponse(one_delta_then_hang(), media_type="text/event-stream")

    return app


def _start_provider() -> None:
    config = uvicorn.Config(provider_app(), host="127.0.0.1", port=MOCK_PORT, log_level="warning")
    uvicorn.Server(config).run()


async def _pg_conn():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(_env("TEST_DATABASE_URL"), poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _create_user() -> str:
    from datetime import UTC, datetime

    import jwt as pyjwt
    from app.repositories import credit_accounts as accounts
    from app.repositories import users as users_repo

    engine, sf = await _pg_conn()
    try:
        async with sf() as session:
            phone = f"+989{str(uuid.uuid4().int)[:9]}"
            user = await users_repo.create(session, phone=phone, role="user")
            await accounts.create(session, user_id=user.id, available_balance=5)
            await session.commit()
            uid = str(user.id)
    finally:
        await engine.dispose()
    now = datetime.now(UTC)
    token = pyjwt.encode(
        {"sub": uid, "role": "user", "type": "access", "jti": str(uuid.uuid4()), "iat": now, "exp": now + timedelta(minutes=10)},
        DEV_SECRET,
        algorithm="HS256",
    )
    return uid, token


async def _reservation_status(user_id: str, key: str) -> str | None:
    from app.repositories import reservations as res

    engine, sf = await _pg_conn()
    try:
        async with sf() as session:
            r = await res.get_by_idempotency_key(session, uuid.UUID(user_id), key)
            return r.status if r else None
    finally:
        await engine.dispose()


def _start_server() -> subprocess.Popen:
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "APP_SECRET_KEY": DEV_SECRET,
            "DATABASE_URL": _env("TEST_DATABASE_URL"),
            "REDIS_URL": _env("REDIS_URL", "redis://localhost:6379/0"),
            "LLM_BASE_URL": f"http://127.0.0.1:{MOCK_PORT}",
            "LLM_MODEL": "mock",
            "LLM_API_KEY": "k",
            "LLM_MAX_RETRIES": "0",
            "INFERENCE_MODE": "service",
            "EMBEDDING_BACKEND": "remote",
            "CHAT_STREAM_SHUTDOWN_GRACE_SECONDS": "8",
        }
    )
    return subprocess.Popen(
        [sys.executable, "-m", "app.core.run_server"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=open("server_stdout.log", "w"),
        stderr=open("server_stderr.log", "w"),
    )


async def _wait_health(proc, health_timeout: float = 40) -> bool:
    deadline = time.time() + health_timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            if httpx.get("http://127.0.0.1:8000/health", timeout=1).status_code == 200:
                return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


async def _run_scenario(mode: str, crid_suffix: str) -> tuple[str, str | None]:
    MOCK["mode"] = mode
    uid, token = await _create_user()
    crid = f"linux-{mode}-{crid_suffix}"
    key = f"chat:{uid}:{crid}"
    poll_task = None

    async with httpx.AsyncClient(timeout=40, http2=False) as client:
        async with client.stream(
            "POST", "http://127.0.0.1:8000/api/v1/chat/stream",
            json={"content": "hello", "client_request_id": crid},
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            if resp.status_code != 200:
                return "FAIL", f"stream status {resp.status_code}"
            await asyncio.sleep(0.5)

            async def poll_release():
                t0 = time.time()
                while time.time() - t0 < 25:
                    st = await _reservation_status(uid, key)
                    if st is not None and st in ("released", "settled"):
                        return st, time.time() - t0
                    await asyncio.sleep(0.3)
                return None, time.time() - t0

            poll_task = asyncio.create_task(poll_release())
            # ارسال SIGTERM واقعی به PID اصلی
            os.kill(proc.pid, signal.SIGTERM)

            status, elapsed = await poll_task
            # اتصال را ببند
        # صبر برای خروج process
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            return "FAIL", "server did not exit in time"
    # after proc exit, re-read reservation with independent connection
    final_status = await _reservation_status(uid, key)
    if mode == "hang":
        expect = "released"
    else:
        expect = "settled"
    if final_status != expect:
        return "FAIL", f"expected {expect}, got {final_status}"
    return "PASS", f"{final_status} after {elapsed:.1f}s"


async def main() -> int:
    threading.Thread(target=_start_provider, daemon=True).start()
    time.sleep(2)
    global proc
    proc = _start_server()
    if not await _wait_health(proc):
        print("FAIL server not healthy")
        return 2

    r_a, d_a = await _run_scenario("hang", "a")
    print(f"SCENARIO_A(open-no-billable)={r_a} detail={d_a}")
    r_b, d_b = await _run_scenario("delta", "b")
    print(f"SCENARIO_B(open-after-billable)={r_b} detail={d_b}")

    ok = r_a == "PASS" and r_b == "PASS"
    print("OVERALL_PASS" if ok else "OVERALL_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    proc = None
    sys.exit(asyncio.run(main()))
