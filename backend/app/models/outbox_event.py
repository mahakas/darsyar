"""مدل transactional outbox برای ارسال مطمئن job به ARQ (فقط persistence؛ بدون publisher)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
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

OUTBOX_STATES = ("pending", "publishing", "published", "failed")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_outbox_events_dedup"),
        CheckConstraint("publication_state IN ('pending','publishing','published','failed')", name="ck_outbox_events_state_valid"),
        CheckConstraint("attempt_count >= 0", name="ck_outbox_events_attempt_nonneg"),
        Index("ix_outbox_events_claim", "publication_state", "available_at"),
        Index("ix_outbox_events_job", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    publication_state: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
