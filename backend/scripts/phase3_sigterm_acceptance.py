# ruff: noqa: ASYNC210,ASYNC221,ASYNC251,ASYNC110  (اسکریپت ارکستراسیون؛ blocking عمدی است)
"""پذیرش process-level: SIGTERM واقعی در Linux (Docker) برای چت استریم.

- اجرای تصویر darsyar-api:test با --network host در برابر PostgreSQL/Redis تست محلی.
- Provider mock محلی (hang) روی پورت 9101 تا stream فعال بماند.
- ارسال SIGTERM به کانتینر و بررسی drain + وضعیت مالی نهایی.
این اسکریپت فقط در محیطی که Docker/Linux signal دارد قابل اجراست.
"""

import asyncio
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
ROOT = BACKEND_DIR.parent
PROVIDER_PORT = 9101
CONTAINER = "p3-sigterm"
IMAGE = "darsyar-api:test"
DEV_SECRET = "DevSecret0123456789abcdef0123456789abcdef"  # >=32 bytes, dev-only


def _read_env(key: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError(f"{key} not found in .env")


TEST_DB_URL = _read_env("TEST_DATABASE_URL")


def _to_host_docker_internal(url: str) -> str:
    import re

    # postgresql+asyncpg://user:pw@host:5432/db -> host.docker.internal
    return re.sub(r"@([^:/]+):", "@host.docker.internal:", url)


def provider_app() -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def completions():
        async def hang():
            while True:
                yield b""
                await asyncio.sleep(5)
        return StreamingResponse(hang(), media_type="text/event-stream")

    return app


async def mint_token(user_id: str) -> str:
    """توکن access واقعی با همان DEV_SECRET که به container داده می‌شود."""
    from datetime import UTC, datetime

    import jwt as pyjwt

    now = datetime.now(UTC)
    payload = {
        "sub": user_id, "role": "user", "type": "access", "jti": str(uuid.uuid4()),
        "iat": now, "exp": now + timedelta(minutes=10),
    }
    return pyjwt.encode(payload, DEV_SECRET, algorithm="HS256")


async def create_user() -> str:
    from app.repositories import credit_accounts as accounts
    from app.repositories import users as users_repo
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    phone = f"+989{str(uuid.uuid4().int)[:9]}"
    async with sf() as session:
        user = await users_repo.create(session, phone=phone, role="user")
        await accounts.create(session, user_id=user.id, available_balance=5)
        await session.commit()
        uid = str(user.id)
    await engine.dispose()
    return uid


async def get_reservation_status(user_id: str, key: str) -> str | None:
    from app.repositories import reservations as res
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sf() as session:
            r = await res.get_by_idempotency_key(session, uuid.UUID(user_id), key)
            return r.status if r else None
    finally:
        await engine.dispose()


def start_provider() -> None:
    config = uvicorn.Config(provider_app(), host="127.0.0.1", port=PROVIDER_PORT, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()


def docker_run() -> None:
    subprocess.run(f"docker rm -f {CONTAINER}", shell=True, capture_output=True, text=True)
    env_block = " ".join(
        f'-e {k}="{v}"'
        for k, v in {
            "APP_ENV": "development",
            "APP_SECRET_KEY": DEV_SECRET,
            "DATABASE_URL": _to_host_docker_internal(TEST_DB_URL),
            "REDIS_URL": "redis://host.docker.internal:6379/0",
            "LLM_BASE_URL": f"http://host.docker.internal:{PROVIDER_PORT}",
            "LLM_MODEL": "mock",
            "LLM_API_KEY": "k",
            "LLM_MAX_RETRIES": "0",
            "INFERENCE_MODE": "service",
            "EMBEDDING_BACKEND": "remote",
            "CHAT_STREAM_SHUTDOWN_GRACE_SECONDS": "10",
        }.items()
    )
    subprocess.run(
        f"docker run -d --name {CONTAINER} -p 8123:8000 {env_block} {IMAGE}",
        shell=True, check=True, capture_output=True, text=True,
    )


async def main() -> int:
    start_provider()
    time.sleep(2)
    docker_run()
    base = "http://127.0.0.1:8123"
    try:
        # wait healthy
        for _ in range(60):
            try:
                r = httpx.get(f"{base}/health", timeout=2)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            print("FAIL container did not become healthy")
            return 2

        uid = await create_user()
        token = await mint_token(uid)
        crid = "sigterm-hang-0001"
        key = f"chat:{uid}:{crid}"
        # open a hanging stream and KEEP it open across SIGTERM so the server must drain/cancel it
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream(
                "POST", f"{base}/api/v1/chat/stream",
                json={"content": "hello", "client_request_id": crid},
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                if resp.status_code != 200:
                    print(f"FAIL stream status {resp.status_code}")
                    return 3
                # read a bit to ensure it is active
                await asyncio.sleep(1.0)
                # send SIGTERM while the stream is still open
                subprocess.run(f"docker kill --signal=SIGTERM {CONTAINER}", shell=True, check=True, capture_output=True)
                # wait until the server drains and releases the hanging reservation (max 20s)
                release_t0 = time.time()
                released = None
                while time.time() - release_t0 < 55:
                    released = await get_reservation_status(uid, key)
                    if released == "released":
                        break
                    await asyncio.sleep(0.5)
                release_sec = time.time() - release_t0
                print(f"reservation_release_sec={release_sec:.1f} released={released}")
            # connection closed now; measure process exit
            t0 = time.time()
            rc = subprocess.run(f"docker wait {CONTAINER}", shell=True, capture_output=True, text=True)
            elapsed = time.time() - t0
            print(f"container_exit_code={rc.stdout.strip()} exit_wait_sec={elapsed:.1f}")

        # container logs
        logs = subprocess.run(f"docker logs {CONTAINER} 2>&1", shell=True, capture_output=True, text=True).stdout
        has_shutdown_started = "shutdown_started" in logs or "shutdown_completed" in logs
        print(f"logs_have_shutdown_events={has_shutdown_started}")
        # reservation terminal status after cancellation (hang provider => no billable => release)
        status = await get_reservation_status(uid, key)
        print(f"reservation_status={status}")

        ok = True
        if elapsed > 30:
            print("FAIL container exit took too long")
            ok = False
        if not has_shutdown_started:
            print("FAIL no shutdown lifecycle logs")
            ok = False
        if status != "released":
            print(f"FAIL expected released, got {status}")
            ok = False
        print("PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        subprocess.run(f"docker rm -f {CONTAINER}", shell=True, capture_output=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
