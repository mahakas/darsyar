"""چالش OTP؛ فقط digest با pepper ذخیره می‌شود، هرگز متن کد (R-100)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OtpChallenge(Base):
    """چالش یک‌بارمصرف با تلاش شمارش‌شده و انقضا."""

    __tablename__ = "otp_challenges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    phone: Mapped[str] = mapped_column(String(16), nullable=False)
    code_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    pepper_id: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
