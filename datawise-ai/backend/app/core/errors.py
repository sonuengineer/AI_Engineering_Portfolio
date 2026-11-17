"""JSON error envelope: {"error": {"code", "message", "request_id"}}."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _envelope(status: int, code: str, message: str, request: Request, extra: Any = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message, "request_id": _request_id(request)}}
    if extra is not None:
        body["error"]["details"] = extra
    headers = {"X-Request-ID": _request_id(request) or ""}
    return JSONResponse(status_code=status, content=body, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.status_code, exc.code, exc.message, request)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, "http_error"
        )
        return _envelope(exc.status_code, code, str(exc.detail), request)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return _envelope(422, "validation_error", "Request body is invalid", request, details)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        structlog.get_logger("datawise").error("unhandled_error", error_type=type(exc).__name__)
        return _envelope(500, "internal_error", "Internal server error", request)
