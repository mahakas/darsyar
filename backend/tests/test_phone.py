from app.core.phone import normalize_e164


def test_normalize_various_iranian_formats() -> None:
    assert normalize_e164("09121234567") == "+989121234567"
    assert normalize_e164("00989121234567") == "+989121234567"
    assert normalize_e164("+989121234567") == "+989121234567"
    assert normalize_e164("912 123 4567") == "+989121234567"


def test_normalize_rejects_invalid_phones() -> None:
    for invalid in ("", "123", "0912123456", "+981234567890", "+98912123456", "abc"):
        try:
            normalize_e164(invalid)
        except ValueError:
            continue
        raise AssertionError(f"{invalid!r} should have been rejected")
