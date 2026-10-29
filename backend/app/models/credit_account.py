"""projection ماندهٔ قابل‌مصرف اعتبار؛ فقط در تراکنش با ledger تغییر می‌کند (R-126/ADR-035)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CreditAccount(Base):
    """ماندهٔ تراکنشی؛ available_balance رزروهای pending را شامل نمی‌شود."""

    __tablename__ = "credit_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, unique=True)
    available_balance: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
