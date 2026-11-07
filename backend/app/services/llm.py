"""درگاه provider سازگار OpenAI (NVIDIA/OpenAI) برای چت استریم (R-040/R-044).

- بدون SDK اختصاصی vendor در لایهٔ دامنه؛ فقط `httpx.AsyncClient`.
- timeout صریح connect/read/request؛ retry کران‌دار فقط پیش از نخستین توکن.
- لغو (cancel) از طریق ابطال وظیفهٔ caller به جریان httpx منتقل می‌شود.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class ChatChunk:
    delta: str
    request_id: str | None = None
    done: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ChatRequest:
    messages: list[dict[str, str]]
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None


class LLMProvider(Protocol):
    def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]: ...


class OpenAICompatibleProvider:
    """adapter سازگار OpenAI برای NVIDIA/OpenAI و دیگر providers."""

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout_seconds, connect=10.0),
            headers={"Authorization": f"Bearer {self._api_key}"} if self._api_key else {},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        payload: dict[str, object] = {
            "model": req.model or self._model,
            "messages": req.messages,
            "stream": True,
        }
        if req.max_tokens is not None:
            payload["max_tokens"] = req.max_tokens
        if req.temperature is not None:
            payload["temperature"] = req.temperature
        try:
            async with self._client.stream("POST", "/v1/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        yield ChatChunk(delta="", done=True)
                        return
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choice = (obj.get("choices") or [{}])[0]
                    delta = (choice.get("delta") or {}).get("content") or ""
                    if delta:
                        yield ChatChunk(delta=delta, request_id=obj.get("id"))
        except httpx.HTTPError as exc:
            yield ChatChunk(delta="", done=True, error=f"provider_http_error: {type(exc).__name__}")


def get_llm_provider() -> OpenAICompatibleProvider | None:
    """factory مبتنی بر تنظیمات؛ اگر پیکربندی ناقص باشد None برمی‌گرداند."""
    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_model:
        return None
    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
    return OpenAICompatibleProvider(
        base_url=settings.llm_base_url,
        api_key=api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


async def run_chat_with_bounded_retry(
    provider: LLMProvider,
    req: ChatRequest,
    *,
    max_retries: int,
    on_chunk: "Callable[[ChatChunk], None]",
) -> None:
    """پخش استریم با retry فقط پیش از نخستین توکن.

    - پیش از نخستین delta محتوایی: خطا → تا `max_retries` تلاش مجدد.
    - پس از نخستین delta: هر خطا مستقیم به caller گزارش می‌شود (بدون retry)
      تا صورتحساب/settle دو بار اعمال نشود (R-13x/ADR-039).
    - لغو (CancelledError) به caller منتقل می‌شود.
    """
    attempt = 0
    while True:
        emitted = False
        error: str | None = None
        try:
            async for chunk in provider.stream_chat(req):
                if chunk.delta and not emitted:
                    emitted = True
                if chunk.error:
                    error = chunk.error
                    break
                on_chunk(chunk)
                if chunk.done:
                    return
        except asyncio.CancelledError:
            raise
        if emitted and not error:
            return
        if emitted and error:
            on_chunk(ChatChunk(delta="", done=True, error=error))
            return
        if attempt >= max_retries:
            on_chunk(ChatChunk(delta="", done=True, error=error or "provider_failed"))
            return
        attempt += 1
