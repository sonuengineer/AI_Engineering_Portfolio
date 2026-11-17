from datetime import date

import pytest

from app.schemas.plan import Filter, OrderBy, QueryPlan, TimeRange
from app.semantic.layer import DIMENSIONS, FACTS, METRICS
from app.services.compiler import PlanError, compile_plan
from app.services.validator import validate_sql


def test_revenue_excludes_cancelled_and_applies_time_range() -> None:
    plan = QueryPlan(metrics=["revenue"], time_range=TimeRange(start=date(2025, 1, 1), end=date(2026, 1, 1)))
    sql = compile_plan(plan, 1000).sql
    assert "o.status <> 'cancelled'" in sql
    assert "o.order_date >= CAST('2025-01-01' AS DATE)" in sql
    assert "o.order_date < CAST('2026-01-01' AS DATE)" in sql
    assert sql.strip().endswith("LIMIT 100")


def test_supplier_join_pulls_in_products_first() -> None:
    sql = compile_plan(QueryPlan(metrics=["revenue"], dimensions=["supplier"]), 1000).sql
    assert sql.index("JOIN products p") < sql.index("JOIN suppliers s")


def test_string_literals_are_escaped() -> None:
    plan = QueryPlan(metrics=["revenue"], filters=[Filter(field="customer", value="O'Brien'); DROP TABLE x; --")])
    sql = compile_plan(plan, 1000).sql
    assert "'O''Brien''); DROP TABLE x; --'" in sql
    assert validate_sql(sql, 1000).ok


def test_limit_is_clamped_to_max_rows() -> None:
    sql = compile_plan(QueryPlan(metrics=["revenue"], dimensions=["customer"], limit=50000), 1000).sql
    assert sql.strip().endswith("LIMIT 1000")


def test_metric_filter_becomes_having() -> None:
    plan = QueryPlan(metrics=["revenue"], dimensions=["customer"],
                     filters=[Filter(field="revenue", kind="metric", op="gt", value=1000)],
                     order_by=[OrderBy(field="revenue", direction="desc")])
    sql = compile_plan(plan, 1000).sql
    assert "HAVING ROUND(SUM(oi.quantity * oi.unit_price), 2) > 1000" in sql
    assert "ORDER BY revenue DESC, customer ASC" in sql


@pytest.mark.parametrize(
    ("plan_kwargs", "issue"),
    [
        ({"metrics": ["churn"]}, "unknown metric"),
        ({"metrics": ["revenue", "conversion_rate"]}, "different facts"),
        ({"metrics": ["conversion_rate"], "dimensions": ["product"]}, "not available"),
        ({"metrics": ["revenue"], "dimensions": ["password"]}, "unknown dimension"),
        ({"metrics": ["revenue"], "order_by": [{"field": "name; drop", "direction": "asc"}]}, "order_by"),
        ({"metrics": ["revenue"], "filters": [{"field": "month", "value": "2025-01"}]}, "cannot be filtered"),
    ],
)
def test_invalid_plans_raise(plan_kwargs: dict, issue: str) -> None:
    with pytest.raises(PlanError) as e:
        compile_plan(QueryPlan.model_validate(plan_kwargs), 1000)
    assert any(issue in i for i in e.value.issues)


def test_every_metric_dimension_combination_compiles_and_validates() -> None:
    count = 0
    for m in METRICS.values():
        for d in DIMENSIONS.values():
            if m.fact not in d.bindings:
                continue
            sql = compile_plan(QueryPlan(metrics=[m.name], dimensions=[d.name]), 1000).sql
            res = validate_sql(sql, 1000)
            assert res.ok, (m.name, d.name, res.issues)
            count += 1
    assert count > 30
    assert set(FACTS) == {"sales", "web", "deliveries"}


def test_plan_rejects_extra_fields_like_raw_sql() -> None:
    with pytest.raises(ValueError):
        QueryPlan.model_validate({"metrics": ["revenue"], "sql": "DROP TABLE orders"})
