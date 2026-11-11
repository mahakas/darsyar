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


@pytest.mark.asyncio
async def test_remote_rerank_uses_its_own_endpoint_and_key() -> None:
    settings = Settings(
        app_env="test",
        embedding_backend="remote",
        inference_mode="remote",
        embedding_remote_base_url="https://embed.test/v1",
        embedding_remote_api_key="sk-embed",
        embedding_remote_model="embed-model",
        rerank_remote_base_url="https://rerank.test/v2",
        rerank_remote_api_key="sk-rerank",
        rerank_remote_model="rerank-model",
        embedding_dim=1024,
    )
    backend = RemoteInferenceBackend(settings)
    await backend.startup()

    with respx.mock(assert_all_called=True) as router:
        route = router.post("https://rerank.test/v2/rerank").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {"index": 1, "relevance_score": 0.25},
                        {"index": 0, "relevance_score": 0.9},
                    ]
                },
            )
        )
        scores = await backend.rerank([("پرسش", "سند اول"), ("پرسش", "سند دوم")])

    assert route.called
    assert route.calls[0].request.headers["Authorization"] == "Bearer sk-rerank"
    assert scores == [0.9, 0.25]
    await backend.aclose()


@pytest.mark.asyncio
async def test_remote_rerank_rejects_missing_or_duplicate_indexes() -> None:
    settings = Settings(
        app_env="test",
        embedding_backend="remote",
        inference_mode="remote",
        embedding_remote_base_url="https://embed.test/v1",
        embedding_remote_api_key="sk-embed",
        embedding_remote_model="embed-model",
        rerank_remote_base_url="https://rerank.test/v2",
        rerank_remote_model="rerank-model",
        embedding_dim=1024,
    )
    backend = RemoteInferenceBackend(settings)
    await backend.startup()
    with respx.mock:
        respx.post("https://rerank.test/v2/rerank").mock(
            return_value=Response(
                200,
                json={"results": [{"index": 0, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]},
            )
        )
        with pytest.raises(Exception) as excinfo:
            await backend.rerank([("پرسش", "سند اول"), ("پرسش", "سند دوم")])
    assert "inference_remote_malformed" in str(excinfo.value)
    await backend.aclose()
