"""به‌روزرسانی کاتالوگ محصولات فقط از مسیر operator/CLI با audit (ADR-047).

استفاده: `uv run --locked python -m app.scripts.upsert_product --product basic --price 550000 --grant 500 --actor <uuid> --reason "..."`
"""

import asyncio
import sys
import uuid
from argparse import ArgumentParser

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import SessionFactory
from app.repositories import admin_audit_log as audit_repo
from app.repositories import product_catalog as catalog_repo
from app.repositories import users as users_repo


async def upsert_product(
    session: AsyncSession,
    *,
    product_id: str,
    price_toman: int,
    credit_grant: int,
    actor_user_id: uuid.UUID,
    reason: str,
) -> None:
    if product_id not in catalog_repo.SUPPORTED_PRODUCT_IDS:
        raise AppError("unsupported_product", 422, "شناسهٔ محصول پشتیبانی نمی‌شود.")
    if price_toman <= 0 or credit_grant <= 0:
        raise AppError("invalid_catalog_values", 422, "قیمت و کردیت باید مثبت باشند.")
    if not reason.strip():
        raise AppError("reason_required", 422, "دلیل تغییر الزامی است.")

    actor = await users_repo.get_by_id(session, actor_user_id)
    if actor is None or actor.role != "admin":
        raise AppError("actor_required", 403, "تغییر کاتالوگ فقط برای ادمین مجاز است.")

    before, after = await catalog_repo.update_price_and_grant(
        session,
        product_id,
        price_toman=price_toman,
        credit_grant=credit_grant,
        actor_user_id=actor_user_id,
        reason=reason,
    )
    if before is None or after is None:
        raise AppError("unknown_product", 404, "محصول یافت نشد.")
    await audit_repo.create(
        session,
        actor_user_id=actor_user_id,
        action="catalog_price_change",
        entity_type="product_catalog",
        entity_id=product_id,
        before=before,
        after=after,
        reason=reason,
    )
    await session.commit()


def main() -> int:
    parser = ArgumentParser(description="Update B catalog with audit")
    parser.add_argument("--product", required=True)
    parser.add_argument("--price", required=True, type=int)
    parser.add_argument("--grant", required=True, type=int)
    parser.add_argument("--actor", required=True, help="admin user UUID")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    try:
        actor_id = uuid.UUID(args.actor)
    except ValueError:
        print("invalid actor uuid", file=sys.stderr)
        return 2
    asyncio.run(
        upsert_product(
            SessionFactory(),
            product_id=args.product,
            price_toman=args.price,
            credit_grant=args.grant,
            actor_user_id=actor_id,
            reason=args.reason,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
