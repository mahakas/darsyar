"""تست واحد adapter زرین‌پال با respx؛ بدون تماس شبکهٔ واقعی (R-216)."""

import pytest
import respx
from app.core.config import Settings
from app.services.payment_provider import (
    VERIFY_CODE_ALREADY_VERIFIED,
    VERIFY_CODE_SUCCESS,
    PaymentProviderMalformedError,
    PaymentProviderMerchantError,
    PaymentProviderValidationError,
    VerifyResult,
    ZarinPalProvider,
)
from httpx import ConnectError, Response

BASE = "https://sandbox.zarinpal.com"
AUTHORITY = "A" + "0" * 35


def _provider(merchant: str = "11111111-2222-3333-4444-555555555555", sandbox: bool = True) -> ZarinPalProvider:
    settings = Settings(
        app_env="test",
        zarinpal_merchant_id=merchant,
        zarinpal_sandbox=sandbox,
        zarinpal_callback_url="http://localhost/api/v1/billing/callback",
        zarinpal_timeout_seconds=5.0,
    )
    return ZarinPalProvider(settings)


def test_to_provider_amount_single_conversion_point() -> None:
    assert _provider().to_provider_amount(500000) == 5000000
    assert _provider().to_provider_amount(1000000) == 10000000


def test_gateway_url_built_from_base_and_validated_authority() -> None:
    provider = _provider()
    assert provider.gateway_url(AUTHORITY) == f"{BASE}/pg/StartPay/{AUTHORITY}"
    with pytest.raises(PaymentProviderValidationError):
        provider.gateway_url("BOGUS!")


@pytest.mark.asyncio
async def test_provider_requires_merchant_id() -> None:
    provider = _provider(merchant="")
    with pytest.raises(PaymentProviderMerchantError):
        await provider.request_payment(500000, "http://cb", "d")
    with pytest.raises(PaymentProviderMerchantError):
        await provider.verify_payment(AUTHORITY, 500000)


@respx.mock
async def test_request_payment_success_returns_authority() -> None:
    route = respx.post(f"{BASE}/pg/v4/payment/request.json").mock(
        return_value=Response(200, json={"data": {"authority": AUTHORITY, "fee": 1000}})
    )
    authority = await _provider().request_payment(500000, "http://cb", "darsyar-basic")
    assert authority == AUTHORITY
    import json as _json

    sent = _json.loads(route.calls[0].request.content)
    assert sent["merchant_id"] == "11111111-2222-3333-4444-555555555555"
    assert sent["amount"] == 5000000
    assert sent["callback_url"] == "http://cb"


@respx.mock
async def test_request_payment_merchant_error_status() -> None:
    respx.post(f"{BASE}/pg/v4/payment/request.json").mock(return_value=Response(401, json={}))
    with pytest.raises(PaymentProviderMerchantError):
        await _provider().request_payment(500000, "http://cb", "d")


@respx.mock
async def test_request_payment_malformed_response() -> None:
    respx.post(f"{BASE}/pg/v4/payment/request.json").mock(return_value=Response(200, text="not-json"))
    with pytest.raises(PaymentProviderMalformedError):
        await _provider().request_payment(500000, "http://cb", "d")
    respx.post(f"{BASE}/pg/v4/payment/request.json").mock(return_value=Response(200, json={"data": {}}))
    with pytest.raises(PaymentProviderMalformedError):
        await _provider().request_payment(500000, "http://cb", "d")


@respx.mock
async def test_request_payment_transport_error() -> None:
    from app.services.payment_provider import PaymentProviderTransportError

    respx.post(f"{BASE}/pg/v4/payment/request.json").mock(side_effect=ConnectError("conn-refused"))
    with pytest.raises(PaymentProviderTransportError):
        await _provider().request_payment(500000, "http://cb", "d")


@respx.mock
async def test_verify_payment_code_100_and_101() -> None:
    respx.post(f"{BASE}/pg/v4/payment/verify.json").mock(return_value=Response(200, json={"data": {"code": 100, "ref_id": "REF123"}}))
    assert await _provider().verify_payment(AUTHORITY, 500000) == VerifyResult(VERIFY_CODE_SUCCESS, "REF123")
    respx.post(f"{BASE}/pg/v4/payment/verify.json").mock(return_value=Response(200, json={"data": {"code": 101}}))
    assert await _provider().verify_payment(AUTHORITY, 500000) == VerifyResult(VERIFY_CODE_ALREADY_VERIFIED, None)


@respx.mock
async def test_verify_payment_malformed_and_failure_code() -> None:
    respx.post(f"{BASE}/pg/v4/payment/verify.json").mock(return_value=Response(200, json={"data": {"fee": 1}}))
    with pytest.raises(PaymentProviderMalformedError):
        await _provider().verify_payment(AUTHORITY, 500000)
    respx.post(f"{BASE}/pg/v4/payment/verify.json").mock(return_value=Response(200, json={"data": {"code": -60}}))
    assert (await _provider().verify_payment(AUTHORITY, 500000)).code == -60
