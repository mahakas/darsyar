"""مسیرهای پرداخت یک‌باره (ADR-047): checkout، callback و وضعیت."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.repositories import entitlements as ent_repo
from app.repositories import payment_transactions as payments_repo
from app.repositories import product_catalog as catalog_repo
from app.schemas.billing import (
    CancellationRequestIn,
    CancellationRequestOut,
    CheckoutRequest,
    CheckoutResponse,
    EntitlementOut,
    PaymentStatusOut,
    PlanInfoOut,
    PrePurchaseInfoOut,
)
from app.services.payment import PaymentService
from app.services.payment_provider import ZarinPalProvider
from app.services.plans import PlanService

router = APIRouter(prefix="/billing", tags=["billing"])

SUCCESS_PAGE = "<html><body><h1>پرداخت موفق</h1></body></html>"
FAILURE_PAGE = "<html><body><h1>پرداخت ناموفق</h1></body></html>"
PENDING_PAGE = "<html><body><h1>وضعیت پرداخت نامعلوم است</h1></body></html>"
NOT_FOUND_PAGE = "<html><body><h1>پرداخت یافت نشد</h1></body></html>"


def _payment_service(session: Annotated[AsyncSession, Depends(get_db)]) -> PaymentService:
    return PaymentService(session, ZarinPalProvider())


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PaymentService, Depends(_payment_service)],
    request: Request,
) -> CheckoutResponse:
    result = await service.checkout(
        user.id,
        payload.product_id,
        idempotency_key=payload.idempotency_key,
        request_id=request.headers.get("x-request-id"),
    )
    body = CheckoutResponse(
        payment_id=result.payment_id,
        status=result.status,
        redirect_url=result.redirect_url,
        amount_toman=result.amount_toman,
    )
    response.status_code = 201 if result.redirect_url else 202
    return body


@router.get("/callback")
async def callback(request: Request) -> Response:
    authority = request.query_params.get("Authority", "")
    if not authority:
        return Response(content=NOT_FOUND_PAGE, media_type="text/html")
    from app.db.session import SessionFactory

    async with SessionFactory() as session:
        svc = PaymentService(session, ZarinPalProvider())
        outcome = await svc.verify_and_finalize(authority, request.headers.get("x-request-id"))
    if outcome == "succeeded":
        return Response(content=SUCCESS_PAGE, media_type="text/html")
    if outcome == "failed":
        return Response(content=FAILURE_PAGE, media_type="text/html")
    if outcome == "not_found":
        return Response(content=NOT_FOUND_PAGE, media_type="text/html")
    return Response(content=PENDING_PAGE, media_type="text/html")


@router.get("/payments/{payment_id}", response_model=PaymentStatusOut)
async def payment_status(
    payment_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentStatusOut:
    payment = await payments_repo.get_by_id_and_user(session, payment_id, user.id)
    if payment is None:
        raise AppError("payment_not_found", 404, "پرداخت یافت نشد.")
    return PaymentStatusOut(
        payment_id=payment.id,
        status=payment.status,
        amount_toman=payment.amount_toman,
        ref_id=payment.ref_id,
    )


@router.get("/plans", response_model=list[PlanInfoOut])
async def list_plans(session: Annotated[AsyncSession, Depends(get_db)]) -> list[PlanInfoOut]:
    from sqlalchemy import select

    from app.models.product_catalog import ProductCatalog

    rows = (await session.execute(select(ProductCatalog).where(ProductCatalog.active.is_(True)).order_by(ProductCatalog.product_id))).scalars().all()
    return [
        PlanInfoOut(
            product_id=r.product_id,
            price_toman=r.price_toman,
            credit_grant=r.credit_grant,
            plan_type=r.plan_type,
            duration_days=r.duration_days,
            active=r.active,
        )
        for r in rows
    ]


@router.get("/entitlements", response_model=list[EntitlementOut])
async def list_entitlements(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[EntitlementOut]:
    from sqlalchemy import select

    from app.models.plan_entitlement import PlanEntitlement

    rows = (
        await session.execute(select(PlanEntitlement).where(PlanEntitlement.user_id == user.id).order_by(PlanEntitlement.created_at.desc()))
    ).scalars().all()
    return [EntitlementOut.model_validate(r) for r in rows]


@router.get("/pre-purchase-info", response_model=PrePurchaseInfoOut)
async def pre_purchase_info(
    product_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PrePurchaseInfoOut:
    product = await catalog_repo.get_active(session, product_id)
    if product is None:
        raise AppError("unknown_product", 404, "محصول موردنظر موجود نیست.")
    entitlement = await ent_repo.get_active_entitlement(session, user.id, product_id)
    remaining = 0
    if entitlement is not None:
        remaining = entitlement.remaining_credits
    msg = f"پلن «{product_id}» پس از تأیید پرداخت فعال می‌شود."
    if entitlement is not None:
        msg = (
            f"پلن «{product_id}» فعال است؛ اعتبار باقی‌مانده: {remaining}؛ "
            f"انقضای فعلی: {entitlement.expires_at.isoformat()}. خرید جدید پس از فعال‌سازی اثر می‌کند."
        )
    return PrePurchaseInfoOut(
        product_id=product_id,
        current_entitlement=EntitlementOut.model_validate(entitlement) if entitlement else None,
        remaining_credits=remaining,
        message=msg,
    )


@router.post("/cancellation-requests", response_model=CancellationRequestOut)
async def request_cancellation(
    payload: CancellationRequestIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CancellationRequestOut:
    service = PlanService(session)
    await service.request_cancellation(user.id, payload.entitlement_id)
    from sqlalchemy import select

    from app.models.cancellation_request import CancellationRequest

    row = (
        await session.execute(
            select(CancellationRequest).where(
                CancellationRequest.user_id == user.id, CancellationRequest.entitlement_id == payload.entitlement_id
            ).order_by(CancellationRequest.created_at.desc()).limit(1)
        )
    ).scalar_one()
    await session.commit()
    return CancellationRequestOut(id=row.id, entitlement_id=row.entitlement_id, status=row.status, requested_at=row.requested_at)


@router.post("/cancellation-requests/{request_id}/withdraw")
async def withdraw_cancellation(
    request_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    service = PlanService(session)
    await service.withdraw_cancellation(user.id, request_id)
    await session.commit()
    return {"status": "withdrawn"}
