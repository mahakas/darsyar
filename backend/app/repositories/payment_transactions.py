"""دسترسی دادهٔ تراکنش‌های پرداخت؛ گذارهای شرطی با راستی‌آزمایی rowcount (ADR-047)."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult as _CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_transaction import PaymentTransaction

CursorResult = _CursorResult[object]

STATUS_CREATED = "created"
STATUS_REQUESTING = "requesting"
STATUS_PENDING = "pending"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_UNKNOWN_OUTCOME = "unknown_outcome"


async def get_by_id(session: AsyncSession, payment_id: uuid.UUID) -> PaymentTransaction | None:
    result = await session.execute(select(PaymentTransaction).where(PaymentTransaction.id == payment_id))
    return result.scalar_one_or_none()


async def get_by_id_and_user(session: AsyncSession, payment_id: uuid.UUID, user_id: uuid.UUID) -> PaymentTransaction | None:
    result = await session.execute(
        select(PaymentTransaction).where(PaymentTransaction.id == payment_id, PaymentTransaction.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_by_idempotency_key(
    session: AsyncSession, user_id: uuid.UUID, key: str
) -> PaymentTransaction | None:
    result = await session.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.user_id == user_id,
            PaymentTransaction.idempotency_key == key,
        )
    )
    return result.scalar_one_or_none()


async def get_by_authority(session: AsyncSession, authority: str) -> PaymentTransaction | None:
    result = await session.execute(select(PaymentTransaction).where(PaymentTransaction.authority == authority))
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    product_id: str,
    amount_toman: int,
    credit_grant: int,
    provider: str,
    provider_currency: str,
    provider_amount: int,
    idempotency_key: str,
    request_fingerprint: str,
    request_id: str | None = None,
) -> PaymentTransaction:
    payment = PaymentTransaction(
        user_id=user_id,
        product_id=product_id,
        amount_toman=amount_toman,
        credit_grant=credit_grant,
        provider=provider,
        provider_currency=provider_currency,
        provider_amount=provider_amount,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        request_id=request_id,
        status=STATUS_CREATED,
    )
    session.add(payment)
    await session.flush()
    return payment


async def try_claim_request(session: AsyncSession, payment_id: uuid.UUID) -> bool:
    """ادعای اتمیک created→requesting؛ دقیقاً یک هندلر برنده می‌شود."""
    result = await session.execute(
        update(PaymentTransaction)
        .where(PaymentTransaction.id == payment_id, PaymentTransaction.status == STATUS_CREATED)
        .values(status=STATUS_REQUESTING)
    )
    return cast(CursorResult, result).rowcount == 1


async def try_persist_authority(
    session: AsyncSession,
    payment_id: uuid.UUID,
    authority: str,
) -> bool:
    """ثبت authority و گذار requesting→pending."""
    result = await session.execute(
        update(PaymentTransaction)
        .where(PaymentTransaction.id == payment_id, PaymentTransaction.status == STATUS_REQUESTING)
        .values(status=STATUS_PENDING, authority=authority)
    )
    return cast(CursorResult, result).rowcount == 1


async def try_mark_failed(
    session: AsyncSession,
    payment_id: uuid.UUID,
    *,
    failure_code: str,
    failure_reason: str,
) -> bool:
    """شکست قطعی از requesting یا pending (شواهد معتبر provider)."""
    result = await session.execute(
        update(PaymentTransaction)
        .where(
            PaymentTransaction.id == payment_id,
            PaymentTransaction.status.in_([STATUS_REQUESTING, STATUS_PENDING]),
        )
        .values(status=STATUS_FAILED, failure_code=failure_code, failure_reason=failure_reason)
    )
    return cast(CursorResult, result).rowcount == 1


async def try_mark_unknown_outcome(session: AsyncSession, payment_id: uuid.UUID) -> bool:
    result = await session.execute(
        update(PaymentTransaction)
        .where(PaymentTransaction.id == payment_id, PaymentTransaction.status == STATUS_REQUESTING)
        .values(status=STATUS_UNKNOWN_OUTCOME)
    )
    return cast(CursorResult, result).rowcount == 1


async def try_finalize_succeeded(
    session: AsyncSession,
    payment_id: uuid.UUID,
    ref_id: str,
    now: datetime,
) -> bool:
    """گذاری شرطی pending→succeeded؛ سپس ledger/balance در همان تراکنش (سرویس)."""
    result = await session.execute(
        update(PaymentTransaction)
        .where(PaymentTransaction.id == payment_id, PaymentTransaction.status == STATUS_PENDING)
        .values(status=STATUS_SUCCEEDED, ref_id=ref_id, succeeded_at=now)
    )
    return cast(CursorResult, result).rowcount == 1


async def list_stale_requesting(
    session: AsyncSession,
    older_than: datetime,
    limit: int,
    user_id: uuid.UUID | None = None,
) -> Sequence[PaymentTransaction]:
    statement = select(PaymentTransaction).where(
        PaymentTransaction.status == STATUS_REQUESTING, PaymentTransaction.created_at < older_than
    )
    if user_id is not None:
        statement = statement.where(PaymentTransaction.user_id == user_id)
    statement = statement.order_by(PaymentTransaction.created_at.asc()).limit(limit)
    result = await session.execute(statement)
    return result.scalars().all()
