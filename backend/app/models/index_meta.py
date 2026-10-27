"""رجیستری ایندکس امبدینگ فعال (R-087): منبع حقیقت سازگاری ایندکس‌ها.

هیچ ingestion یا کوئری بدون خواندن رکورد فعال این جدول اجرا نمی‌شود.
فقط یک رکورد می‌تواند در هر لحظه `is_active` باشد (ایندکس یکتای جزئی).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndexMeta(Base):
    """فرادادهٔ ایندکس امبدینگ فعال برای dense retrieval."""

    __tablename__ = "index_meta"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("false"))
