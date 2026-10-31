"""تنظیمات type-safe برنامهٔ درسیار."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """تنظیمات زیرساختی که در فاز جاری توسط برنامه خوانده می‌شوند."""

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    app_name: str = "Darsyar AI"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "production"] = "development"
    app_secret_key: SecretStr | None = None
    app_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    trusted_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "api"])
    forwarded_allow_ips: str = "127.0.0.1"
    request_id_header: str = "X-Request-ID"
    log_level: str = "INFO"
    log_format: str = "json"

    database_url: str = "postgresql+asyncpg://darsyar:change-me@localhost:5432/darsyar"
    database_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    database_pool_size: int = Field(default=5, ge=1, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=200)
    database_pool_timeout: float = Field(default=30.0, gt=0, le=300)
    test_database_url: str = "postgresql+asyncpg://darsyar:change-me@localhost:5432/darsyar_test"
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = Field(default=20, gt=0, le=1000)
    settings_cache_ttl: int = Field(default=30, gt=0, le=3600)

    jwt_algorithm: Literal["HS256", "HS384", "HS512", "RS256", "RS384", "RS512", "ES256"] = "HS256"
    jwt_previous_secret: SecretStr | None = None
    refresh_grace_seconds: int = Field(default=30, ge=0, le=120)
    access_token_expire_minutes: int = Field(default=15, gt=0, le=120)
    refresh_token_expire_days: int = Field(default=7, gt=0, le=30)
    refresh_cookie_name: str = "darsyar_refresh"
    csrf_cookie_name: str = "darsyar_csrf"
    otp_code_length: int = Field(default=6, ge=4, le=8)
    otp_expire_seconds: int = Field(default=120, ge=30, le=600)
    otp_max_attempts: int = Field(default=5, ge=1, le=20)
    otp_request_limit_phone: int = Field(default=3, ge=1, le=20)
    otp_request_window: int = Field(default=300, ge=30, le=3600)
    otp_request_limit_ip: int = Field(default=10, ge=1, le=100)
    otp_verify_rate_ip: int = Field(default=20, ge=1, le=200)
    chat_rate_user: int = Field(default=30, ge=1, le=1000)
    chat_rate_ip: int = Field(default=60, ge=1, le=1000)
    otp_pepper: SecretStr | None = None
    otp_pepper_id: str = "v1"
    otp_previous_pepper: SecretStr | None = None
    sms_provider: Literal["kavenegar"] = "kavenegar"
    kavenegar_api_key: SecretStr | None = None
    kavenegar_otp_template: str = ""
    kavenegar_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    admin_email: str = ""
    admin_phone: str = ""
    admin_name: str = ""
    admin_password_login_enabled: bool = False
    page_size_max: int = Field(default=100, ge=1, le=1000)
    max_request_bytes: int = Field(default=20971520, ge=1024, le=104857600)
    reservation_stale_minutes: int = Field(default=15, ge=1, le=1440)
    reconcile_interval_minutes: int = Field(default=5, ge=1, le=1440)
    min_billable_tokens: int = Field(default=1, ge=1, le=1000)
    payment_provider: Literal["zarinpal"] = "zarinpal"
    zarinpal_merchant_id: SecretStr | None = None
    zarinpal_sandbox: bool = False
    zarinpal_callback_url: str = ""
    zarinpal_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    payment_request_stale_minutes: int = Field(default=30, ge=1, le=1440)
    credit_reconcile_alert_threshold: int = Field(default=1, ge=0, le=1000000000)
    free_plan_credits: int = Field(default=5, gt=0, le=1000)

    inference_mode: Literal["service", "remote"] = "remote"
    inference_url: str = "http://localhost:8100"
    inference_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    request_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    model_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    hf_home: str = "/models/huggingface"

    child_chunk_size: int = Field(default=400, gt=0, le=10000)
    child_chunk_overlap: int = Field(default=60, ge=0, le=5000)
    parent_chunk_size: int = Field(default=1200, gt=0, le=20000)
    min_confidence: float = Field(default=0.35, ge=0.0, le=1.0)
    min_retrieval_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reranker_top_k: int = Field(default=20, gt=0, le=100)
    max_context_tokens: int = Field(default=12000, gt=0, le=200000)
    resources_dir: str = "./resources"
    upload_dir: str = "./uploads"
    supported_languages: list[str] = Field(default_factory=lambda: ["fa", "en", "ar"])
    default_language: Literal["fa", "en", "ar"] = "fa"
    trace_store_prompts: bool = False
    allowed_fetch_domains: list[str] = Field(default_factory=list)

    @field_validator("app_cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        """فهرست CORS را به مبدأهای دقیق و غیرتهی محدود می‌کند."""
        normalized = [item.strip().rstrip("/") for item in value if item.strip()]
        if not normalized or "*" in normalized:
            raise ValueError("APP_CORS_ORIGINS must be non-empty and must not contain '*'")
        return normalized

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "Settings":
        """قیود متقابل تنظیمات و boot guard امنیتی را بررسی می‌کند."""
        if self.child_chunk_overlap >= self.child_chunk_size:
            raise ValueError("CHILD_CHUNK_OVERLAP must be smaller than CHILD_CHUNK_SIZE")
        if self.app_env == "production":
            secret = self.app_secret_key.get_secret_value() if self.app_secret_key else ""
            pepper = self.otp_pepper.get_secret_value() if self.otp_pepper else ""
            if secret.startswith("CHANGE_ME") or len(secret.encode("utf-8")) < 32:
                raise ValueError("APP_SECRET_KEY must be a strong production secret (at least 32 bytes)")
            if pepper.startswith("CHANGE_ME") or len(pepper.encode("utf-8")) < 32:
                raise ValueError("OTP_PEPPER must be an independent strong production secret")
            if secret == pepper:
                raise ValueError("OTP_PEPPER must differ from APP_SECRET_KEY")
            if self.sms_provider == "kavenegar":
                sms_key = self.kavenegar_api_key.get_secret_value() if self.kavenegar_api_key else ""
                if not sms_key or sms_key.startswith("CHANGE_ME"):
                    raise ValueError("KAVENEGAR_API_KEY must be a valid production secret")
            if self.payment_provider == "zarinpal":
                merchant = self.zarinpal_merchant_id.get_secret_value() if self.zarinpal_merchant_id else ""
                if not merchant or merchant.startswith("CHANGE_ME"):
                    raise ValueError("ZARINPAL_MERCHANT_ID must be a valid production secret")
                if not self.zarinpal_callback_url.startswith("https://"):
                    raise ValueError("ZARINPAL_CALLBACK_URL must be an https URL in production")
            if not self.app_cors_origins or "*" in self.app_cors_origins:
                raise ValueError("APP_CORS_ORIGINS must be explicit in production")
            if self.inference_mode not in {"service", "remote"}:
                raise ValueError("INFERENCE_MODE must be service or remote")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """نمونهٔ تنظیمات را برای هر process cache می‌کند."""
    return Settings()
