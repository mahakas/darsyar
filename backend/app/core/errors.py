"""خطاهای دامنه و handlerهای امن HTTP مطابق R-054."""

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AppError(Exception):
    """خطای شناخته‌شدهٔ دامنه با پیام مجاز برای نمایش به کاربر."""

    def __init__(self, code: str, http_status: int, message_for_user: str) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.message_for_user = message_for_user


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return str(value or uuid4())


def _payload(code: str, message: str, request_id: str) -> dict[str, str]:
    """شکل عمومی و ثابت خطای API را می‌سازد."""
    return {"code": code, "message": message, "request_id": request_id}


def install_error_handlers(app: FastAPI) -> None:
    """handlerهای خطای دامنه، اعتبارسنجی و خطای پیش‌بینی‌نشده را ثبت می‌کند."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(status_code=exc.http_status, content=_payload(exc.code, exc.message_for_user, request_id), headers={settings.request_id_header: request_id})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # ورودی نامعتبر ممکن است حاوی دادهٔ شخصی باشد؛ جزئیات مقدار ورودی را برنمی‌گردانیم.
        issues: list[dict[str, Any]] = [
            {"loc": list(error.get("loc", ())), "type": str(error.get("type", "invalid"))}
            for error in exc.errors()
        ]
        request_id = _request_id(request)
        return JSONResponse(status_code=422, content={**_payload("validation_error", "ورودی معتبر نیست.", request_id), "issues": issues}, headers={settings.request_id_header: request_id})

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = _request_id(request)
        headers = dict(exc.headers or {})
        headers[settings.request_id_header] = request_id
        return JSONResponse(status_code=exc.status_code, content=_payload("http_error", "درخواست قابل انجام نیست.", request_id), headers=headers)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.error("unexpected_error", extra={"request_id": request_id, "path": request.url.path, "method": request.method}, exc_info=exc)
        return JSONResponse(status_code=500, content=_payload("internal_error", "خطای داخلی رخ داد.", request_id), headers={settings.request_id_header: request_id})
