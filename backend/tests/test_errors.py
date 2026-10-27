import pytest
from app.core.errors import AppError, install_error_handlers
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def create_test_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/known-error")
    async def known_error() -> None:
        raise AppError("test_error", 409, "خطای آزمایشی")

    @app.get("/unexpected-error")
    async def unexpected_error() -> None:
        raise RuntimeError("sensitive internal detail")

    return app


@pytest.mark.asyncio
async def test_app_error_returns_flat_contract_and_request_id() -> None:
    app = create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/known-error")
    assert response.status_code == 409
    assert response.headers.get("x-request-id")
    assert response.json()["message"] == "خطای آزمایشی"
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "error" not in response.json()


@pytest.mark.asyncio
async def test_unexpected_error_does_not_leak_exception_message() -> None:
    app = create_test_app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/unexpected-error")
    assert response.status_code == 500
    assert response.headers.get("x-request-id")
    assert "sensitive internal detail" not in response.text
