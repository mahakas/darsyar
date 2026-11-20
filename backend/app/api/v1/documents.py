"""Administrative ingestion intake/status routes.

Intake is deliberately narrow: it can only queue a ``synthetic`` job for a
document identity that already exists. Real PDF processing stays blocked until
source authorization and Gate A/B/C evidence are approved separately.
"""

import hashlib
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.services.ingestion_creation import create_ingestion_job

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: uuid.UUID
    idempotency_key: str = Field(min_length=8, max_length=128)
    job_type: str = Field(default="synthetic", pattern="^synthetic$")


class DocumentJobOut(BaseModel):
    job_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    created: bool


@router.post("/jobs", response_model=DocumentJobOut, status_code=202)
async def create_document_job(
    payload: DocumentJobRequest,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentJobOut:
    """Create one idempotent synthetic job plus its initial outbox event."""
    request_hash = hashlib.sha256(
        json.dumps(
            {
                "document_id": str(payload.document_id),
                "idempotency_key": payload.idempotency_key,
                "job_type": payload.job_type,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    result = await create_ingestion_job(
        session,
        document_id=payload.document_id,
        request_idempotency_key=payload.idempotency_key,
        request_hash=request_hash,
        job_type=payload.job_type,
    )
    await session.flush()
    return DocumentJobOut(
        job_id=result.job.id,
        document_id=result.job.document_id,
        status=result.job.status,
        created=result.created,
    )


@router.get("/jobs/{job_id}", response_model=DocumentJobOut)
async def get_document_job(
    job_id: uuid.UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentJobOut:
    """Read the durable state of an ingestion job; admin only."""
    from app.models.ingestion_job import IngestionJob

    job = await session.get(IngestionJob, job_id)
    if job is None:
        raise AppError("ingestion_job_not_found", 404, "ingestion job یافت نشد.")
    return DocumentJobOut(
        job_id=job.id,
        document_id=job.document_id,
        status=job.status,
        created=True,
    )
