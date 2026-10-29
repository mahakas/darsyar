"""دسترسی دادهٔ کاتالوگ محصولات؛ تغییرات فقط از مسیر operator/CLI با audit."""

import uuid

from sqlalchemy import select
from sqlalchemy.engine import CursorResult as _CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_catalog import ProductCatalog

CursorResult = _CursorResult[object]

SUPPORTED_PRODUCT_IDS = ("basic", "pro")


async def get_active(session: AsyncSession, product_id: str) -> ProductCatalog | None:
    result = await session.execute(
        select(ProductCatalog).where(ProductCatalog.product_id == product_id, ProductCatalog.active.is_(True))
    )
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, product_id: str) -> ProductCatalog | None:
    result = await session.execute(select(ProductCatalog).where(ProductCatalog.product_id == product_id))
    return result.scalar_one_or_none()


async def update_price_and_grant(
    session: AsyncSession,
    product_id: str,
    *,
    price_toman: int,
    credit_grant: int,
    actor_user_id: uuid.UUID | None,
    reason: str,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """به‌روزرسانی کاتالوگ و بازگرداندن before/after برای رویداد audit (در همان تراکنش)."""
    product = await get_by_id(session, product_id)
    if product is None:
        return None, None
    before: dict[str, object] = {"price_toman": product.price_toman, "credit_grant": product.credit_grant, "active": product.active}
    product.price_toman = price_toman
    product.credit_grant = credit_grant
    await session.flush()
    after: dict[str, object] = {"price_toman": product.price_toman, "credit_grant": product.credit_grant, "active": product.active}
    return before, after
