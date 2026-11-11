"""مدل chunk سند (R-150) برای بازنمایی و بازیابی.

Childهای کوچک برای جست‌وجو و parentها برای زمینه به مدل استفاده می‌شوند
(R-158). فیلتر سطح تحصیلی (`chunk.grade_level <= student.selected_grade`)
در همان query و برای هر دو شاخه dense/lexical اعمال می‌شود (R-148).
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

CHUNK_SOURCE_TYPES = ("textbook", "image", "web", "synthetic")


class IngestionChunk(Base):
    __tablename__ = "ingestion_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_ingestion_chunks_doc_index"),
        CheckConstraint("grade_level BETWEEN 1 AND 12", name="ck_ingestion_chunks_grade"),
        CheckConstraint("edition_year > 0", name="ck_ingestion_chunks_edition_year"),
        CheckConstraint("chunk_index >= 0", name="ck_ingestion_chunks_index_nonneg"),
        CheckConstraint("source_type IN ('textbook','image','web','synthetic')", name="ck_ingestion_chunks_source_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_documents.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_chunks.id", ondelete="CASCADE"), nullable=True)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_parent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))

    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_normalized: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)

    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(32), nullable=False)
    edition_year: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="textbook")
    source_origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # ایندکس‌ها جدا از مهاجرت (CONCURRENTLY) ساخته می‌شوند (R-081/082).
