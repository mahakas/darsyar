import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_live_returns_service_status() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/health/live", headers={"X-Request-ID": "test-request-1"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-request-id"] == "test-request-1"


@pytest.mark.asyncio
async def test_live_generates_request_id_when_missing() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_root_health_and_version_are_available_without_lifespan() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        health_response = await client.get("/health")
        version_response = await client.get("/version")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert version_response.status_code == 200
    assert "version" in version_response.json()
