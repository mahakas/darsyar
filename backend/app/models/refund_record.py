"""رکورد بازپرداخت؛ مستقل از لغو؛ هرگز وضعیت موفق بدون تأیید اجرای provider."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefundRecord(Base):
    __tablename__ = "refund_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    payment_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    requested_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    approved_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credit_voided: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'requested'"))
    provider_settlement_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
