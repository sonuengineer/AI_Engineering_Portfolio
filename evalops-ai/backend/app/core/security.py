"""Password hashing (argon2) and JWT (HS256) helpers."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import Unauthorized

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID, org_id: uuid.UUID, role: str) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": str(org_id),
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(minutes=s.jwt_expire_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Token expired", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid token", code="invalid_token") from exc
