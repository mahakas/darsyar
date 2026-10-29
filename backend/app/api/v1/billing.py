"""مسیرهای پرداخت یک‌باره (ADR-047): checkout، callback و وضعیت."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.repositories import payment_transactions as payments_repo
from app.schemas.billing import CheckoutRequest, CheckoutResponse, PaymentStatusOut
from app.services.payment import PaymentService
from app.services.payment_provider import ZarinPalProvider

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
