"""SQL validator -- defense in depth for every statement before execution.

Even though our own compiler builds the SQL, we re-parse it with sqlglot (postgres dialect) and
enforce: exactly one SELECT, no DML/DDL/side-effect nodes anywhere in the tree, only allowlisted
tables/columns, only allowlisted functions, and an outer LIMIT <= MAX_ROWS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.semantic.layer import ALLOWED_COLUMNS, ALLOWED_TABLES

# sqlglot logs a warning when it falls back to a generic Command; we reject those anyway.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

# Node types that must never appear anywhere in the parse tree.
_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Drop, exp.Create, exp.Alter, exp.TruncateTable,
    exp.Grant, exp.Revoke, exp.Copy, exp.Command, exp.Set, exp.Into, exp.Lock, exp.Transaction,
    exp.Commit, exp.Use, exp.Kill, exp.Pragma,
)

# Function node classes (by sqlglot class name) that compiled SQL may use.
_ALLOWED_FUNCTIONS = frozenset({
    "Sum", "Count", "Avg", "Min", "Max", "Round", "Nullif", "Coalesce", "Cast", "TimestampTrunc",
    "DateTrunc", "Extract", "Case", "If", "Lower", "Upper", "Abs",
    # boolean connectors are modelled as Func subclasses in sqlglot
    "And", "Or",
})


@dataclass
class ValidationResult:
    ok: bool
    issues: list[str] = field(default_factory=list)


def validate_sql(sql: str, max_rows: int) -> ValidationResult:
    issues: list[str] = []
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except ParseError as e:
        return ValidationResult(False, [f"SQL failed to parse: {str(e).splitlines()[0][:200]}"])
    except Exception as e:  # sqlglot can raise other errors on hostile input
        return ValidationResult(False, [f"SQL failed to parse: {type(e).__name__}"])

    if len(statements) != 1:
        return ValidationResult(False, [f"expected exactly one statement, found {len(statements)}"])
    tree = statements[0]

    if not isinstance(tree, exp.Select):
        issues.append(f"only SELECT statements are allowed (got {type(tree).__name__.upper()})")

    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            issues.append(f"forbidden operation: {type(node).__name__.upper()}")

    # tables: allowlisted base tables or CTE names defined in this query
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        schema = (table.db or "").lower()
        if schema and schema != "public":
            issues.append(f"schema not allowed: {schema}")
        if table.catalog:
            issues.append(f"cross-database reference not allowed: {table.catalog}")
        if name not in ALLOWED_TABLES and name not in cte_names:
            issues.append(f"table not allowed: {name}")

    # columns: allowlisted physical columns or aliases defined in a SELECT list
    aliases = {a.alias.lower() for a in tree.find_all(exp.Alias)}
    for col in tree.find_all(exp.Column):
        if isinstance(col.this, exp.Star):
            issues.append("SELECT * is not allowed; list columns explicitly")
            continue
        cname = col.name.lower()
        if cname not in ALLOWED_COLUMNS and cname not in aliases:
            issues.append(f"column not allowed: {cname}")
    if any(isinstance(s, exp.Star) and not isinstance(s.parent, exp.Column | exp.Count)
           for s in tree.find_all(exp.Star)):
        issues.append("SELECT * is not allowed; list columns explicitly")

    # functions
    for fn in tree.find_all(exp.Func):
        cls = type(fn).__name__
        if isinstance(fn, exp.Anonymous):
            issues.append(f"function not allowed: {fn.name.lower()}")
        elif cls not in _ALLOWED_FUNCTIONS:
            issues.append(f"function not allowed: {fn.sql_name().lower()}")

    # outer LIMIT
    if isinstance(tree, exp.Select):
        limit = tree.args.get("limit")
        if limit is None:
            issues.append("missing LIMIT")
        else:
            expr = limit.expression
            if not (isinstance(expr, exp.Literal) and expr.is_int):
                issues.append("LIMIT must be an integer literal")
            elif int(expr.this) > max_rows:
                issues.append(f"LIMIT {expr.this} exceeds MAX_ROWS ({max_rows})")
        if tree.args.get("offset") is not None:
            issues.append("OFFSET is not allowed")

    # de-duplicate, keep order
    unique = list(dict.fromkeys(issues))
    return ValidationResult(ok=not unique, issues=unique)
