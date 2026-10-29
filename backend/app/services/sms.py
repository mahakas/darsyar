"""adapter پیامک (R-040)؛ MVP فقط Kavenegar با verify پاسخ و timeout صریح."""

from typing import Protocol

import httpx

from app.core.config import Settings, get_settings


class SmsError(Exception):
    """خطای ارسال پیامک."""


class SmsProvider(Protocol):
    async def send_otp(self, phone: str, code: str) -> None: ...


class KavenegarProvider:
    """ارسال OTP از طریق Kavenegar؛ بدون وابستگی به SDK و با timeout/retry محدود."""

    BASE_URL = "https://api.kavenegar.com/v1"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._api_key = self._settings.kavenegar_api_key.get_secret_value() if self._settings.kavenegar_api_key else ""

    async def send_otp(self, phone: str, code: str) -> None:
        if not self._api_key:
            raise SmsError("kavenegar_api_key_missing")
        if not self._settings.kavenegar_otp_template:
            raise SmsError("kavenegar_otp_template_missing")
        url = f"{self.BASE_URL}/{self._api_key}/verify/lookup.json"
        payload = {
            "receptor": phone,
            "token": code,
            "template": self._settings.kavenegar_otp_template,
        }
        async with httpx.AsyncClient(timeout=self._settings.kavenegar_timeout_seconds) as client:
            response = await client.post(url, data=payload, follow_redirects=False)
        if response.status_code != 200 or response.json().get("return", {}).get("status") != 200:
            raise SmsError("kavenegar_send_failed")
