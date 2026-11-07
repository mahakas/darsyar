"""تخصیص grant→رزرو (ADR-053)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReservationAllocation(Base):
    __tablename__ = "reservation_credit_allocations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    reservation_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    grant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    allocated_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed_amount: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    released_amount: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    voided_amount: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
