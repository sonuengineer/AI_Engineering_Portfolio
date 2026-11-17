"""Read-only enforcement: even if a write reached the executor, the reader role must refuse it."""

import psycopg
import pytest

from app.services.executor import ExecutionError, execute_readonly


def test_select_works(settings) -> None:  # type: ignore[no-untyped-def]
    r = execute_readonly("SELECT COUNT(*) FROM orders LIMIT 1", settings.analytics_reader_database_url, 10, 5000)
    assert r.rows[0][0] == 8000


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO suppliers (supplier_id, name, country) VALUES (9999, 'x', 'y')",
        "UPDATE products SET list_price = 0",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "CREATE TABLE evil (id int)",
        "TRUNCATE orders",
    ],
)
def test_writes_blocked_by_executor(settings, sql: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ExecutionError) as e:
        execute_readonly(sql, settings.analytics_reader_database_url, 10, 5000)
    assert e.value.code in ("read_only_violation", "execution_error")


def test_reader_role_cannot_write_even_in_read_write_transaction(settings) -> None:  # type: ignore[no-untyped-def]
    """Bypass our executor entirely: the role itself only has SELECT."""
    with psycopg.connect(settings.analytics_reader_database_url) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ WRITE")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("INSERT INTO suppliers (supplier_id, name, country) VALUES (9999, 'x', 'y')")


def test_reader_role_default_is_read_only(settings) -> None:  # type: ignore[no-untyped-def]
    with psycopg.connect(settings.analytics_reader_database_url) as conn, conn.cursor() as cur:
        cur.execute("SHOW default_transaction_read_only")
        assert cur.fetchone()[0] == "on"


def test_reader_cannot_connect_to_app_db(settings) -> None:  # type: ignore[no-untyped-def]
    dsn = settings.analytics_reader_database_url.rsplit("/", 1)[0] + "/datawise_app"
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(dsn, connect_timeout=5)


def test_statement_timeout(settings) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ExecutionError) as e:
        execute_readonly("SELECT pg_sleep(3)", settings.analytics_reader_database_url, 10, 300)
    assert e.value.code == "query_timeout"


def test_row_cap_applies_even_without_limit(settings) -> None:  # type: ignore[no-untyped-def]
    r = execute_readonly("SELECT order_id FROM orders", settings.analytics_reader_database_url, 50, 5000)
    assert len(r.rows) == 50 and r.truncated
