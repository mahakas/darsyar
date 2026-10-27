"""توابع ابتدایی رمزنگاری؛ جریان کامل احراز هویت در فاز ۱ ساخته می‌شود."""

import hashlib
import hmac


def otp_digest(code: str, pepper: str) -> str:
    """digest وابسته به pepper برای OTP کم‌آنتروپی تولید می‌کند."""
    return hmac.new(pepper.encode("utf-8"), code.encode("ascii"), hashlib.sha256).hexdigest()


def otp_matches(code: str, expected_digest: str, pepper: str) -> bool:
    """OTP را با مقایسهٔ ثابت‌زمان با digest ذخیره‌شده مقایسه می‌کند."""
    return hmac.compare_digest(otp_digest(code, pepper), expected_digest)


def token_digest(token: str) -> str:
    """برای توکن‌های تصادفی پرآنتروپی فقط digest ذخیره‌پذیر می‌سازد."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
