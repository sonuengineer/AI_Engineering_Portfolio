"""NEXUS AI API entrypoint."""

import threading
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import admin, auth, chat, documents, workflows
from app.core.config import get_settings
from app.core.context import request_id_var
from app.core.db import get_engine
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import configure_tracing
from app.tools import builtin as _builtin_tools  # noqa: F401 -- registers tools

log = get_logger("nexus.api")


def _embedded_worker(stop: threading.Event) -> None:
    from app.core.db import session_factory
    from app.ingestion.jobs import claim_next, run_job
    from app.ingestion.storage import get_storage

    storage = get_storage()
    while not stop.is_set():
        try:
            with session_factory()() as db:
                job = claim_next(db)
                if job is None:
                    stop.wait(1.0)
                    continue
                run_job(db, job, storage)
        except Exception as exc:  # noqa: BLE001 -- keep the loop alive; job state records failures
            log.error("embedded_worker_error", error_type=type(exc).__name__)
            stop.wait(2.0)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    configure_tracing("nexus-api")
    from app.ingestion.storage import prepare_storage

    try:
        prepare_storage()
    except Exception as exc:  # noqa: BLE001 -- storage outage must not block boot; uploads will report it
        log.error("storage_prepare_failed", error_type=type(exc).__name__)
    from app.services.workflows import mark_interrupted_runs

    try:
        n = mark_interrupted_runs()
        if n:
            log.warning("marked_interrupted_runs", count=n)
    except Exception as exc:  # noqa: BLE001 -- DB may be down at boot; readiness reports it
        log.error("startup_recovery_failed", error_type=type(exc).__name__)
    stop = threading.Event()
    if get_settings().ingestion_mode == "embedded":
        threading.Thread(target=_embedded_worker, args=(stop,), daemon=True, name="ingest").start()
    yield
    stop.set()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="NEXUS AI", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if incoming.replace("-", "").isalnum() and len(incoming) <= 64 else uuid.uuid4().hex
        request.state.request_id = rid
        token = request_id_var.set(rid)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=int((time.perf_counter() - t0) * 1000),
            request_id=rid,
        )
        return response

    install_error_handlers(app)
    for r in (auth.router, chat.router, documents.router, workflows.router, admin.router):
        app.include_router(r, prefix="/api/v1")

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    def readyz(response: Response) -> dict[str, str]:
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ready", "llm_provider": s.llm_provider}
        except Exception:  # noqa: BLE001
            response.status_code = 503
            return {"status": "unavailable"}

    return app


app = create_app()
