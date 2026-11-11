FROM python:3.13-slim AS runtime-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    HF_HOME=/models/huggingface
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-fas fonts-noto-core libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /usr/local/bin/
COPY pyproject.toml README.md ./
# Lockfiles are generated and validated in phase 0; builds must never silently resolve floating versions.
COPY uv.lock ./uv.lock
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
ENV PATH="/opt/venv/bin:$PATH"

FROM runtime-base AS api
EXPOSE 8000
# Early Draining + timeout_graceful_shutdown محدود (۴۵s): draining از لحظه SIGTERM فعال
# می‌شود؛ Uvicorn پس از مهلت، تسک‌های باقی‌مانده را لغو می‌کند و lifespan/drain سپس cleanup
# مالی (settle/release) را کامل می‌کند.
CMD ["python", "-m", "app.core.run_server"]

FROM runtime-base AS worker
# PDF parsing and YAML manifests are lightweight ingestion runtime dependencies.
RUN uv sync --frozen --no-dev --no-install-project --extra ingestion
CMD ["arq", "app.services.worker.WorkerSettings"]

FROM runtime-base AS inference
# Slice E: همان image مشترک (R-036) + extra مدل (torch/FlagEmbedding/سentence-transformers).
RUN uv sync --frozen --no-dev --no-install-project --extra rag
EXPOSE 8100
CMD ["uvicorn", "app.inference.main:app", "--host", "0.0.0.0", "--port", "8100"]

FROM runtime-base AS migrate
CMD ["alembic", "upgrade", "head"]
