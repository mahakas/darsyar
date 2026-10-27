"""وابستگی‌های پایهٔ API؛ احراز هویت در فاز ۱ اضافه می‌شود."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

__all__ = ["AsyncSession", "AsyncIterator", "get_db"]
