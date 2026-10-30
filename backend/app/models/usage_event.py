"""رویداد مصرف اعتبار؛ append-only و مبنای بازسازی fair-use (R-139)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsageEvent(Base):
    """یک رویداد منطقی مصرف؛ فقط درج؛ تخمینی هرگز واقعی معرفی نمی‌شود."""

    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
