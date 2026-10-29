"""Schemaهای Pydantic مسیرهای پرداخت (ADR-047)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=32)
    idempotency_key: str = Field(min_length=8, max_length=128)


class CheckoutResponse(BaseModel):
    """پاسخ یکپارچه؛ HTTP 201 وقتی redirect_url موجود است، وگرنه 202."""

    payment_id: uuid.UUID
    status: str
    redirect_url: str | None = None
    amount_toman: int | None = None


class PaymentStatusOut(BaseModel):
    payment_id: uuid.UUID
    status: str
    amount_toman: int
    ref_id: str | None = None
