"""دسترسی دادهٔ کاربر؛ مالکیت و فیلتر soft delete در query (R-051/R-121)."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_by_phone(session: AsyncSession, phone: str) -> User | None:
    result = await session.execute(select(User).where(User.phone == phone, User.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def list_admins(session: AsyncSession) -> Sequence[User]:
    result = await session.execute(select(User).where(User.role == "admin", User.deleted_at.is_(None)))
    return result.scalars().all()


async def create(session: AsyncSession, *, phone: str, role: str = "user", name: str | None = None, email: str | None = None, password_hash: str | None = None) -> User:
    user = User(phone=phone, role=role, name=name, email=email, password_hash=password_hash)
    session.add(user)
    await session.flush()
    return user
