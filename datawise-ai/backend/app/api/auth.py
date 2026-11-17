from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, request_id
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import AuditEvent, Org, User
from app.schemas.api import LoginRequest, MeResponse, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
# Unknown emails are verified against this hash so both paths pay the argon2 cost (no timing oracle).
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession, request: Request) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    password_ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not password_ok:
        db.add(AuditEvent(org_id=user.org_id if user else None, user_id=user.id if user else None,
                          action="auth.login_failed", detail={}, request_id=request_id(request)))
        db.commit()
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    db.add(AuditEvent(org_id=user.org_id, user_id=user.id, action="auth.login", detail={},
                      request_id=request_id(request)))
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.org_id, user.role))


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser, db: DbSession) -> MeResponse:
    org = db.get(Org, user.org_id)
    return MeResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role, org_id=user.org_id,
                      org_name=org.name if org else "")
