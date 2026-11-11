"""مدل durable ingestion job — فقط persistence؛ بدون claim/lease/heartbeat runtime.

حالت job اجرایی است و با چرخهٔ عمر منبع (R-156) مستقل است.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JOB_STATUSES = ("queued", "running", "retry_waiting", "succeeded", "terminal_failure", "cancellation_requested", "cancelled")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        UniqueConstraint("document_id", "request_idempotency_key", name="uq_ingestion_jobs_request_idempotency"),
        CheckConstraint("status IN ('queued','running','retry_waiting','succeeded','terminal_failure','cancellation_requested','cancelled')", name="ck_ingestion_jobs_status_valid"),
        CheckConstraint("attempt_count >= 0", name="ck_ingestion_jobs_attempt_nonneg"),
        CheckConstraint("fencing_token >= 0", name="ck_ingestion_jobs_fencing_nonneg"),
        Index("ix_ingestion_jobs_claim", "status", "retry_available_at"),
        Index("ix_ingestion_jobs_lease_expiry", "lease_expires_at"),
        Index("ix_ingestion_jobs_document", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'queued'"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_documents.id", ondelete="RESTRICT"), nullable=False)
    request_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    retry_available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
