"""Insight correctness: numbers in answers must equal independently written SQL (admin connection)."""

from fastapi.testclient import TestClient


def scalar(conn, sql: str) -> float:  # type: ignore[no-untyped-def]
    with conn.cursor() as cur:
        cur.execute(sql)
        return float(cur.fetchone()[0])


def ask(client: TestClient, headers: dict[str, str], q: str):  # type: ignore[no-untyped-def]
    b = client.post("/api/v1/questions/ask", json={"question": q}, headers=headers).json()
    assert b["status"] == "answered", b
    return b


def test_total_revenue_2025_matches_direct_sql(client, acme_headers, admin_conn) -> None:  # type: ignore[no-untyped-def]
    expected = scalar(admin_conn, """
        SELECT SUM(oi.quantity * oi.unit_price) FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        WHERE o.status != 'cancelled' AND EXTRACT(YEAR FROM o.order_date) = 2025""")
    b = ask(client, acme_headers, "What was total revenue in 2025?")
    assert abs(b["rows"][0][0] - expected) < 0.01
    assert f"${expected:,.2f}" in b["insight"]


def test_top_product_insight_matches(client, acme_headers, admin_conn) -> None:  # type: ignore[no-untyped-def]
    with admin_conn.cursor() as cur:
        cur.execute("""
            SELECT p.name, SUM(oi.quantity * oi.unit_price) AS rev FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id JOIN products p ON p.product_id = oi.product_id
            WHERE o.status != 'cancelled' AND o.order_date BETWEEN '2025-01-01' AND '2025-12-31'
            GROUP BY p.name ORDER BY rev DESC LIMIT 1""")
        name, rev = cur.fetchone()
    b = ask(client, acme_headers, "Top 5 products by revenue in 2025")
    assert b["rows"][0][0] == name
    assert f"{name} at ${float(rev):,.2f}" in b["insight"]
    prov = b["insight_provenance"][0]
    assert prov["row_indexes"] == [0] and "revenue" in prov["columns"]


def test_time_series_change_is_computed_from_rows(client, acme_headers) -> None:  # type: ignore[no-untyped-def]
    b = ask(client, acme_headers, "Revenue by month in 2025")
    first, last = b["rows"][0][1], b["rows"][-1][1]
    pct = (last - first) / first * 100
    assert f"({pct:+.1f}%)" in b["insight"]
    total = sum(r[1] for r in b["rows"])
    assert f"${total:,.2f}" in b["insight"]


def test_conversion_rate_matches(client, acme_headers, admin_conn) -> None:  # type: ignore[no-untyped-def]
    expected = scalar(admin_conn, """
        SELECT SUM(CASE WHEN converted THEN 1 ELSE 0 END)::numeric / COUNT(*) FROM web_sessions
        WHERE session_date >= '2025-01-01' AND session_date < '2026-01-01'""")
    b = ask(client, acme_headers, "What was the conversion rate in 2025?")
    assert abs(b["rows"][0][0] - expected) < 0.0001


def test_on_time_rate_by_supplier_matches(client, acme_headers, admin_conn) -> None:  # type: ignore[no-untyped-def]
    with admin_conn.cursor() as cur:
        cur.execute("""
            SELECT s.name, AVG(CASE WHEN d.delivered_date <= d.promised_date THEN 1.0 ELSE 0.0 END)
            FROM supplier_deliveries d JOIN suppliers s USING (supplier_id)
            GROUP BY s.name ORDER BY 2 ASC, 1 LIMIT 1""")
        worst_name, worst_rate = cur.fetchone()
    b = ask(client, acme_headers, "Which suppliers have the worst on-time delivery rate?")
    assert b["rows"][0][0] == worst_name
    assert abs(b["rows"][0][1] - float(worst_rate)) < 0.0001


def test_empty_result_has_honest_insight(client, acme_headers) -> None:  # type: ignore[no-untyped-def]
    b = ask(client, acme_headers, "Revenue by month in 2023")
    assert b["row_count"] == 0 and "No data" in b["insight"]
