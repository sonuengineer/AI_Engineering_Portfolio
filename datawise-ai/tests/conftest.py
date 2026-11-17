"""Test fixtures. Tests run against the REAL compose Postgres (host port 5442 by default).

Session start: apply Alembic migrations, seed demo users, seed analytics if empty.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.services.values import ValueIndex, load_value_index  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_databases() -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")
    from scripts import seed, seed_analytics

    seed.main()
    seed_analytics.seed(reset=False)


@pytest.fixture(scope="session")
def settings():  # type: ignore[no-untyped-def]
    return get_settings()


@pytest.fixture(scope="session")
def values(settings) -> ValueIndex:  # type: ignore[no-untyped-def]
    return load_value_index(settings.analytics_reader_database_url)


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    from app.api.deps import ask_limiter

    ask_limiter().reset()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def acme_headers(client: TestClient, settings) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return _login(client, "demo@acme.example", settings.demo_user_password)


@pytest.fixture(scope="session")
def globex_headers(client: TestClient, settings) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return _login(client, "demo@globex.example", settings.demo_user_password)


@pytest.fixture(scope="session")
def admin_conn(settings):  # type: ignore[no-untyped-def]
    """Admin connection to analytics -- used ONLY to compute independent expected values."""
    import psycopg

    conn = psycopg.connect(settings.analytics_admin_database_url, autocommit=True)
    yield conn
    conn.close()
