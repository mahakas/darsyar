"""شمارندهٔ ریت‌لیمیت fallback مبتنی بر PostgreSQL (OQ-006).

این جدول فقط برای پذیرش/محدودیت نرخ درخواست هنگام ازکارافتادن Redis استفاده می‌شود
و به‌هیچ‌وجه منبع حقیقت مالی نیست (R-124). کاملاً از ledger مالی جدا است.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
