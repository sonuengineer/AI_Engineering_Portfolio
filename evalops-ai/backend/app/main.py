"""FastAPI application factory."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import auth, health, resources, runs
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger

log = get_logger("evalops.api")


def _err(status: int, code: str, message: str, request: Request, extra: dict[str, object] | None = None) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    body: dict[str, object] = {"code": code, "message": message, "request_id": rid}
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content={"error": body}, headers={"X-Request-ID": rid or ""})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    stop = threading.Event()
    thread: threading.Thread | None = None
    if s.run_worker_in_api:
        from app.worker import worker_loop

        thread = threading.Thread(target=worker_loop, args=(stop,), name="evalops-worker", daemon=True)
        thread.start()
    yield
    stop.set()
    if thread:
        thread.join(timeout=5)


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level)
    app = FastAPI(title="EvalOps AI", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition", "X-Total-Count"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if incoming and len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        request.state.request_id = rid
        structlog.contextvars.bind_contextvars(request_id=rid)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        log.info("request", method=request.method, path=request.url.path, status=response.status_code,
                 duration_ms=round((time.perf_counter() - t0) * 1000, 1), request_id=rid)
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return _err(exc.status_code, exc.code, exc.message, request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()][:20]
        return _err(422, "validation_failed", "Request validation failed", request, {"details": details})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized"}.get(exc.status_code, "http_error")
        return _err(exc.status_code, code, str(exc.detail), request)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_error", error_type=type(exc).__name__)
        return _err(500, "internal_error", "Internal server error", request)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(resources.router)
    app.include_router(runs.router)
    return app


app = create_app()
