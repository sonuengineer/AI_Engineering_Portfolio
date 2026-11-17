"""Password hashing (argon2) and JWT access tokens."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import Unauthorized

_hasher = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: str, org_id: str, role: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "org": org_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
        "typ": "access",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        claims: dict[str, Any] = jwt.decode(
            token, get_settings().jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid or expired token") from exc
    if claims.get("typ") != "access":
        raise Unauthorized("Wrong token type")
    return claims
