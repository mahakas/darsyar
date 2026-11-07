"""Remote inference backend (OpenAI-compatible embedding + generic rerank endpoint).

Used when `EMBEDDING_BACKEND=remote` (the user's online-embedding configuration).
No local ML model is loaded. There is no silent fallback to the local service.
"""

import asyncio
import logging

import httpx
import numpy as np

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class RemoteInferenceBackend:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.embedding_remote_base_url.rstrip("/"),
            timeout=httpx.Timeout(settings.inference_timeout_seconds, connect=10.0),
        )
        self._semaphore = asyncio.Semaphore(settings.inference_concurrency_limit)
        self._started = False
        self._load_error: str | None = None

    @property
    def started(self) -> bool:
        return self._started

    @property
    def ready(self) -> bool:
        return self._started and self._load_error is None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    async def startup(self) -> None:
        s = self._settings
        if not s.embedding_remote_base_url or not s.embedding_remote_model:
            self._load_error = "embedding remote base_url/model not configured"
            raise AppError("model_runtime_not_ready", 503, "embedding دورستی پیکربندی نشده است.")
        if not (s.embedding_remote_api_key and s.embedding_remote_api_key.get_secret_value()):
            self._load_error = "embedding remote api key not configured"
            raise AppError("model_runtime_not_ready", 503, "کلید API embedding دورستی پیکربندی نشده است.")
        self._started = True

    async def aclose(self) -> None:
        await self._client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.ready:
            raise AppError("model_runtime_not_ready", 503, "سرویس inference آماده نیست.")
        s = self._settings
        api_key = s.embedding_remote_api_key.get_secret_value() if s.embedding_remote_api_key else ""
        async with self._semaphore:
            try:
                response = await self._client.post(
                    "/embeddings",
                    json={"model": s.embedding_remote_model, "input": texts},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                response.raise_for_status()
                data = response.json().get("data", [])
            except httpx.HTTPError as exc:
                raise AppError("inference_remote_error", 502, f"شکست سرویس embedding دورستی: {type(exc).__name__}") from exc
            if len(data) != len(texts):
                raise AppError("inference_remote_malformed", 502, "پاسخ embedding دورستی ناسازگار است.")
            vectors: list[list[float]] = []
            for item in data:
                vec = item.get("embedding")
                if not isinstance(vec, list):
                    raise AppError("inference_remote_malformed", 502, "پاسخ embedding دورستی ناسازگار است.")
                arr = np.asarray(vec, dtype="float32")
                if arr.ndim != 1 or arr.shape[0] != s.embedding_dim:
                    raise AppError("embedding_dim_mismatch", 500, "ابعاد خروجی embedding با قرارداد ناسازگار است.")
                if not np.isfinite(arr).all():
                    raise AppError("embedding_non_finite", 500, "embedding حاوی NaN/Inf است.")
                vectors.append(arr.tolist())
            return vectors

    async def rerank(self, pairs: list[tuple[str, str]]) -> list[float]:
        s = self._settings
        if not s.rerank_remote_base_url or not s.rerank_remote_model:
            raise AppError("rerank_remote_not_configured", 503, "rerank دورستی پیکربندی نشده است.")
        if not self.ready:
            raise AppError("model_runtime_not_ready", 503, "سرویس inference آماده نیست.")
        query = pairs[0][0]
        documents = [p[1] for p in pairs]
        async with self._semaphore:
            try:
                response = await self._client.post(
                    "/rerank",
                    json={"model": s.rerank_remote_model, "query": query, "documents": documents},
                    headers={"Authorization": f"Bearer {(s.rerank_remote_api_key.get_secret_value() if s.rerank_remote_api_key else '')}"},
                )
                response.raise_for_status()
                results = response.json().get("results", [])
            except httpx.HTTPError as exc:
                raise AppError("inference_remote_error", 502, f"شکست سرویس rerank دورستی: {type(exc).__name__}") from exc
            ordered = sorted(results, key=lambda r: r.get("index", 0))
            scores = [float(r.get("relevance_score")) for r in ordered]
            if len(scores) != len(pairs):
                raise AppError("inference_remote_malformed", 502, "پاسخ rerank دورستی ناسازگار است.")
            if not all(np.isfinite(sc) for sc in scores):
                raise AppError("rerank_non_finite", 500, "امتیاز rerank حاوی NaN/Inf است.")
            return scores
