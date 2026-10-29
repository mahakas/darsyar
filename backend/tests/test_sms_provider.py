"""تست adapter پیامک Kavenegar با respx؛ بدون شبکهٔ واقعی (R-216)."""

import pytest
import respx
from app.core.config import Settings
from app.services.sms import KavenegarProvider, SmsError
from httpx import Response


def _provider(api_key: str = "secret-key", template: str = "darsyar-otp") -> KavenegarProvider:
    settings = Settings(
        app_env="test",
        kavenegar_api_key=api_key,
        kavenegar_otp_template=template,
        kavenegar_timeout_seconds=5.0,
    )
    return KavenegarProvider(settings)


@respx.mock
async def test_send_otp_success() -> None:
    route = respx.post("https://api.kavenegar.com/v1/secret-key/verify/lookup.json").mock(
        return_value=Response(200, json={"return": {"status": 200, "message": "ok"}})
    )
    await _provider().send_otp("+989121234567", "123456")
    assert route.called
    request = route.calls[0].request
    assert request.content and b"receptor=%2B989121234567" in request.content
    assert b"token=123456" in request.content
    assert b"template=darsyar-otp" in request.content


@respx.mock
async def test_send_otp_fails_on_provider_error_status() -> None:
    respx.post("https://api.kavenegar.com/v1/secret-key/verify/lookup.json").mock(
        return_value=Response(200, json={"return": {"status": 400, "message": "bad request"}})
    )
    with pytest.raises(SmsError):
        await _provider().send_otp("+989121234567", "123456")


@respx.mock
async def test_send_otp_fails_on_http_error_status() -> None:
    respx.post("https://api.kavenegar.com/v1/secret-key/verify/lookup.json").mock(
        return_value=Response(503, json={})
    )
    with pytest.raises(SmsError):
        await _provider().send_otp("+989121234567", "123456")


async def test_provider_requires_api_key_and_template() -> None:
    with pytest.raises(SmsError):
        await _provider(api_key="", template="darsyar-otp").send_otp("+989121234567", "123456")
    with pytest.raises(SmsError):
        await _provider(api_key="secret-key", template="").send_otp("+989121234567", "123456")
