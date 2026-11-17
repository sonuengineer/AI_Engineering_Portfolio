"""Shared fixtures. Tests run against a REAL Postgres database (docker compose `db`, database
`evalops_test`), never SQLite. Override with TEST_DATABASE_URL."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://evalops:evalops_dev_password@localhost:5443/evalops_test"
)
os.environ["RUN_WORKER_IN_API"] = "false"
os.environ["LLM_PROVIDER"] = "local"
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-0123456789"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "100000"

from collections.abc import Iterator  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, get_engine, reset_engine, session_scope  # noqa: E402
from app.core.ratelimit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Org, User  # noqa: E402

PASSWORD = "test-password-123"


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> Iterator[None]:
    get_settings.cache_clear()
    reset_engine()
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    yield
    reset_engine()


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    yield
    with session_scope() as s:
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        s.execute(text(f"TRUNCATE {tables} CASCADE"))
    limiter.reset()


def make_org(slug: str) -> dict[str, Any]:
    """Create an org with admin/member/viewer users; returns ids and emails."""
    with session_scope() as s:
        org = Org(name=slug.title(), slug=slug)
        s.add(org)
        s.flush()
        users = {}
        for role in ("admin", "member", "viewer"):
            u = User(org_id=org.id, email=f"{role}@{slug}.test", password_hash=hash_password(PASSWORD), role=role)
            s.add(u)
            s.flush()
            users[role] = u.id
        return {"org_id": org.id, "users": users, "slug": slug}


@pytest.fixture
def org_a() -> dict[str, Any]:
    return make_org("alpha")


@pytest.fixture
def org_b() -> dict[str, Any]:
    return make_org("beta")
