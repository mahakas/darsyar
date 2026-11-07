"""تست واحد درگاه LLM (ریslice A) با respx؛ بدون تماس شبکهٔ واقعی (R-216)."""

from __future__ import annotations

import pytest
import respx
from app.services.llm import (
    ChatChunk,
    ChatRequest,
    OpenAICompatibleProvider,
    run_chat_with_bounded_retry,
)
from httpx import Response

BASE = "http://llm.test"


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(base_url=BASE, api_key="secret", model="nvidia-model", timeout_seconds=5.0)


def _sse(body: str) -> Response:
    return Response(200, content=body.encode("utf-8"), headers={"content-type": "text/event-stream"})


@respx.mock
@pytest.mark.asyncio
async def test_stream_chat_parses_deltas_and_done() -> None:
    body = (
        'data: {"id":"req1","choices":[{"delta":{"content":"سلام"}}]}\n'
        'data: {"id":"req1","choices":[{"delta":{"content":" دنیا"}}]}\n'
        "data: [DONE]\n"
    )
    respx.post(f"{BASE}/v1/chat/completions").mock(return_value=_sse(body))
    p = _provider()
    chunks = []
    async for c in p.stream_chat(ChatRequest(messages=[{"role": "user", "content": "hi"}])):
        chunks.append(c)
    assert "".join(c.delta for c in chunks if c.delta) == "سلام دنیا"
    assert chunks[-1].done
    await p.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_stream_chat_http_error_emits_error_chunk() -> None:
    respx.post(f"{BASE}/v1/chat/completions").mock(return_value=Response(500))
    p = _provider()
    chunks = []
    async for c in p.stream_chat(ChatRequest(messages=[{"role": "user", "content": "hi"}])):
        chunks.append(c)
    assert chunks[-1].done
    assert chunks[-1].error is not None and "provider_http_error" in chunks[-1].error
    await p.aclose()


class _FlakyProvider:
    """اولین تلاش خطا، سپس موفق."""

    def __init__(self) -> None:
        self.calls = 0

    async def stream_chat(self, req: ChatRequest):
        self.calls += 1
        if self.calls == 1:
            yield ChatChunk(delta="", done=True, error="provider_failed")
            return
        yield ChatChunk(delta="ok")
        yield ChatChunk(delta="", done=True)


@pytest.mark.asyncio
async def test_bounded_retry_before_first_token() -> None:
    provider = _FlakyProvider()
    collected: list[ChatChunk] = []
    await run_chat_with_bounded_retry(provider, ChatRequest(messages=[{"role": "user", "content": "x"}]), max_retries=2, on_chunk=collected.append)
    assert provider.calls == 2
    assert "".join(c.delta for c in collected if c.delta) == "ok"
    assert collected[-1].done


class _NeverSuccessProvider:
    async def stream_chat(self, req: ChatRequest):
        yield ChatChunk(delta="", done=True, error="provider_failed")


@pytest.mark.asyncio
async def test_bounded_retry_gives_up_after_max() -> None:
    provider = _NeverSuccessProvider()
    collected: list[ChatChunk] = []
    await run_chat_with_bounded_retry(provider, ChatRequest(messages=[{"role": "user", "content": "x"}]), max_retries=2, on_chunk=collected.append)
    assert collected[-1].done
    assert collected[-1].error == "provider_failed"
