"""توابع ابتدایی رمزنگاری؛ جریان کامل احراز هویت در فاز ۱ ساخته می‌شود."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import PyJWTError

from app.core.config import get_settings

ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def otp_digest(code: str, pepper: str) -> str:
    """digest وابسته به pepper برای OTP کم‌آنتروپی تولید می‌کند."""
    return hmac.new(pepper.encode("utf-8"), code.encode("ascii"), hashlib.sha256).hexdigest()


def otp_matches(code: str, expected_digest: str, pepper: str) -> bool:
    """OTP را با مقایسهٔ ثابت‌زمان با digest ذخیره‌شده مقایسه می‌کند."""
    return hmac.compare_digest(otp_digest(code, pepper), expected_digest)


def resolve_pepper_for(pepper_id: str) -> str:
    """pepper متناظر با شناسهٔ ثبت‌شدهٔ چالش را برمی‌گرداند (پشتیبانی چرخش)."""
    from app.core.config import get_settings

    settings = get_settings()
    current_id = settings.otp_pepper_id
    current = settings.otp_pepper.get_secret_value() if settings.otp_pepper else ""
    previous = settings.otp_previous_pepper.get_secret_value() if settings.otp_previous_pepper else None
    if pepper_id == current_id and current:
        return current
    if previous and pepper_id == "v0":
        return previous
    raise ValueError("otp_pepper_unknown")


def token_digest(token: str) -> str:
    """برای توکن‌های تصادفی پرآنتروپی فقط digest ذخیره‌پذیر می‌سازد."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def gen_refresh_token() -> str:
    """توکن refresh تصادفی ۲۵۶-بیتی."""
    return secrets.token_urlsafe(32)


def gen_csrf_token() -> str:
    """توکن CSRF تصادفی برای کوکی double-submit."""
    return secrets.token_urlsafe(24)


def gen_otp_code(length: int) -> str:
    """کد OTP عددی با طول داده‌شده، بدون صفرهای پیش‌فرض غیر یکتا."""
    if length <= 0:
        raise ValueError("otp_code_length must be positive")
    return f"{secrets.randbelow(10 ** length):0{length}d}"


def _signing_secrets() -> tuple[str, str | None]:
    settings = get_settings()
    current = settings.app_secret_key.get_secret_value() if settings.app_secret_key else ""
    previous = settings.jwt_previous_secret.get_secret_value() if settings.jwt_previous_secret else None
    return current, previous


def create_token(subject: str, role: str, token_type: str, jti: str, *, lifetime: timedelta) -> str:
    current, _ = _signing_secrets()
    if not current:
        raise ValueError("APP_SECRET_KEY is not configured")
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, current, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str, *, allow_previous: bool = True) -> dict[str, Any]:
    """JWT را با کلید فعلی (و در صورت نیاز قبلی) اعتبارسنجی می‌کند."""
    current, previous = _signing_secrets()
    if not current:
        raise ValueError("APP_SECRET_KEY is not configured")
    candidates = [current]
    if allow_previous and previous:
        candidates.append(previous)
    last_error: PyJWTError | None = None
    for key in candidates:
        try:
            payload = jwt.decode(token, key, algorithms=[ALGORITHM])
        except PyJWTError as exc:
            last_error = exc
            continue
        if payload.get("type") != expected_type:
            raise ValueError("token_type_mismatch")
        return payload
    if last_error is not None:
        raise last_error
    raise ValueError("token_invalid")
