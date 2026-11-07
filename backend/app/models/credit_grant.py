"""سبد اعتبار قابل‌انتساب به پلن/خرید (ADR-052)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CreditGrant(Base):
    __tablename__ = "credit_grants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    original_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_amount: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
