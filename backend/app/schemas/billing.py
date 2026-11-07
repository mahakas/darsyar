"""Schemaهای Pydantic مسیرهای پرداخت و پلن (ADR-047/052)."""

import uuid
from datetime import datetime

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


class PlanInfoOut(BaseModel):
    product_id: str
    price_toman: int
    credit_grant: int
    plan_type: str
    duration_days: int
    active: bool


class EntitlementOut(BaseModel):
    id: uuid.UUID
    product_id: str
    plan_type: str
    status: str
    activated_at: datetime
    expires_at: datetime
    granted_credits: int
    remaining_credits: int


class PrePurchaseInfoOut(BaseModel):
    product_id: str
    current_entitlement: EntitlementOut | None = None
    remaining_credits: int = 0
    message: str


class CancellationRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entitlement_id: uuid.UUID


class CancellationRequestOut(BaseModel):
    id: uuid.UUID
    entitlement_id: uuid.UUID
    status: str
    requested_at: datetime
