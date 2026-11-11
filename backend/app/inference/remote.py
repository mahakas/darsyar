"""Remote inference backend (OpenAI-compatible embedding + generic rerank endpoint).

Used when `EMBEDDING_BACKEND=remote`. Embedding and reranking may use
separate provider endpoints and credentials. No local ML model is loaded.
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
        timeout = httpx.Timeout(settings.inference_timeout_seconds, connect=10.0)
        self._client = httpx.AsyncClient(
            base_url=settings.embedding_remote_base_url.rstrip("/"),
            timeout=timeout,
        )
        self._rerank_client = (
            httpx.AsyncClient(
                base_url=settings.rerank_remote_base_url.rstrip("/"),
                timeout=timeout,
            )
            if settings.rerank_remote_base_url
            else None
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
        if self._rerank_client is not None:
            await self._rerank_client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.ready:
            raise AppError("model_runtime_not_ready", 503, "سرویس inference آماده نیست.")
        if not texts:
            return []
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
                raise AppError(
                    "inference_remote_error", 502,
                    f"شکست سرویس embedding دورستی: {type(exc).__name__}",
                ) from exc
            if not isinstance(data, list) or len(data) != len(texts):
                raise AppError("inference_remote_malformed", 502, "پاسخ embedding دورستی ناسازگار است.")
            vectors: list[list[float]] = []
            for item in data:
                vec = item.get("embedding") if isinstance(item, dict) else None
                if not isinstance(vec, list):
                    raise AppError("inference_remote_malformed", 502, "پاسخ embedding دورستی ناسازگار است.")
                try:
                    arr = np.asarray(vec, dtype="float32")
                except (TypeError, ValueError) as exc:
                    raise AppError("inference_remote_malformed", 502, "پاسخ embedding دورستی ناسازگار است.") from exc
                if arr.ndim != 1 or arr.shape[0] != s.embedding_dim:
                    raise AppError("embedding_dim_mismatch", 500, "ابعاد خروجی embedding با قرارداد ناسازگار است.")
                if not np.isfinite(arr).all():
                    raise AppError("embedding_non_finite", 500, "embedding حاوی NaN/Inf است.")
                vectors.append(arr.tolist())
            return vectors

    async def rerank(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        s = self._settings
        if not s.rerank_remote_base_url or not s.rerank_remote_model or self._rerank_client is None:
            raise AppError("rerank_remote_not_configured", 503, "rerank دورستی پیکربندی نشده است.")
        if not self.ready:
            raise AppError("model_runtime_not_ready", 503, "سرویس inference آماده نیست.")

        query = pairs[0][0]
        documents = [pair[1] for pair in pairs]
        headers: dict[str, str] = {}
        if s.rerank_remote_api_key and s.rerank_remote_api_key.get_secret_value():
            headers["Authorization"] = f"Bearer {s.rerank_remote_api_key.get_secret_value()}"

        async with self._semaphore:
            try:
                response = await self._rerank_client.post(
                    "/rerank",
                    json={"model": s.rerank_remote_model, "query": query, "documents": documents},
                    headers=headers,
                )
                response.raise_for_status()
                results = response.json().get("results", [])
            except httpx.HTTPError as exc:
                raise AppError(
                    "inference_remote_error", 502,
                    f"شکست سرویس rerank دورستی: {type(exc).__name__}",
                ) from exc

        if not isinstance(results, list) or len(results) != len(pairs):
            raise AppError("inference_remote_malformed", 502, "پاسخ rerank دورستی ناسازگار است.")

        indexed_scores: dict[int, float] = {}
        try:
            for item in results:
                if not isinstance(item, dict):
                    raise ValueError("invalid result item")
                index = item.get("index")
                if not isinstance(index, int) or index < 0 or index >= len(pairs) or index in indexed_scores:
                    raise ValueError("invalid result index")
                score = float(item["relevance_score"])
                if not np.isfinite(score):
                    raise ValueError("non-finite score")
                indexed_scores[index] = score
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError("inference_remote_malformed", 502, "پاسخ rerank دورستی ناسازگار است.") from exc

        if set(indexed_scores) != set(range(len(pairs))):
            raise AppError("inference_remote_malformed", 502, "پاسخ rerank دورستی ناسازگار است.")
        return [indexed_scores[index] for index in range(len(pairs))]
