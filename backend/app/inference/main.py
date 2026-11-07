"""خدمت Inference عملیاتی (Slice E؛ ADR-036).

بارگذاری مدل‌ها فقط در همین فرایند؛ API process هرگز مدل را import/initialize نمی‌کند.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.errors import AppError, install_error_handlers
from app.inference.remote import RemoteInferenceBackend
from app.inference.runtime import InferenceRuntime

logger = logging.getLogger(__name__)


def _select_runtime(settings: Settings) -> InferenceRuntime | RemoteInferenceBackend:
    """انتخاب backend فقط بر اساس EMBEDDING_BACKEND (ADR-054).

    INFERENCE_MODE نحوهٔ اجرای سرویس را تعیین می‌کند، نه backend مدل را.
    مقدار legacy `INFERENCE_MODE=remote` دیگر به‌تنهایی backend را انتخاب نمی‌کند و
    صرفاً با هشدار پشتیبانی می‌شود؛ مقدار canonical `INFERENCE_MODE=service` است.
    """
    if settings.inference_mode == "remote":
        logger.warning(
            "inference_mode_remote_deprecated: INFERENCE_MODE=remote دیگر backend را انتخاب نمی‌کند؛ "
            "مقدار canonical INFERENCE_MODE=service است و انتخاب از EMBEDDING_BACKEND صورت می‌گیرد."
        )
    if settings.embedding_backend == "remote":
        return RemoteInferenceBackend(settings)
    return InferenceRuntime(settings)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=128)


class RerankRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8192)
    documents: list[str] = Field(min_length=1, max_length=128)


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]


class RerankResponse(BaseModel):
    scores: list[float]


def create_app(settings: Settings | None = None, runtime: InferenceRuntime | RemoteInferenceBackend | None = None) -> FastAPI:
    settings = settings or get_settings()
    runtime = runtime or _select_runtime(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if not runtime.started and runtime.load_error is None:
            try:
                await runtime.startup()
            except AppError:
                pass
        try:
            yield
        finally:
            if isinstance(runtime, RemoteInferenceBackend):
                await runtime.aclose()

    app = FastAPI(title="Darsyar Inference", version=settings.app_version, lifespan=lifespan)
    install_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.inference_mode}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        if not runtime.ready:
            raise AppError("model_runtime_not_ready", 503, "مدل‌های inference آماده نیستند.")
        return {"status": "ready", "mode": settings.inference_mode}

    @app.post("/embed", response_model=EmbedResponse)
    async def embed(payload: EmbedRequest) -> EmbedResponse:
        for t in payload.texts:
            if len(t) > settings.inference_max_sequence_length:
                raise AppError("input_too_long", 422, "طول ورودی از سقف مجاز بیشتر است.")
        embeddings = await runtime.embed(payload.texts)
        return EmbedResponse(embeddings=embeddings)

    @app.post("/rerank", response_model=RerankResponse)
    async def rerank(payload: RerankRequest) -> RerankResponse:
        for d in payload.documents:
            if len(d) > settings.inference_max_sequence_length:
                raise AppError("input_too_long", 422, "طول سند از سقف مجاز بیشتر است.")
        pairs = [(payload.query, d) for d in payload.documents]
        scores = await runtime.rerank(pairs)
        return RerankResponse(scores=scores)

    return app


app = create_app()
