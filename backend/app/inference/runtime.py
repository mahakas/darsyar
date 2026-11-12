"""Inference runtime: real BGE-M3 + BGE-Reranker-v2-M3 lifecycle (Slice E, ADR-036).

Models are loaded once at startup and retained for the process lifetime. Heavy CPU
work runs in a thread executor so the event loop is never blocked. NaN/Inf outputs
and dimension mismatches are rejected. No silent remote fallback.
"""

import asyncio
import logging
from typing import Any

import numpy as np

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class InferenceRuntime:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embed: Any = None
        self._rerank: Any = None
        self._device = settings.inference_device
        self._semaphore = asyncio.Semaphore(settings.inference_concurrency_limit)
        self._load_error: str | None = None
        self._started = False

    @property
    def ready(self) -> bool:
        return self._embed is not None and self._rerank is not None and self._load_error is None

    @property
    def started(self) -> bool:
        return self._started

    @property
    def load_error(self) -> str | None:
        return self._load_error

    async def startup(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._load_sync)
            if self._settings.inference_warmup:
                await loop.run_in_executor(None, self._warmup_sync)
            self._started = True
        except Exception as exc:  # noqa: BLE001
            self._load_error = f"{type(exc).__name__}: {exc}"
            logger.exception("inference_startup_failed")
            raise AppError("model_runtime_not_ready", 503, "مدل‌های inference بارگذاری نشدند.") from exc

    def _load_sync(self) -> None:
        from FlagEmbedding import BGEM3FlagModel, FlagReranker  # type: ignore[import-not-found]

        use_fp16 = self._device == "cuda"
        self._embed = BGEM3FlagModel(self._settings.embedding_model, use_fp16=use_fp16, device=self._device)
        self._rerank = FlagReranker(self._settings.reranker_model, use_fp16=use_fp16, device=self._device)

    def _warmup_sync(self) -> None:
        self._embed.encode(["سلام"], return_dense=True, return_sparse=False, return_colbert_vecs=False)
        pairs = [["سلام", "دنیا"]]
        if hasattr(self._rerank, "compute_score"):
            self._rerank.compute_score(pairs)
        else:
            self._rerank.predict(pairs)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.ready:
            raise AppError("model_runtime_not_ready", 503, "سرویس inference آماده نیست.")
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(None, self._embed_sync, texts),
                    timeout=self._settings.inference_timeout_seconds,
                )
            except TimeoutError as exc:
                raise AppError("inference_timeout", 504, "سرویس inference مهلت را رد کرد.") from exc

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        out = self._embed.encode(
            texts, return_dense=True, return_sparse=False, return_colbert_vecs=False
        )
        arr = np.asarray(out["dense_vecs"], dtype="float32")
        if arr.ndim != 2 or arr.shape[1] != self._settings.embedding_dim:
            raise AppError("embedding_dim_mismatch", 500, "ابعاد خروجی embedding با قرارداد ناسازگار است.")
        if not np.isfinite(arr).all():
            raise AppError("embedding_non_finite", 500, "embedding حاوی NaN/Inf است.")
        return [row.tolist() for row in arr]

    async def rerank(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not self.ready:
            raise AppError("model_runtime_not_ready", 503, "سرویس inference آماده نیست.")
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(None, self._rerank_sync, pairs),
                    timeout=self._settings.inference_timeout_seconds,
                )
            except TimeoutError as exc:
                raise AppError("inference_timeout", 504, "سرویس inference مهلت را رد کرد.") from exc

    def _rerank_sync(self, pairs: list[tuple[str, str]]) -> list[float]:
        list_pairs = [list(p) for p in pairs]
        if hasattr(self._rerank, "compute_score"):
            scores = self._rerank.compute_score(list_pairs)
        else:
            scores = self._rerank.predict(list_pairs)
        out = [float(s) for s in scores]
        if not all(np.isfinite(s) for s in out):
            raise AppError("rerank_non_finite", 500, "امتیاز rerank حاوی NaN/Inf است.")
        return out
