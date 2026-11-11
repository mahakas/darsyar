"""مدل هویت canonical سند (R-157) — فقط هویت/منبع؛ بدون شواهد مجوز.

هویت یکتای canonical: (checksum, edition_year, subject, grade_level).
Provenance و authorization به‌صورت جدا حفظ می‌شوند؛ وجود رکورد هویت به‌معنای
مجازبودن نیست (ADR-024).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestionDocument(Base):
    __tablename__ = "ingestion_documents"
    __table_args__ = (
        UniqueConstraint("checksum", "edition_year", "subject", "grade_level", name="uq_ingestion_documents_canonical"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    edition_year: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(32), nullable=False)
    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
