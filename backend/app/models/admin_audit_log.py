"""لاگ حسابرسی ادمین؛ append-only (R-122)."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminAuditLog(Base):
    """ثبت عملیات حساس ادمین با کنشگر، قبل/بعد و دلیل."""

    __tablename__ = "admin_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
