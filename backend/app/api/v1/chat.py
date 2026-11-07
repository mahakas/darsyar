"""Chat streaming endpoint (Slice C+D+F): authenticated fetch-based SSE with financial lifecycle.

Slice F: drain-aware admission, active-stream tracking, and low-cardinality metrics.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_rate_limit, get_current_user, get_db
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.metrics import METRICS
from app.core.ratelimit import RateLimitRule
from app.core.shutdown import SHUTDOWN_STATE
from app.models.user import User
from app.schemas.conversation import ChatStreamRequest
from app.services.chat_service import ChatStreamService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(
    payload: ChatStreamRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    settings = get_settings()

    # Drain guard: reject new streams during shutdown BEFORE any admission/reservation.
    if SHUTDOWN_STATE.draining:
        raise AppError("service_draining", 503, "سرویس در حال خاموشی است؛ بعداً تلاش کنید.")

    await check_rate_limit(
        request,
        f"chat:user:{user.id}",
        RateLimitRule(limit=settings.chat_rate_user, window_seconds=60),
        degraded_allowed=True,
    )
    last_event_id = request.headers.get("Last-Event-ID")

    def on_financial(outcome: str) -> None:
        METRICS.financial_outcome.inc({"outcome": outcome})

    service = ChatStreamService(on_financial=on_financial)
    # Pre-stream validation: ownership + idempotency fingerprint conflict must return a
    # standard JSON error (404/409) BEFORE the SSE response begins, not a broken 200.
    await service.preflight(payload, user)

    async def gen() -> AsyncIterator[str]:
        task = asyncio.current_task()
        if task is not None:
            SHUTDOWN_STATE.active_streams.add(task)
        started = time.perf_counter()
        first_billable = None
        METRICS.chat_active.inc()
        METRICS.chat_started.inc()
        try:
            async for event in service.stream_chat(payload, user, last_event_id):
                if first_billable is None and "event:delta" in event:
                    first_billable = time.perf_counter()
                    METRICS.ttfb.observe(first_billable - started)
                yield event
        except asyncio.CancelledError:
            METRICS.chat_cancelled.inc()
            raise
        except Exception:
            METRICS.chat_failed.inc()
            raise
        else:
            METRICS.chat_completed.inc()
        finally:
            METRICS.chat_active.dec()
            METRICS.stream_duration.observe(time.perf_counter() - started)
            if task is not None:
                SHUTDOWN_STATE.active_streams.discard(task)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
