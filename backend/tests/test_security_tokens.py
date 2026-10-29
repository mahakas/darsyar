from datetime import timedelta

import jwt
import pytest
from app.core.security import (
    create_token,
    decode_token,
    gen_otp_code,
    gen_refresh_token,
    otp_digest,
    otp_matches,
    token_digest,
)


@pytest.fixture(autouse=True)
def _pinned_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    def fake_settings() -> Settings:
        return Settings(
            app_env="test",
            app_secret_key="s" * 40,
            jwt_previous_secret="p" * 40,
            otp_pepper="q" * 40,
            otp_pepper_id="v1",
            otp_previous_pepper=None,
        )

    monkeypatch.setattr("app.core.security.get_settings", fake_settings)
    monkeypatch.setattr("app.core.config.get_settings", fake_settings)


def test_create_and_decode_access_token() -> None:
    token = create_token("user-1", "user", "access", "jti-1", lifetime=timedelta(minutes=15))
    payload = decode_token(token, "access")
    assert payload["sub"] == "user-1"
    assert payload["role"] == "user"
    assert payload["jti"] == "jti-1"


def test_decode_rejects_wrong_token_type() -> None:
    token = create_token("user-1", "user", "refresh", "jti-2", lifetime=timedelta(days=7))
    with pytest.raises(ValueError):
        decode_token(token, "access")


def test_decode_rejects_tampered_signature() -> None:
    token = create_token("user-1", "user", "access", "jti-3", lifetime=timedelta(minutes=15))
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(jwt.PyJWTError):
        decode_token(tampered, "access")


def test_decode_accepts_previous_secret_rotation() -> None:
    import jwt as _jwt
    from app.core.security import ALGORITHM, _signing_secrets

    current, previous = _signing_secrets()
    assert previous is not None
    legacy = _jwt.encode({"sub": "u", "role": "user", "type": "access", "jti": "j", "iat": 0, "exp": 4_000_000_000}, previous, algorithm=ALGORITHM)
    payload = decode_token(legacy, "access")
    assert payload["sub"] == "u"


def test_otp_digest_never_plaintext_and_constant_time_compare() -> None:
    assert otp_digest("123456", "pepper-a") != otp_digest("123456", "pepper-b")
    digest = otp_digest("123456", "pepper")
    assert otp_matches("123456", digest, "pepper")
    assert not otp_matches("654321", digest, "pepper")
    assert "123456" not in digest


def test_token_digest_is_sha256_hex() -> None:
    digest = token_digest("some-high-entropy-token")
    assert len(digest) == 64
    assert digest != "some-high-entropy-token"


def test_gen_otp_code_length_and_digits() -> None:
    code = gen_otp_code(6)
    assert len(code) == 6
    assert code.isdigit()


def test_gen_refresh_token_high_entropy() -> None:
    a = gen_refresh_token()
    b = gen_refresh_token()
    assert a != b
    assert len(a) >= 32
