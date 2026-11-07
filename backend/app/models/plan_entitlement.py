"""هویت دورهٔ فعال پلن (ADR-052)."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    product_id: Mapped[str] = mapped_column(String(32), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'active'"))
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granted_credits: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    remaining_credits: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
