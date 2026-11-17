"""Test setup: migrate + seed a dedicated Postgres test database once per session.

Only true external boundaries (DNS, HTTP, LLM APIs) are faked; DB, retrieval, agents, tools,
approvals and the API run for real.
"""

import os
import tempfile

os.environ["APP_ENV"] = "test"
os.environ["LLM_PROVIDER"] = "local"
os.environ["EMBEDDING_PROVIDER"] = "local"
os.environ["INGESTION_MODE"] = "worker"  # tests drain the queue explicitly
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["DEMO_USER_PASSWORD"] = "test-password-123"
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="nexus-test-store-")
_TEST_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://nexus:nexus_local_only@localhost:5441/nexus_test")
os.environ["DATABASE_URL"] = _TEST_URL
os.environ["ALEMBIC_DATABASE_URL"] = _TEST_URL

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import configure_engine, session_factory  # noqa: E402

PASSWORD = "test-password-123"
BACKEND = Path(__file__).resolve().parents[1] / "backend"


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    get_settings.cache_clear()
    engine = configure_engine(_TEST_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public; CREATE EXTENSION IF NOT EXISTS vector"))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")
    from app.ingestion.storage import get_storage
    from scripts.seed import seed

    with session_factory()() as db:
        seed(db, get_storage(), password=PASSWORD)
    yield
    engine.dispose()


@pytest.fixture
def db() -> Iterator[Session]:
    s = session_factory()()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def login(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def manager(client: TestClient) -> dict[str, str]:
    return login(client, "manager@acme.example")


@pytest.fixture(scope="session")
def analyst(client: TestClient) -> dict[str, str]:
    return login(client, "analyst@acme.example")


@pytest.fixture(scope="session")
def viewer(client: TestClient) -> dict[str, str]:
    return login(client, "viewer@acme.example")


@pytest.fixture(scope="session")
def globex(client: TestClient) -> dict[str, str]:
    return login(client, "admin@globex.example")


def get_user(db: Session, email: str):  # type: ignore[no-untyped-def]
    from app.models import User

    return db.scalar(select(User).where(User.email == email))
