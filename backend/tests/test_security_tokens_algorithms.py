"""Configured JWT algorithm must be the algorithm actually used for tokens."""

from datetime import timedelta

import jwt
import pytest
from app.core.config import get_settings
from app.core.security import create_token, decode_token
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512"])
def test_hmac_algorithm_is_honoured(monkeypatch: pytest.MonkeyPatch, algorithm: str) -> None:
    monkeypatch.setenv("JWT_ALGORITHM", algorithm)
    monkeypatch.setenv("APP_SECRET_KEY", "x" * 48)

    token = create_token("user-id", "user", "access", "jti-1", lifetime=timedelta(minutes=5))

    assert jwt.get_unverified_header(token)["alg"] == algorithm
    assert decode_token(token, "access")["sub"] == "user-id"


def test_rsa_algorithm_uses_derived_public_key(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    monkeypatch.setenv("JWT_ALGORITHM", "RS256")
    monkeypatch.setenv("APP_SECRET_KEY", pem)

    token = create_token("user-id", "user", "access", "jti-2", lifetime=timedelta(minutes=5))

    assert jwt.get_unverified_header(token)["alg"] == "RS256"
    assert decode_token(token, "access")["sub"] == "user-id"


def test_es256_algorithm_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    monkeypatch.setenv("JWT_ALGORITHM", "ES256")
    monkeypatch.setenv("APP_SECRET_KEY", pem)

    token = create_token("user-id", "user", "access", "jti-3", lifetime=timedelta(minutes=5))

    assert jwt.get_unverified_header(token)["alg"] == "ES256"
    assert decode_token(token, "access")["sub"] == "user-id"
