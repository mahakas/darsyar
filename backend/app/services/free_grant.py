"""گرانت رایگان یک‌بار هنگام ساخت کاربر واقعی (ADR-048/R-135).

تمام عملیات (ساخت کاربر، ساخت/قفل حساب، درج ledger، به‌روزرسانی projection)
در **یک تراکنش** انجام می‌شود؛ این ماژول commit نمی‌کند.
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user import User
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import users as users_repo

FREE_GRANT_KIND = "free_grant"


async def create_user_with_free_grant(
    session: AsyncSession,
    *,
    phone: str,
    role: str = "user",
    name: str | None = None,
    email: str | None = None,
    password_hash: str | None = None,
) -> User:
    """ساخت کاربر + حساب + گرانت ۵ در همان تراکنش (بدون commit داخلی)."""
    settings = get_settings()
    user = await users_repo.create(session, phone=phone, role=role, name=name, email=email, password_hash=password_hash)
    account = await accounts_repo.create(session, user_id=user.id, available_balance=0)
    await ledger_repo.create(
        session,
        user_id=user.id,
        kind=FREE_GRANT_KIND,
        amount=settings.free_plan_credits,
        idempotency_key=f"free-grant:{user.id}:once",
        request_id=None,
        reason="one-time free registration grant",
    )
    account.available_balance += settings.free_plan_credits
    await session.flush()
    return user


async def grant_if_new(user_id: uuid.UUID, session: AsyncSession) -> None:
    """حل‌کنندهٔ ساده برای مسیرهای پشتیبان: فقط در صورت نبود گرانت اقدام می‌کند."""
    existing = await ledger_repo.find_by_kind(session, user_id, FREE_GRANT_KIND)
    if existing is not None:
        return
    settings = get_settings()
    account = await accounts_repo.get_for_update(session, user_id)
    try:
        await ledger_repo.create(
            session,
            user_id=user_id,
            kind=FREE_GRANT_KIND,
            amount=settings.free_plan_credits,
            idempotency_key=f"free-grant:{user_id}:once",
            request_id=None,
            reason="one-time free registration grant",
        )
    except IntegrityError:
        await session.rollback()
        return
    account.available_balance += settings.free_plan_credits
    await session.flush()
