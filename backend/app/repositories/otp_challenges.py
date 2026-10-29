"""دسترسی دادهٔ چالش‌های OTP."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.otp_challenge import OtpChallenge


async def get_latest_active(session: AsyncSession, phone: str, now: datetime) -> OtpChallenge | None:
    """آخرین چالش مصرف‌نشده و منقضی‌نشده را برمی‌گرداند."""
    result = await session.execute(
        select(OtpChallenge)
        .where(
            OtpChallenge.phone == phone,
            OtpChallenge.consumed_at.is_(None),
            OtpChallenge.expires_at > now,
        )
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, challenge_id: uuid.UUID) -> OtpChallenge | None:
    result = await session.execute(select(OtpChallenge).where(OtpChallenge.id == challenge_id))
    return result.scalar_one_or_none()


async def create(session: AsyncSession, *, phone: str, code_digest: str, pepper_id: str, expires_at: datetime) -> OtpChallenge:
    challenge = OtpChallenge(phone=phone, code_digest=code_digest, pepper_id=pepper_id, expires_at=expires_at)
    session.add(challenge)
    await session.flush()
    return challenge
