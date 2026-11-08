# ruff: noqa: ASYNC210,ASYNC221,ASYNC251,ASYNC110  (اسکریپت ارکستراسیون Linux CI؛ blocking عمدی است)
"""آزمون process-level Linux (GitHub CI): Open SSE + SIGTERM واقعی + تأیید مالی PostgreSQL.

هر سناریو سرورِ جداگانه‌ای (python -m app.core.run_server / Uvicorn 0.54.0) را در
subprocess شروع می‌کند، SIGTERM واقعی به PID اصلی می‌دهد، و بعد از خروج، با اتصال
مستقل PostgreSQL وضعیت نهایی رزرو را می‌خواند.

  A) بدون خروجی billable            -> reservation باید `released` شود
  B) پس از حداقل یک delta billable   -> reservation باید `settled` شود (ADR-039)

خروجی مورد انتظار:
  SCENARIO_A(open-no-billable)=PASS
  SCENARIO_B(open-after-billable)=PASS
  OVERALL_PASS
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
GRACE_SECONDS = os.environ.get("CHAT_STREAM_SHUTDOWN_GRACE_SECONDS", "8")

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


def start_provider() -> None:
    config = uvicorn.Config(provider_app(), host="127.0.0.1", port=MOCK_PORT, log_level="warning")
    uvicorn.Server(config).run()


async def _pg_sessionmaker():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(_env("TEST_DATABASE_URL"), poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def create_user() -> tuple[str, str]:
    from datetime import UTC, datetime

    import jwt as pyjwt
    from app.repositories import credit_accounts as accounts
    from app.repositories import users as users_repo

    engine, sf = await _pg_sessionmaker()
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


async def reservation_status(user_id: str, key: str) -> str | None:
    from app.repositories import reservations as res

    engine, sf = await _pg_sessionmaker()
    try:
        async with sf() as session:
            r = await res.get_by_idempotency_key(session, uuid.UUID(user_id), key)
            return r.status if r else None
    finally:
        await engine.dispose()


def start_server(tag: str) -> subprocess.Popen:
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
            "CHAT_STREAM_SHUTDOWN_GRACE_SECONDS": GRACE_SECONDS,
        }
    )
    return subprocess.Popen(
        [sys.executable, "-m", "app.core.run_server"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=open(f"server_{tag}_stdout.log", "w"),
        stderr=open(f"server_{tag}_stderr.log", "w"),
    )


async def wait_health(proc, health_timeout: float = 40) -> bool:
    deadline = time.time() + health_timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            if httpx.get("http://127.0.0.1:8000/health", timeout=1).status_code == 200:
                return True
        except Exception:
            pass
        await asyncio.sleep(0.5)  # noqa: ASYNC110
    return False


async def run_scenario(mode: str, tag: str) -> tuple[str, str]:
    MOCK["mode"] = mode
    MOCK["calls"] = 0
    proc = start_server(tag)
    try:
        if not await wait_health(proc):
            return "FAIL", "server not healthy / startup failed"
        uid, token = await create_user()
        crid = f"linux-{mode}-{tag}"
        key = f"chat:{uid}:{crid}"
        poll_task = None
        calls_before = MOCK["calls"]

        async with httpx.AsyncClient(timeout=40) as client:
            async with client.stream(
                "POST", "http://127.0.0.1:8000/api/v1/chat/stream",
                json={"content": "hello", "client_request_id": crid},
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                if resp.status_code != 200:
                    return "FAIL", f"stream status {resp.status_code}"
                if mode == "delta":
                    # مصرف تا اولین delta billable تا ثابت شود خروجی واقعاً تولید شده است
                    emitted = False
                    async for line in resp.aiter_lines():
                        if line.startswith("event:delta"):
                            emitted = True
                            break
                    if not emitted:
                        return "FAIL", "no billable delta emitted before SIGTERM"
                else:
                    # scenario A: provider فعال ولی بدون خروجی billable
                    if calls_before == MOCK["calls"]:
                        await asyncio.sleep(0.5)  # noqa: ASYNC110
                    if MOCK["calls"] <= calls_before:
                        return "FAIL", "provider not invoked (no reservation flow)"
                    await asyncio.sleep(0.3)  # noqa: ASYNC110

                async def poll_terminal():
                    t0 = time.time()
                    while time.time() - t0 < 30:
                        st = await reservation_status(uid, key)
                        if st in ("released", "settled"):
                            return st, time.time() - t0
                        await asyncio.sleep(0.3)  # noqa: ASYNC110
                    return None, time.time() - t0

                poll_task = asyncio.create_task(poll_terminal())
                os.kill(proc.pid, signal.SIGTERM)
                status, elapsed = await poll_task
            # اتصال بسته شد

        try:
            proc.wait(timeout=40)
        except subprocess.TimeoutExpired:
            proc.kill()
            return "FAIL", "server did not exit in time"

        final_status = await reservation_status(uid, key)
        expect = "released" if mode == "hang" else "settled"
        exit_code = proc.returncode if proc.poll() is not None else None
        diag = (
            f"res_after={final_status} expect={expect} poll={status} elapsed={elapsed:.1f}s "
            f"provider_calls={MOCK['calls']} exit_code={exit_code}"
        )
        if final_status != expect:
            return "FAIL", f"{diag} (expected {expect}, got {final_status})"
        if status != expect:
            return "FAIL", f"{diag} (terminal poll {status} != {expect})"
        return "PASS", diag
    except Exception as exc:  # noqa: BLE001
        return "FAIL", f"unhandled: {type(exc).__name__}: {exc}"
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


async def main() -> int:
    threading.Thread(target=start_provider, daemon=True).start()
    time.sleep(2)

    r_a, d_a = await run_scenario("hang", "a")
    print(f"SCENARIO_A(open-no-billable)={r_a} detail={d_a}")
    MOCK["calls"] = 0
    r_b, d_b = await run_scenario("delta", "b")
    print(f"SCENARIO_B(open-after-billable)={r_b} detail={d_b}")

    ok = r_a == "PASS" and r_b == "PASS"
    print("OVERALL_PASS" if ok else "OVERALL_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
