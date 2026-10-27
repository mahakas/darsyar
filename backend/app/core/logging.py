"""لاگ JSON با redaction مقادیر محرمانه و بدون متن prompt کاربر."""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

_AUTH_PATTERN = re.compile(r"(?i)(authorization\s*[=:]\s*)(?:bearer|basic)\s+[^\s,;&]+")
_SENSITIVE_PATTERN = re.compile(
    r"""(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|secret|otp(?:[_-]?code)?|merchant[_-]?id|authority|prompt|cookie|set-cookie)(\s*[=:]\s*)("[^"]*"|'[^']*'|[^\s,;&]+)"""
)


def redact(value: str) -> str:
    """مقادیر حساس و نشانگرهای متداول راز را پیش از لاگ می‌پوشاند."""
    value = _AUTH_PATTERN.sub(r"\1[REDACTED]", value)
    return _SENSITIVE_PATTERN.sub(r"\1\2[REDACTED]", value)


class JsonFormatter(logging.Formatter):
    """رکورد log را به JSON تبدیل می‌کند و exception message خام را نشت نمی‌دهد."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.now(UTC).isoformat(), "level": record.levelname,
            "logger": record.name, "msg": redact(record.getMessage()),
        }
        for key in ("request_id", "user_id", "path", "method", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = redact(str(value)) if isinstance(value, str) else value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "UnknownException"
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """تنظیم‌کنندهٔ مرکزی لاگ JSON را فعال می‌کند."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """logger نام‌دار پروژه را برمی‌گرداند."""
    return logging.getLogger(name)
