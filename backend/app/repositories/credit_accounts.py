"""دسترسی دادهٔ projection اعتبار؛ قفل ردیف برای هر تغییر موجودی (R-126)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_account import CreditAccount


async def get_for_update(session: AsyncSession, user_id: uuid.UUID) -> CreditAccount:
    """سطر حساب را با قفل ردیف می‌خواند؛ شرط مالکیت در query (R-121)."""
    result = await session.execute(
        select(CreditAccount).where(CreditAccount.user_id == user_id).with_for_update()
    )
    return result.scalar_one()


async def exists(session: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await session.execute(select(CreditAccount.id).where(CreditAccount.user_id == user_id))
    return result.first() is not None


async def create(session: AsyncSession, *, user_id: uuid.UUID, available_balance: int = 0) -> CreditAccount:
    account = CreditAccount(user_id=user_id, available_balance=available_balance)
    session.add(account)
    await session.flush()
    return account
