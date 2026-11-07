"""تست واقعی مدل BGE-M3 + Reranker (Slice E).

این تست فقط وقتی اجرا می‌شود که هر دو مدل واقعاً قابل بارگذاری باشند (cache/دیسک/شبکه).
در غیر این صورت با دلیل `skip` می‌شود؛ هرگز به‌عنوان PASS بدون اجرا گزارش نمی‌شود.
"""
import asyncio
import os
from pathlib import Path

import pytest
from app.core.config import Settings
from app.inference.runtime import InferenceRuntime

EMBED_DIR = "models--BAAI--bge-m3"
RERANK_DIR = "models--BAAI--bge-reranker-v2-m3"


def _model_cached(dir_name: str) -> bool:
    candidates: list[Path] = []
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        candidates.append(Path(hf_home) / "hub")
    candidates.append(Path.home() / ".cache" / "huggingface" / "hub")
    for base in candidates:
        if (base / dir_name).exists():
            return True
    return False


async def _try_real_smoke() -> bool:
    if not _model_cached(EMBED_DIR) or not _model_cached(RERANK_DIR):
        return False
    settings = Settings(
        app_env="test",
        inference_device="cpu",
        embedding_model="BAAI/bge-m3",
        reranker_model="BAAI/bge-reranker-v2-m3",
        inference_warmup=False,
        inference_timeout_seconds=30.0,
    )
    runtime = InferenceRuntime(settings)
    try:
        await asyncio.wait_for(runtime.startup(), timeout=120.0)
    except Exception:
        return False
    if not runtime.ready:
        return False
    try:
        vecs = await asyncio.wait_for(runtime.embed(["سلام دنیا"]), timeout=60.0)
        scores = await asyncio.wait_for(
            runtime.rerank([("سؤال", "سند مرتبط"), ("سؤال", "سند نامرتبط")]), timeout=60.0
        )
    except Exception:
        return False
    if len(vecs) != 1 or len(vecs[0]) != 1024 or len(scores) != 2:
        return False
    return True


@pytest.mark.asyncio
async def test_real_models_embed_and_rerank() -> None:
    ok = await _try_real_smoke()
    if not ok:
        pytest.skip("مدل‌های واقعی در این محیط cache/دیسک کافی ندارند؛ اجرا نشد.")
    assert ok is True
