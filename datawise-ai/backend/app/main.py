"""FastAPI app factory: middleware (request id, access log, CORS), error envelope, routers."""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, catalog, health, questions, reports
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("datawise.http")
    app = FastAPI(title="DATAWISE AI", version="0.1.0",
                  description="Natural-language BI with safe text-to-SQL (semantic layer -> plan -> validated SQL)")

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if 0 < len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        request.state.request_id = rid
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=rid)
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        log.info("http_request", method=request.method, path=request.url.path, status=response.status_code,
                 duration_ms=int((time.perf_counter() - t0) * 1000))
        return response

    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type",
                                                                         "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    install_error_handlers(app)
    for r in (health.router, auth.router, questions.router, reports.router, catalog.router):
        app.include_router(r)
    return app


app = create_app()
