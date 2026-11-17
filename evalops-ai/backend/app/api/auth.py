from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app.api.deps import DB, Admin, CurrentUser, request_id
from app.core.config import get_settings
from app.core.errors import Conflict, RateLimited, Unauthorized
from app.core.ratelimit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas import LoginIn, TokenOut, UserCreate, UserOut
from app.services import audit

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: DB) -> TokenOut:
    ip = request.client.host if request.client else "unknown"
    if not limiter.allow(f"login:{ip}", get_settings().login_rate_limit_per_minute):
        raise RateLimited("Too many login attempts")
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        audit.record(db, org_id=user.org_id if user else None, user_id=None, action="auth.login_failed",
                     resource_type="user", details={"email": body.email}, request_id=request_id(request))
        db.commit()
        raise Unauthorized("Invalid email or password", code="invalid_credentials")
    audit.record(db, org_id=user.org_id, user_id=user.id, action="auth.login", resource_type="user",
                 resource_id=user.id, request_id=request_id(request))
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.org_id, user.role))


@router.get("/auth/me", response_model=UserOut)
def me(p: CurrentUser, db: DB) -> User:
    user = db.get(User, p.user_id)
    assert user is not None
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(p: Admin, db: DB) -> list[User]:
    return list(db.scalars(select(User).where(User.org_id == p.org_id).order_by(User.email)))


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, p: Admin, db: DB, request: Request) -> User:
    if db.scalar(select(User).where(func.lower(User.email) == body.email.lower())):
        raise Conflict("email already registered")
    user = User(org_id=p.org_id, email=body.email.lower(), display_name=body.display_name,
                password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    audit.record(db, org_id=p.org_id, user_id=p.user_id, action="user.create", resource_type="user",
                 resource_id=user.id, details={"role": body.role}, request_id=request_id(request))
    db.commit()
    return user
