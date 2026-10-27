"""تست پوستهٔ سرویس inference: شکل خطای استاندارد (R-054) و عدم وانمود به embedding واقعی."""

import pytest
from app.inference.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_inference_shell_health_reports_shell_mode() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mode"] in {"service", "remote"}


@pytest.mark.asyncio
async def test_inference_shell_embed_returns_flat_error_contract() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        response = await client.post("/embed", json={"texts": ["متن آزمایشی"]})
    assert response.status_code == 503
    body = response.json()
    assert set(body.keys()) == {"code", "message", "request_id"}
    assert body["code"] == "embedding_not_implemented"
    assert body["request_id"]
    assert response.headers.get("x-request-id") == body["request_id"]
    assert "detail" not in body


@pytest.mark.asyncio
async def test_inference_shell_rerank_returns_flat_error_contract() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        response = await client.post("/rerank", json={"query": "سؤال", "documents": ["سند"]})
    assert response.status_code == 503
    body = response.json()
    assert set(body.keys()) == {"code", "message", "request_id"}
    assert body["code"] == "reranking_not_implemented"
    assert body["request_id"]
    assert response.headers.get("x-request-id") == body["request_id"]


@pytest.mark.asyncio
async def test_inference_shell_invalid_input_uses_standard_validation_shape() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://inference") as client:
        response = await client.post("/embed", json={"texts": []})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["request_id"]
    assert "issues" in body
