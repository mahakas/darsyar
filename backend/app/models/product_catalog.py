"""کاتالوگ محصولات مورد اعتماد سرور؛ تغییرات فقط از مسیر operator/CLI با audit (ADR-047)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductCatalog(Base):
    """محصول یک‌باره با قیمت تومانی و مقدار کردیت."""

    __tablename__ = "product_catalog"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    product_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    price_toman: Mapped[int] = mapped_column(Integer, nullable=False)
    credit_grant: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
