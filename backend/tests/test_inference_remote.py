"""تست واحد backend دورستی inference با respx؛ بدون تماس شبکهٔ واقعی."""

import pytest
import respx
from app.core.config import Settings
from app.inference.main import _select_runtime
from app.inference.remote import RemoteInferenceBackend
from httpx import Response


def _settings(base: str = "https://embed.test/api/v1") -> Settings:
    return Settings(
        app_env="test",
        embedding_backend="remote",
        inference_mode="remote",
        embedding_remote_base_url=base,
        embedding_remote_api_key="sk-test",
        embedding_remote_model="nvidia/llama-nemotron-embed-vl:2b",
        embedding_dim=1024,
    )


def _vectors(k: int = 1) -> list[dict]:
    return [{"embedding": [0.1 * i for i in range(1024)]} for _ in range(k)]


@pytest.mark.asyncio
async def test_remote_embed_success_1024() -> None:
    settings = _settings()
    backend = RemoteInferenceBackend(settings)
    await backend.startup()
    with respx.mock:
        respx.post("https://embed.test/api/v1/embeddings").mock(return_value=Response(200, json={"data": _vectors(2)}))
        out = await backend.embed(["سلام", "دنیا"])
    assert len(out) == 2
    assert len(out[0]) == 1024
    await backend.aclose()


@pytest.mark.asyncio
async def test_remote_embed_dim_mismatch_rejected() -> None:
    settings = _settings()
    backend = RemoteInferenceBackend(settings)
    await backend.startup()
    with respx.mock:
        respx.post("https://embed.test/api/v1/embeddings").mock(
            return_value=Response(200, json={"data": [{"embedding": [0.1] * 256}]})
        )
        with pytest.raises(Exception) as excinfo:
            await backend.embed(["x"])
    assert "embedding_dim_mismatch" in str(excinfo.value)
    await backend.aclose()


@pytest.mark.asyncio
async def test_remote_startup_requires_config() -> None:
    backend = RemoteInferenceBackend(
        Settings(
            app_env="test",
            embedding_backend="remote",
            inference_mode="remote",
            embedding_remote_base_url="",
            embedding_remote_model="",
        )
    )
    with pytest.raises(Exception) as excinfo:
        await backend.startup()
    assert "model_runtime_not_ready" in str(excinfo.value)
    assert backend.ready is False


def test_select_runtime_prefers_remote_when_configured() -> None:
    runtime = _select_runtime(_settings())
    assert isinstance(runtime, RemoteInferenceBackend)
