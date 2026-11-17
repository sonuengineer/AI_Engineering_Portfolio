"""Executes validated SQL against the analytics DB as the read-only role.

Layers of protection here (in addition to the validator):
- connects as datawise_reader (GRANT SELECT only, default_transaction_read_only=on)
- SET TRANSACTION READ ONLY + SET LOCAL statement_timeout inside every transaction
- fetchmany(max_rows) so a missing/oversized LIMIT still cannot flood memory
- the transaction is always rolled back (nothing to commit)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import errors as pg_errors


class ExecutionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ExecutionResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, dt.datetime | dt.date):
        return v.isoformat()
    return v


def execute_readonly(sql: str, dsn: str, max_rows: int, timeout_ms: int) -> ExecutionResult:
    try:
        with psycopg.connect(dsn, autocommit=False, connect_timeout=5) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
                    cur.execute(sql)  # validated SQL, no params
                    columns = [d.name for d in (cur.description or [])]
                    fetched = cur.fetchmany(max_rows + 1)
            finally:
                conn.rollback()
    except pg_errors.QueryCanceled as e:
        raise ExecutionError("query_timeout", f"Query exceeded the {timeout_ms} ms statement timeout") from e
    except (pg_errors.InsufficientPrivilege, pg_errors.ReadOnlySqlTransaction) as e:
        raise ExecutionError("read_only_violation", "Write attempt blocked by the read-only role") from e
    except psycopg.OperationalError as e:
        raise ExecutionError("analytics_unavailable", "Analytics database is unreachable") from e
    except psycopg.Error as e:
        raise ExecutionError("execution_error", f"Query failed: {type(e).__name__}") from e
    truncated = len(fetched) > max_rows
    rows = [[_jsonable(v) for v in r] for r in fetched[:max_rows]]
    return ExecutionResult(columns=columns, rows=rows, truncated=truncated)
