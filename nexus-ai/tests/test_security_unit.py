import time

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import RateLimited, Unauthorized
from app.core.ratelimit import TokenBucketLimiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    h = hash_password("s3cret!")
    assert h.startswith("$argon2") and verify_password("s3cret!", h) and not verify_password("nope", h)
    assert not verify_password("x", "not-a-hash")


def test_jwt_roundtrip_and_tamper():
    tok = create_access_token("u1", "o1", "analyst")
    assert decode_access_token(tok)["org"] == "o1"
    with pytest.raises(Unauthorized):
        decode_access_token(tok[:-2] + ("A" if tok[-1] != "A" else "B") + tok[-1])
    forged = jwt.encode(
        {"sub": "u1", "org": "o1", "role": "admin", "exp": time.time() + 60, "typ": "access"},
        "attacker-secret-attacker-secret-0123",
        algorithm="HS256",
    )
    with pytest.raises(Unauthorized):
        decode_access_token(forged)
    none_alg = jwt.encode({"sub": "u1", "exp": time.time() + 60, "typ": "access"}, None, algorithm="none")
    with pytest.raises(Unauthorized):
        decode_access_token(none_alg)


def test_rate_limiter():
    lim = TokenBucketLimiter(per_minute=3)
    for _ in range(3):
        lim.check("k")
    with pytest.raises(RateLimited):
        lim.check("k")
    lim.check("other-key")


def test_production_settings_reject_weak_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret="change-me-change-me-change-me-123")
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        Settings(llm_provider="gemini", gemini_api_key="")
    ok = Settings(app_env="production", jwt_secret="x" * 48)
    assert ok.app_env == "production"
