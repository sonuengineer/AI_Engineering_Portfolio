"""FastAPI dependencies: DB session, authenticated principal, role checks, rate limiting."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Forbidden, NotFound, RateLimited, Unauthorized
from app.core.ratelimit import limiter
from app.core.security import decode_access_token
from app.models import Project, User

_bearer = HTTPBearer(auto_error=False)

ROLE_RANK = {"viewer": 0, "member": 1, "admin": 2}


@dataclass
class Principal:
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    email: str


DB = Annotated[Session, Depends(get_db)]


def get_principal(
    request: Request, db: DB, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthorized("Missing bearer token")
    claims = decode_access_token(creds.credentials)
    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except ValueError as exc:
        raise Unauthorized("Invalid token subject") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("User not found or inactive")
    route = request.scope.get("route")
    route_key = getattr(route, "path", request.url.path)
    if not limiter.allow(f"{user.id}:{request.method}:{route_key}", get_settings().rate_limit_per_minute):
        raise RateLimited("Too many requests")
    request.state.user_id = user.id
    request.state.org_id = user.org_id
    return Principal(user_id=user.id, org_id=user.org_id, role=user.role, email=user.email)


CurrentUser = Annotated[Principal, Depends(get_principal)]


def require_role(min_role: str) -> Callable[[Principal], Principal]:
    def dep(p: CurrentUser) -> Principal:
        if ROLE_RANK.get(p.role, -1) < ROLE_RANK[min_role]:
            raise Forbidden(f"Requires role '{min_role}' or higher")
        return p

    return dep


Member = Annotated[Principal, Depends(require_role("member"))]
Admin = Annotated[Principal, Depends(require_role("admin"))]


def get_project_or_404(db: Session, p: Principal, project_id: uuid.UUID) -> Project:
    proj = db.get(Project, project_id)
    if proj is None or proj.org_id != p.org_id:
        raise NotFound("project not found")
    return proj


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)
