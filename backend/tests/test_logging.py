from app.core.logging import redact


def test_redact_masks_sensitive_value() -> None:
    assert redact("api_key=secret123") == "api_key=[REDACTED]"
    assert redact("otp_code: 123456") == "otp_code: [REDACTED]"


def test_redact_leaves_regular_text_unchanged() -> None:
    assert redact("request completed with status=200") == "request completed with status=200"


def test_log_redaction_handles_authorization_header() -> None:
    assert redact("authorization=Bearer abc.def") == "authorization=[REDACTED]"


def test_redact_masks_payment_and_prompt_values() -> None:
    assert redact("merchant_id=secret123") == "merchant_id=[REDACTED]"
    assert redact("prompt=private-question") == "prompt=[REDACTED]"
