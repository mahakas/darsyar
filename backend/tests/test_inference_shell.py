"""تست قرارداد سرویس inference (Slice E) با runtime جعلی؛ بدون دانلود/لود مدل واقعی.

مدل‌های واقعی در `tests/test_inference_runtime_db.py` (skip-gated) پوشش داده می‌شوند.
"""

import pytest
from app.core.errors import AppError
from app.inference.main import create_app
from httpx import ASGITransport, AsyncClient


class FakeRuntime:
    def __init__(self, *, ready: bool = True, started: bool = True, load_error: str | None = None) -> None:
        self._ready = ready
        self._started = started
        self._load_error = load_error

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def started(self) -> bool:
        return self._started

    @property
    def load_error(self) -> str | None:
        return self._load_error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._ready:
            raise AppError("model_runtime_not_ready", 503, "مدل‌های inference آماده نیستند.")
        return [[0.5] * 1024 for _ in texts]

    async def rerank(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not self._ready:
            raise AppError("model_runtime_not_ready", 503, "مدل‌های inference آماده نیستند.")
        return [0.9 - 0.1 * i for i in range(len(pairs))]


@pytest.mark.asyncio
async def test_health_reports_mode() -> None:
    app = create_app(runtime=FakeRuntime())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ready_ok_when_models_ready() -> None:
    app = create_app(runtime=FakeRuntime(ready=True))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_not_ready_returns_503_contract() -> None:
    app = create_app(runtime=FakeRuntime(ready=False, started=True))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        r_ready = await client.get("/ready")
        r_embed = await client.post("/embed", json={"texts": ["متن"]})
    assert r_ready.status_code == 503
    assert r_embed.status_code == 503
    body = r_embed.json()
    assert set(body.keys()) == {"code", "message", "request_id"}
    assert body["code"] == "model_runtime_not_ready"


@pytest.mark.asyncio
async def test_embed_success_1024_dim() -> None:
    app = create_app(runtime=FakeRuntime())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        response = await client.post("/embed", json={"texts": ["سلام دنیا"]})
    assert response.status_code == 200
    body = response.json()
    assert len(body["embeddings"]) == 1
    assert len(body["embeddings"][0]) == 1024


@pytest.mark.asyncio
async def test_rerank_success_scores() -> None:
    app = create_app(runtime=FakeRuntime())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        response = await client.post("/rerank", json={"query": "سؤال", "documents": ["الف", "ب"]})
    assert response.status_code == 200
    assert len(response.json()["scores"]) == 2


@pytest.mark.asyncio
async def test_invalid_input_422() -> None:
    app = create_app(runtime=FakeRuntime())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        response = await client.post("/embed", json={"texts": []})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_api_process_does_not_import_heavy_ml_at_module_level() -> None:
    """اطمینان: FlagEmbedding فقط داخل تابع runtime لود می‌شود؛ نه در سطح ماژول و نه در main."""
    from pathlib import Path

    main_src = Path("app/inference/main.py").read_text(encoding="utf-8")
    runtime_src = Path("app/inference/runtime.py").read_text(encoding="utf-8")
    assert "FlagEmbedding" not in main_src
    top_level = [
        line
        for line in runtime_src.splitlines()
        if (line.startswith("import FlagEmbedding") or line.startswith("from FlagEmbedding")) and not line.startswith(" ")
    ]
    assert top_level == [], "FlagEmbedding باید فقط داخل تابع (indented) لود شود"
