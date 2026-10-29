"""مسیرهای احراز هویت OTP و چرخش نشست (فاز ۱)."""

import hmac
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip, rate_limit_dependency
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import RateLimitRule
from app.core.security import gen_csrf_token
from app.db.session import get_db
from app.schemas.auth import OtpRequest, OtpRequestResponse, OtpVerify, TokenResponse, UserOut
from app.services.auth import AuthService
from app.services.sms import KavenegarProvider, SmsProvider

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

OTP_REQUEST_PER_PHONE = RateLimitRule(settings.otp_request_limit_phone, settings.otp_request_window)
OTP_REQUEST_PER_IP = RateLimitRule(settings.otp_request_limit_ip, 60)
OTP_VERIFY_PER_IP = RateLimitRule(settings.otp_verify_rate_ip, 60)


def _sms_provider() -> SmsProvider:
    return KavenegarProvider(settings)


def _auth_service(session: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(session, _sms_provider())


def _phone_key_builder() -> Callable[[Request], str]:
    from app.core.phone import normalize_e164

    def key_builder(request: Request) -> str:
        try:
            return f"otp_request:phone:{normalize_e164(request.state.phone)}"
        except (AttributeError, ValueError):
            return f"otp_request:ip:{client_ip(request)}"

    return key_builder


def _ip_key_builder(prefix: str) -> Callable[[Request], str]:
    def key_builder(request: Request) -> str:
        return f"{prefix}:ip:{client_ip(request)}"

    return key_builder


@router.post("/otp/request", response_model=OtpRequestResponse, status_code=202)
async def request_otp(
    payload: OtpRequest,
    request: Request,
    service: Annotated[AuthService, Depends(_auth_service)],
) -> OtpRequestResponse:
    """درخواست کد؛ پاسخ برای شمارهٔ موجود/ناموجود یکسان است (R-103)."""
    request.state.phone = payload.phone
    await rate_limit_dependency(_phone_key_builder(), OTP_REQUEST_PER_PHONE)(request)
    await rate_limit_dependency(_ip_key_builder("otp_request"), OTP_REQUEST_PER_IP)(request)
    await service.request_otp(payload.phone)
    return OtpRequestResponse()


@router.post("/otp/verify", response_model=TokenResponse)
async def verify_otp(
    payload: OtpVerify,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_auth_service)],
) -> TokenResponse:
    """تأیید کد و صدور نشست؛ refresh در کوکی HttpOnly."""
    request.state.phone = payload.phone
    await rate_limit_dependency(_ip_key_builder("otp_verify"), OTP_VERIFY_PER_IP)(request)
    access_token, refresh_token, _, expires_in, user = await service.verify_otp(payload.phone, payload.code)
    _set_session_cookies(response, refresh_token)
    return TokenResponse(access_token=access_token, expires_in=expires_in, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_auth_service)],
) -> TokenResponse:
    """چرخش refresh با CSRF و کنترل Origin (R-109)."""
    raw_token = _read_refresh_cookie(request)
    _assert_csrf(request)
    access_token, refresh_token, _, expires_in, user = await service.rotate_refresh(raw_token)
    _set_session_cookies(response, refresh_token)
    return TokenResponse(access_token=access_token, expires_in=expires_in, user=UserOut.model_validate(user))


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_auth_service)],
) -> None:
    """باطل‌کردن خانوادهٔ نشست جاری."""
    raw_token = _read_refresh_cookie(request)
    await service.logout_family(raw_token)
    response.delete_cookie(settings.refresh_cookie_name, path="/", httponly=True, secure=settings.app_env == "production", samesite="lax")
    response.delete_cookie(settings.csrf_cookie_name, path="/", httponly=False, secure=settings.app_env == "production", samesite="lax")


def _read_refresh_cookie(request: Request) -> str:
    value = request.cookies.get(settings.refresh_cookie_name)
    if not value:
        raise AppError("invalid_refresh_token", 401, "نشست نامعتبر یا منقضی است.")
    return value


def _assert_csrf(request: Request) -> None:
    """CSRF با double-submit: هدر X-CSRF-Token باید با کوکی csrf برابر باشد (R-109)."""
    origin = request.headers.get("origin", "")
    if origin:
        allowed = {item.strip().rstrip("/") for item in settings.app_cors_origins}
        if origin.rstrip("/") not in allowed:
            raise AppError("csrf_origin_rejected", 403, "مبدأ درخواست مجاز نیست.")
    expected = request.cookies.get(settings.csrf_cookie_name, "")
    provided = request.headers.get("x-csrf-token", "")
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        raise AppError("csrf_token_mismatch", 403, "توکن محافظت درخواست نامعتبر است.")


def _set_session_cookies(response: Response, refresh_token: str) -> None:
    secure = settings.app_env == "production"
    response.set_cookie(
        settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        value=gen_csrf_token(),
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )
