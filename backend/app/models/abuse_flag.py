"""پرچم سوءاستفادهٔ Fair-Use؛ جدا از هشدارهای تطبیق مالی (ADR-050)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AbuseFlag(Base):
    """یک پرچم به ازای هر (کاربر، دورهٔ YYYY-MM)؛ تاریخچهٔ حل حفظ می‌شود."""

    __tablename__ = "abuse_flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    period_key: Mapped[str] = mapped_column(String(7), nullable=False)
    observed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
