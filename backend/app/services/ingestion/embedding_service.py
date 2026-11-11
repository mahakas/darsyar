"""Phase 4: embedding service (R-030/R-031/R-088/R-040).

Wraps a provider callable (InferenceRuntime.embed or RemoteInferenceBackend.embed)
with batch processing, timeout, retry, memory bounds, and dimension validation.
Dimension validity is checked against the active `index_meta` record (R-087/088).
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.core.errors import AppError

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]

# Test-only defaults (owner-approved values flow from settings).
EMBED_BATCH_SIZE = 32
EMBED_TIMEOUT_SECONDS = 30.0
EMBED_MAX_RETRIES = 2
EMBED_BACKOFF_SECONDS = 0.5

MAX_EMBED_BATCH_BYTES = 4 * 1024 * 1024  # rough memory guard


@dataclass(frozen=True)
class EmbedResult:
    vectors: list[list[float]]
    model: str


def _validate_vectors(vectors: list[list[float]], expected_dim: int) -> None:
    for vec in vectors:
        if len(vec) != expected_dim:
            raise AppError("embedding_dim_mismatch", 500, "ابعاد خروجی embedding با قرارداد ناسازگار است.")
        for value in vec:
            if not math.isfinite(value):
                raise AppError("embedding_non_finite", 500, "embedding حاوی NaN/Inf است.")


async def embed_batch(
    texts: list[str],
    *,
    embed: EmbedFn,
    model: str,
    expected_dim: int,
    batch_size: int = EMBED_BATCH_SIZE,
    timeout_seconds: float = EMBED_TIMEOUT_SECONDS,
    max_retries: int = EMBED_MAX_RETRIES,
) -> EmbedResult:
    """Embed texts in bounded batches with timeout/retry and dimension validation."""
    if not texts:
        return EmbedResult(vectors=[], model=model)

    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        estimated_bytes = sum(len(t.encode("utf-8")) for t in batch)
        if estimated_bytes > MAX_EMBED_BATCH_BYTES:
            raise AppError("embedding_batch_too_large", 422, "دستهٔ embedding بیش از حد بزرگ است.")

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                vectors = await asyncio.wait_for(embed(batch), timeout=timeout_seconds)
                _validate_vectors(vectors, expected_dim)
                out.extend(vectors)
                break
            except AppError:
                raise
            except TimeoutError as exc:
                last_exc = exc
            except Exception as exc:  # noqa: BLE001 - provider error
                last_exc = exc
            if attempt < max_retries:
                await asyncio.sleep(EMBED_BACKOFF_SECONDS * (2**attempt))
        else:
            raise AppError("embedding_provider_failure", 502,
                           f"شکست سرویس embedding پس از retry: {type(last_exc).__name__}")

    return EmbedResult(vectors=out, model=model)
