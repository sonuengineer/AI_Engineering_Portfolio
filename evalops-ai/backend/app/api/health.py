from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.db import session_factory

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
def readyz() -> dict[str, str] | JSONResponse:
    try:
        with session_factory()() as s:
            s.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}
