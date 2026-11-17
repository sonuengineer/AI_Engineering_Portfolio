from typing import Any

import psycopg
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
def readyz() -> dict[str, Any] | JSONResponse:
    checks: dict[str, str] = {}
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
        checks["app_db"] = "ok"
    except Exception:
        checks["app_db"] = "unavailable"
    try:
        with psycopg.connect(get_settings().analytics_reader_database_url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        checks["analytics_db"] = "ok"
    except Exception:
        checks["analytics_db"] = "unavailable"
    ok = all(v == "ok" for v in checks.values())
    body = {"status": "ready" if ok else "not_ready", "checks": checks, "provider": get_settings().llm_provider}
    return body if ok else JSONResponse(status_code=503, content=body)
