"""QueryPlan -> SQL, built only from semantic-layer definitions.

Planner output never contributes raw SQL: identifiers come from the registry, user values become
properly escaped string/number literals (via sqlglot), and LIMIT is clamped to MAX_ROWS.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp

from app.schemas.plan import Filter, QueryPlan
from app.semantic.layer import DIMENSIONS, FACTS, METRICS

_OPS = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


class PlanError(ValueError):
    """The plan references unknown or incompatible semantic-layer items."""

    def __init__(self, issues: list[str]) -> None:
        super().__init__("; ".join(issues))
        self.issues = issues


@dataclass
class CompiledQuery:
    sql: str
    fact: str
    columns: list[str]


def _lit(value: str | float) -> str:
    if isinstance(value, bool):
        raise PlanError(["boolean filter values are not supported"])
    if isinstance(value, int | float):
        return exp.Literal.number(value).sql(dialect="postgres")
    return exp.Literal.string(str(value)).sql(dialect="postgres")


def check_plan(plan: QueryPlan) -> list[str]:
    """Semantic validation of a plan. Returns issues (empty = OK)."""
    issues: list[str] = []
    unknown_metrics = [m for m in plan.metrics if m not in METRICS]
    if unknown_metrics:
        issues.append(f"unknown metric(s): {', '.join(unknown_metrics)}")
        return issues
    facts = {METRICS[m].fact for m in plan.metrics}
    if len(facts) > 1:
        issues.append(f"metrics come from different facts ({', '.join(sorted(facts))}) and cannot be combined")
        return issues
    fact = facts.pop()
    for d in plan.dimensions:
        if d not in DIMENSIONS:
            issues.append(f"unknown dimension: {d}")
        elif fact not in DIMENSIONS[d].bindings:
            issues.append(f"dimension '{d}' is not available for metric(s) {', '.join(plan.metrics)}")
    if len(set(plan.dimensions)) != len(plan.dimensions):
        issues.append("duplicate dimensions")
    for f in plan.filters:
        if f.kind == "dimension":
            if f.field not in DIMENSIONS:
                issues.append(f"unknown filter dimension: {f.field}")
            elif not DIMENSIONS[f.field].filterable:
                issues.append(f"dimension '{f.field}' cannot be filtered directly; use time_range")
            elif fact not in DIMENSIONS[f.field].bindings:
                issues.append(f"filter on '{f.field}' is not available for metric(s) {', '.join(plan.metrics)}")
            elif f.op in ("gt", "gte", "lt", "lte"):
                issues.append(f"numeric comparison is not supported on dimension '{f.field}'")
        else:
            if f.field not in METRICS:
                issues.append(f"unknown filter metric: {f.field}")
            elif METRICS[f.field].fact != fact:
                issues.append(f"metric filter '{f.field}' is from a different fact")
            elif f.op == "in" or isinstance(f.value, str | list):
                issues.append(f"metric filter on '{f.field}' needs a numeric comparison")
    output = set(plan.metrics) | set(plan.dimensions)
    for o in plan.order_by:
        if o.field not in output:
            issues.append(f"order_by field '{o.field}' is not a selected metric or dimension")
    return issues


def _filter_sql(f: Filter, fact: str) -> str:
    target = DIMENSIONS[f.field].bindings[fact].sql if f.kind == "dimension" else METRICS[f.field].sql
    if f.op == "in":
        assert isinstance(f.value, list)
        return f"{target} IN ({', '.join(_lit(v) for v in f.value)})"
    assert not isinstance(f.value, list)
    return f"{target} {_OPS[f.op]} {_lit(f.value)}"


def compile_plan(plan: QueryPlan, max_rows: int) -> CompiledQuery:
    issues = check_plan(plan)
    if issues:
        raise PlanError(issues)
    fact_name = METRICS[plan.metrics[0]].fact
    fact = FACTS[fact_name]

    # collect joins needed by dimensions and dimension filters, honoring join dependencies
    needed: list[str] = []

    def _need(alias: str) -> None:
        for req in fact.joins[alias].requires:
            _need(req)
        if alias not in needed:
            needed.append(alias)

    dim_filters = [f for f in plan.filters if f.kind == "dimension"]
    for d in list(plan.dimensions) + [f.field for f in dim_filters]:
        for alias in DIMENSIONS[d].bindings[fact_name].joins:
            _need(alias)

    select_parts = [f"{DIMENSIONS[d].bindings[fact_name].sql} AS {d}" for d in plan.dimensions]
    select_parts += [f"{METRICS[m].sql} AS {m}" for m in plan.metrics]

    where = list(fact.base_where)
    if plan.time_range is not None:
        where.append(f"{fact.time_column} >= CAST({_lit(plan.time_range.start.isoformat())} AS DATE)")
        where.append(f"{fact.time_column} < CAST({_lit(plan.time_range.end.isoformat())} AS DATE)")
    where += [_filter_sql(f, fact_name) for f in dim_filters]
    having = [_filter_sql(f, fact_name) for f in plan.filters if f.kind == "metric"]

    lines = ["SELECT " + ", ".join(select_parts), f"FROM {fact.from_sql}"]
    lines += [fact.joins[a].sql for a in needed]
    if where:
        lines.append("WHERE " + " AND ".join(where))
    if plan.dimensions:
        lines.append("GROUP BY " + ", ".join(str(i + 1) for i in range(len(plan.dimensions))))
    if having:
        lines.append("HAVING " + " AND ".join(having))
    order = plan.order_by
    if order:
        parts = [f"{o.field} {o.direction.upper()}" for o in order]
        # deterministic tie-break on the first dimension so ties never reorder between runs
        if plan.dimensions and plan.dimensions[0] not in {o.field for o in order}:
            parts.append(f"{plan.dimensions[0]} ASC")
        lines.append("ORDER BY " + ", ".join(parts))
    elif plan.dimensions:
        lines.append("ORDER BY 1")
    lines.append(f"LIMIT {min(plan.limit, max_rows)}")
    return CompiledQuery(sql="\n".join(lines), fact=fact_name, columns=list(plan.dimensions) + list(plan.metrics))
