"""دسترسی دادهٔ توکن‌های refresh و زنجیره‌ها."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult as _CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken

CursorResult = _CursorResult[object]


async def get_by_hash(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    return result.scalar_one_or_none()


async def try_mark_revoked(
    session: AsyncSession,
    token_id: uuid.UUID,
    now: datetime,
    replaced_by_jti: str,
) -> bool:
    """ابطال اتمیک با compare-and-swap؛ فقط اگر هنوز باطل نشده باشد موفق است."""
    result = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == token_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now, replaced_by_jti=replaced_by_jti)
    )
    return cast(CursorResult, result).rowcount == 1


async def get_active_by_family(session: AsyncSession, family_id: uuid.UUID) -> RefreshToken | None:
    result = await session.execute(
        select(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .order_by(RefreshToken.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_all_by_family(session: AsyncSession, family_id: uuid.UUID) -> Sequence[RefreshToken]:
    result = await session.execute(select(RefreshToken).where(RefreshToken.family_id == family_id))
    return result.scalars().all()


async def create(session: AsyncSession, *, user_id: uuid.UUID, jti: str, token_hash: str, family_id: uuid.UUID, expires_at: object) -> RefreshToken:
    token = RefreshToken(user_id=user_id, jti=jti, token_hash=token_hash, family_id=family_id, expires_at=expires_at)
    session.add(token)
    await session.flush()
    return token


async def revoke_family(session: AsyncSession, family_id: uuid.UUID, now: datetime, replaced_by_jti: str | None = None) -> None:
    """همهٔ رکوردهای فعال خانواده را باطل می‌کند."""
    tokens = await get_all_by_family(session, family_id)
    for token in tokens:
        if token.revoked_at is None:
            token.revoked_at = now
            if replaced_by_jti is not None:
                token.replaced_by_jti = replaced_by_jti
