"""adapter زرین‌پال (R-040/R-143)؛ فقط این ماژول تومان→ریال تبدیل می‌کند."""

import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings

AUTHORITY_RE = re.compile(r"^[AS][0-9a-zA-Z]{35}$")
VERIFY_CODE_SUCCESS = 100
VERIFY_CODE_ALREADY_VERIFIED = 101


class PaymentProviderError(Exception):
    """خطای پایهٔ provider با طبقه‌بندی امن."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.message = message


class PaymentProviderValidationError(PaymentProviderError):
    def __init__(self, message: str) -> None:
        super().__init__("validation", message)


class PaymentProviderMerchantError(PaymentProviderError):
    def __init__(self, message: str) -> None:
        super().__init__("merchant", message)


class PaymentProviderTransportError(PaymentProviderError):
    def __init__(self, message: str) -> None:
        super().__init__("transport", message)


class PaymentProviderMalformedError(PaymentProviderError):
    def __init__(self, message: str) -> None:
        super().__init__("malformed", message)


@dataclass(frozen=True, slots=True)
class VerifyResult:
    code: int
    ref_id: str | None = None


class PaymentProvider(Protocol):
    async def request_payment(self, amount_toman: int, callback_url: str, description: str) -> str: ...
    async def verify_payment(self, authority: str, amount_toman: int) -> VerifyResult: ...
    def gateway_url(self, authority: str) -> str: ...
    def to_provider_amount(self, amount_toman: int) -> int: ...


class ZarinPalProvider:
    """پیاده‌سازی v4؛ تبدیل تومان→ریال فقط اینجا (R-143)."""

    PROD_BASE_URL = "https://payment.zarinpal.com"
    SANDBOX_BASE_URL = "https://sandbox.zarinpal.com"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        base = self.SANDBOX_BASE_URL if self._settings.zarinpal_sandbox else self.PROD_BASE_URL
        self._base_url = base
        self._merchant_id = (
            self._settings.zarinpal_merchant_id.get_secret_value() if self._settings.zarinpal_merchant_id else ""
        )
        self._timeout = self._settings.zarinpal_timeout_seconds

    def to_provider_amount(self, amount_toman: int) -> int:
        """یکتای نقطهٔ تبدیل تومان→ریال (R-143)."""
        return amount_toman * 10

    def gateway_url(self, authority: str) -> str:
        if not AUTHORITY_RE.fullmatch(authority):
            raise PaymentProviderValidationError("invalid_authority_format")
        return f"{self._base_url}/pg/StartPay/{authority}"

    async def request_payment(self, amount_toman: int, callback_url: str, description: str) -> str:
        if not self._merchant_id:
            raise PaymentProviderMerchantError("merchant_id_missing")
        if amount_toman <= 0:
            raise PaymentProviderValidationError("invalid_amount")
        payload = {
            "merchant_id": self._merchant_id,
            "amount": self.to_provider_amount(amount_toman),
            "callback_url": callback_url,
            "description": description,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/pg/v4/payment/request.json", json=payload)
        except httpx.HTTPError as exc:
            raise PaymentProviderTransportError(f"transport_failure: {type(exc).__name__}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise PaymentProviderMalformedError("malformed_response") from exc
        if response.status_code in (401, 403, 404):
            raise PaymentProviderMerchantError(f"merchant_error_status_{response.status_code}")
        data = body.get("data") if isinstance(body, dict) else None
        authority = data.get("authority") if isinstance(data, dict) else None
        if not isinstance(authority, str) or not AUTHORITY_RE.fullmatch(authority):
            raise PaymentProviderMalformedError("missing_or_invalid_authority")
        return authority

    async def verify_payment(self, authority: str, amount_toman: int) -> VerifyResult:
        if not self._merchant_id:
            raise PaymentProviderMerchantError("merchant_id_missing")
        if not AUTHORITY_RE.fullmatch(authority):
            raise PaymentProviderValidationError("invalid_authority_format")
        payload = {
            "merchant_id": self._merchant_id,
            "authority": authority,
            "amount": self.to_provider_amount(amount_toman),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/pg/v4/payment/verify.json", json=payload)
        except httpx.HTTPError as exc:
            raise PaymentProviderTransportError(f"transport_failure: {type(exc).__name__}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise PaymentProviderMalformedError("malformed_response") from exc
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict) or "code" not in data:
            raise PaymentProviderMalformedError("missing_verify_code")
        try:
            code = int(data["code"])
        except (TypeError, ValueError) as exc:
            raise PaymentProviderMalformedError("invalid_verify_code") from exc
        ref_id = data.get("ref_id")
        return VerifyResult(code=code, ref_id=str(ref_id) if ref_id else None)
