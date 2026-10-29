"""Schemaهای Pydantic برای احراز هویت OTP و نشست."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OtpRequest(BaseModel):
    """درخواست ارسال کد؛ شماره قبل از هر استفاده نرمال می‌شود."""

    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=8, max_length=20)


class OtpVerify(BaseModel):
    """درخواست تأیید کد و صدور نشست."""

    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=8, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class UserOut(BaseModel):
    """نمای عمومی کاربر."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    name: str | None = None
    role: Literal["user", "admin"]


class TokenResponse(BaseModel):
    """پاسخ موفق نشست؛ refresh در کوکی HttpOnly حمل می‌شود و در بدنه نیست."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class OtpRequestResponse(BaseModel):
    """پاسخ یکسان و ضد-enumeration برای درخواست کد."""

    status: Literal["sent"] = "sent"
