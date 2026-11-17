from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.ratelimit import TokenBucketLimiter
from app.core.security import decode_access_token
from app.models import User
from app.tools.registry import ROLE_RANK

_bearer = HTTPBearer(auto_error=False)
_limiter: TokenBucketLimiter | None = None


def limiter() -> TokenBucketLimiter:
    global _limiter
    if _limiter is None:
        _limiter = TokenBucketLimiter(get_settings().rate_limit_per_minute)
    return _limiter


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise Unauthorized("Missing bearer token")
    claims = decode_access_token(creds.credentials)
    user = db.get(User, claims["sub"])
    if user is None or not user.is_active or user.org_id != claims.get("org"):
        raise Unauthorized("User not found or inactive")
    request.state.user_id = user.id
    limiter().check(f"{user.id}:{request.url.path.split('/')[3] if request.url.path.count('/') > 2 else ''}")
    return user


def require_role(min_role: str) -> Callable[[User], User]:
    def dep(user: User = Depends(current_user)) -> User:
        if ROLE_RANK.get(user.role, -1) < ROLE_RANK[min_role]:
            raise Forbidden(f"Requires role '{min_role}' or higher")
        return user

    return dep
