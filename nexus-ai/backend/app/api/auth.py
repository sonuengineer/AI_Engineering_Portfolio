from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, limiter
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Organization, User
from app.schemas.api import LoginIn, MeOut, TokenOut
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])
# Verified against when the email is unknown, so both paths pay the argon2 cost (no timing oracle).
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    ip = request.client.host if request.client else "unknown"
    limiter().check(f"login:{ip}", cost=6)  # ~10 attempts/minute/IP at default settings
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    password_ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not user.is_active or not password_ok:
        if user is not None:
            audit(db, org_id=user.org_id, actor_id=user.id, action="auth.login", outcome="denied")
            db.commit()
        raise Unauthorized("Invalid email or password")  # same message: no user enumeration
    audit(db, org_id=user.org_id, actor_id=user.id, action="auth.login")
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.org_id, user.role))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> MeOut:
    org = db.get(Organization, user.org_id)
    s = get_settings()
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        org_id=user.org_id,
        org_name=org.name if org else "",
        llm_provider=s.llm_provider,
        embedding_provider=s.embedding_provider,
    )
