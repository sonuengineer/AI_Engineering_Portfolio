"""Validator unit tests: malicious and malformed SQL must be rejected; compiled SQL must pass."""

import pytest

from app.services.validator import validate_sql

MAX = 1000

MALICIOUS = [
    ("DELETE FROM orders", "DELETE"),
    ("DROP TABLE orders", "DROP"),
    ("TRUNCATE orders", "TRUNCATETABLE"),
    ("UPDATE products SET list_price = 0", "UPDATE"),
    ("INSERT INTO suppliers VALUES (99, 'x', 'y')", "INSERT"),
    ("ALTER TABLE orders ADD COLUMN x int", "ALTER"),
    ("GRANT ALL ON orders TO public", "GRANT"),
    ("CREATE TABLE x AS SELECT order_id FROM orders", "CREATE"),
    ("COPY orders TO '/tmp/out.csv'", "only SELECT"),
    ("SET statement_timeout = 0", "only SELECT"),
    ("SELECT order_id FROM orders LIMIT 5; DROP TABLE orders", "exactly one statement"),
    ("SELECT order_id FROM orders LIMIT 1; SELECT name FROM customers LIMIT 1", "exactly one statement"),
    ("WITH d AS (DELETE FROM orders RETURNING order_id) SELECT order_id FROM d LIMIT 1", "DELETE"),
    ("SELECT order_id INTO backup FROM orders LIMIT 1", "INTO"),
    ("SELECT order_id FROM orders LIMIT 1 FOR UPDATE", "LOCK"),
    ("SELECT pg_sleep(10) FROM orders LIMIT 1", "pg_sleep"),
    ("SELECT pg_read_file('/etc/passwd') FROM orders LIMIT 1", "pg_read_file"),
    ("SELECT dblink('host=x', 'select 1') FROM orders LIMIT 1", "dblink"),
    ("SELECT current_setting('server_version') FROM orders LIMIT 1", "function not allowed"),
    ("SELECT set_config('x', 'y', false) FROM orders LIMIT 1", "set_config"),
    ("SELECT version() FROM orders LIMIT 1", "function not allowed"),
    ("SELECT usename FROM pg_catalog.pg_user LIMIT 1", "pg_catalog"),
    ("SELECT passwd FROM pg_shadow LIMIT 1", "pg_shadow"),
    ("SELECT table_name FROM information_schema.tables LIMIT 5", "information_schema"),
    ("SELECT email, password_hash FROM users LIMIT 5", "users"),
    ("SELECT email FROM datawise_app.public.users LIMIT 5", "users"),
    ("SELECT * FROM orders LIMIT 5", "SELECT *"),
    ("SELECT name FROM customers", "missing LIMIT"),
    ("SELECT name FROM customers LIMIT 100000", "exceeds MAX_ROWS"),
    ("SELECT name FROM customers LIMIT 10 OFFSET 5", "OFFSET"),
    ("SELECT secret_col FROM customers LIMIT 5", "column not allowed"),
    ("SELECT name FROM customers UNION SELECT usename FROM pg_user LIMIT 5", "only SELECT"),
    ("SELECT name FROM (SELECT rolname AS name FROM pg_roles) x LIMIT 5", "pg_roles"),
    ("SELECT lo_import('/etc/passwd') FROM orders LIMIT 1", "lo_import"),
    ("EXPLAIN ANALYZE SELECT name FROM customers LIMIT 1", "only SELECT"),
    ("VACUUM orders", "only SELECT"),
    ("CALL do_something()", "only SELECT"),
    ("DO $$ BEGIN DELETE FROM orders; END $$", "only SELECT"),
    ("SELECT name FROM customers LIMIT (SELECT 5)", "LIMIT must be"),
    ("this is not sql at all", ""),
    ("", "exactly one statement"),
]


@pytest.mark.parametrize(("sql", "expected_issue"), MALICIOUS)
def test_malicious_sql_is_rejected(sql: str, expected_issue: str) -> None:
    result = validate_sql(sql, MAX)
    assert not result.ok, f"should be rejected: {sql}"
    if expected_issue:
        assert any(expected_issue.lower() in i.lower() for i in result.issues), result.issues


SAFE = [
    "SELECT name FROM customers LIMIT 5",
    "SELECT region, COUNT(customer_id) AS n FROM customers GROUP BY 1 ORDER BY n DESC LIMIT 10",
    "SELECT CAST(DATE_TRUNC('month', o.order_date) AS DATE) AS month, ROUND(SUM(oi.quantity * oi.unit_price), 2) "
    "AS revenue FROM orders o JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status <> 'cancelled' "
    "GROUP BY 1 ORDER BY month LIMIT 1000",
    "SELECT COUNT(*) FROM orders LIMIT 1",
]


@pytest.mark.parametrize("sql", SAFE)
def test_safe_sql_passes(sql: str) -> None:
    result = validate_sql(sql, MAX)
    assert result.ok, result.issues
