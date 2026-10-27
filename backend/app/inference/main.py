"""پوستهٔ سرویس داخلی inference؛ در فاز صفر هیچ مدل سنگینی دانلود نمی‌شود."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import AppError, install_error_handlers

settings = get_settings()
app = FastAPI(title="Darsyar Inference", version=settings.app_version)
install_error_handlers(app)


class EmbedRequest(BaseModel):
    """درخواست embedding؛ اجرای واقعی در فاز ۳."""
    texts: list[str] = Field(min_length=1, max_length=128)


class RerankRequest(BaseModel):
    """درخواست rerank؛ اجرای واقعی در فاز ۳."""
    query: str = Field(min_length=1, max_length=10000)
    documents: list[str] = Field(min_length=1, max_length=128)


@app.get("/health")
async def health() -> dict[str, str]:
    """liveness سرویس inference را گزارش می‌کند."""
    return {"status": "ok", "mode": settings.inference_mode}


@app.get("/ready")
async def ready() -> dict[str, str]:
    """remote mode برای اسکلت آماده است؛ مدل محلی هنوز در فاز صفر لود نمی‌شود."""
    if settings.inference_mode == "service":
        raise AppError("model_runtime_not_implemented", 503, "اجرای مدل محلی در این فاز پیاده‌سازی نشده است.")
    return {"status": "ready", "mode": "remote"}


@app.post("/embed")
async def embed(_: EmbedRequest) -> None:
    """پیاده‌سازی در فاز ۳؛ در اسکلت نباید خروجی ساختگی تولید شود."""
    raise AppError("embedding_not_implemented", 503, "سرویس embedding در این فاز پیاده‌سازی نشده است.")


@app.post("/rerank")
async def rerank(_: RerankRequest) -> None:
    """پیاده‌سازی در فاز ۳؛ در اسکلت نباید امتیاز ساختگی تولید شود."""
    raise AppError("reranking_not_implemented", 503, "سرویس rerank در این فاز پیاده‌سازی نشده است.")
