"""Shared FastAPI dependencies: current user, ask service, rate limiting."""

from __future__ import annotations

import threading
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.ratelimit import TokenBucketLimiter
from app.core.security import decode_access_token
from app.llm.base import PlannerProvider, ProviderError
from app.llm.factory import build_planner
from app.models import User
from app.services.ask import AskService

_bearer = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AppError(401, "unauthorized", "Missing bearer token")
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as e:
        raise AppError(401, "unauthorized", "Invalid or expired token") from e
    user = db.get(User, user_id)
    if user is None or user.org_id != payload.get("org"):
        raise AppError(401, "unauthorized", "Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

_planner_lock = threading.Lock()
_planner: PlannerProvider | None = None


def get_planner() -> PlannerProvider:
    global _planner
    with _planner_lock:
        if _planner is None:
            try:
                _planner = build_planner(get_settings())
            except ProviderError as e:
                raise AppError(503, "planner_unavailable", str(e)) from e
        return _planner


def reset_planner() -> None:
    global _planner
    with _planner_lock:
        _planner = None


def get_ask_service(planner: Annotated[PlannerProvider, Depends(get_planner)]) -> AskService:
    return AskService(get_settings(), planner)


_ask_limiter: TokenBucketLimiter | None = None


def ask_limiter() -> TokenBucketLimiter:
    global _ask_limiter
    if _ask_limiter is None:
        per_min = get_settings().rate_limit_ask_per_minute
        _ask_limiter = TokenBucketLimiter(capacity=per_min, refill_per_second=per_min / 60.0)
    return _ask_limiter


def rate_limit_ask(request: Request, user: CurrentUser) -> None:
    # One bucket per user for every endpoint that executes analytics queries (ask + report runs).
    # Keying on the concrete URL path gave each saved report its own bucket (limit bypass).
    if not ask_limiter().allow(f"{user.id}:query-execution"):
        raise AppError(429, "rate_limited", "Too many questions; please wait a moment")


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)
