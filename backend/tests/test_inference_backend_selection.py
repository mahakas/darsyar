"""تست‌های ماتریس انتخاب backend (ADR-054): جدا بودن انتخاب از INFERENCE_MODE."""

import pytest
from app.core.config import Settings
from app.inference.main import _select_runtime
from app.inference.remote import RemoteInferenceBackend
from app.inference.runtime import InferenceRuntime
from pydantic import ValidationError


def _settings(inference_mode: str = "service", embedding_backend: str = "service") -> Settings:
    return Settings(
        app_env="test",
        inference_mode=inference_mode,  # type: ignore[arg-type]
        embedding_backend=embedding_backend,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_service_remote_selects_remote() -> None:
    runtime = _select_runtime(_settings(inference_mode="service", embedding_backend="remote"))
    assert isinstance(runtime, RemoteInferenceBackend)


@pytest.mark.asyncio
async def test_service_service_selects_local() -> None:
    runtime = _select_runtime(_settings(inference_mode="service", embedding_backend="service"))
    assert isinstance(runtime, InferenceRuntime)


@pytest.mark.asyncio
async def test_legacy_remote_with_remote_backend_selects_remote() -> None:
    runtime = _select_runtime(_settings(inference_mode="remote", embedding_backend="remote"))
    assert isinstance(runtime, RemoteInferenceBackend)


@pytest.mark.asyncio
async def test_legacy_remote_does_not_override_local_backend() -> None:
    # INFERENCE_MODE=remote نباید به‌تنهایی backend را انتخاب کند (ADR-054).
    runtime = _select_runtime(_settings(inference_mode="remote", embedding_backend="service"))
    assert isinstance(runtime, InferenceRuntime)


@pytest.mark.asyncio
async def test_invalid_embedding_backend_raises_configuration_error() -> None:
    with pytest.raises(ValidationError):
        _settings(embedding_backend="bogus")


@pytest.mark.asyncio
async def test_remote_with_incomplete_config_not_ready() -> None:
    settings = Settings(
        app_env="test",
        inference_mode="service",
        embedding_backend="remote",
        embedding_remote_base_url="",
        embedding_remote_model="",
        embedding_remote_api_key=None,
    )
    runtime = RemoteInferenceBackend(settings)
    with pytest.raises(Exception) as excinfo:
        await runtime.startup()
    assert "model_runtime_not_ready" in str(excinfo.value)
    assert runtime.ready is False
