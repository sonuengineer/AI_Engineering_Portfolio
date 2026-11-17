"""Schema discovery: information_schema (via the read-only role) for allowlisted tables, merged with
semantic-layer descriptions."""

from __future__ import annotations

from typing import Any

import psycopg

from app.semantic.layer import (
    ALLOWED_TABLES,
    DATA_END,
    DATA_START,
    DIMENSIONS,
    FACTS,
    METRICS,
    TABLE_DESCRIPTIONS,
)

_cache: dict[str, Any] | None = None


def build_catalog(dsn: str) -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    tables: dict[str, list[dict[str, str]]] = {t: [] for t in ALLOWED_TABLES}
    with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = ANY(%s) ORDER BY table_name, ordinal_position",
            (list(ALLOWED_TABLES),),
        )
        for t, c, dt in cur.fetchall():
            if c in ALLOWED_TABLES[t]:
                tables[t].append({"name": c, "type": dt})
        conn.rollback()
    _cache = {
        "data_range": {"start": DATA_START, "end": DATA_END},
        "tables": [{"name": t, "description": TABLE_DESCRIPTIONS.get(t, ""), "columns": cols}
                   for t, cols in tables.items()],
        "metrics": [{"name": m.name, "label": m.label, "description": m.description, "fact": m.fact,
                     "format": m.fmt, "synonyms": list(m.synonyms)} for m in METRICS.values()],
        "dimensions": [{"name": d.name, "label": d.label, "description": d.description,
                        "synonyms": list(d.synonyms), "facts": list(d.bindings), "is_time": d.is_time}
                       for d in DIMENSIONS.values()],
        "facts": [{"name": f.name, "description": f.description, "from": f.from_sql,
                   "joins": [j.sql for j in f.joins.values()], "time_column": f.time_column}
                  for f in FACTS.values()],
    }
    return _cache
