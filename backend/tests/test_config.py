import pytest
from app.core.config import Settings
from pydantic import SecretStr, ValidationError


def test_settings_reject_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="test", app_cors_origins=["*"])


def test_settings_reject_chunk_overlap_at_least_chunk_size() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="test", child_chunk_size=100, child_chunk_overlap=100)


def test_production_requires_high_entropy_independent_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", app_secret_key=SecretStr("too-short"), otp_pepper=SecretStr("too-short"))


def test_otp_pepper_must_differ_from_app_secret() -> None:
    secret = "a" * 40
    with pytest.raises(ValidationError):
        Settings(app_env="production", app_secret_key=SecretStr(secret), otp_pepper=SecretStr(secret), app_cors_origins=["https://example.invalid"])
