"""کلاس پایهٔ مدل‌های SQLAlchemy."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """پایهٔ مشترک مدل‌های پایگاه داده."""
