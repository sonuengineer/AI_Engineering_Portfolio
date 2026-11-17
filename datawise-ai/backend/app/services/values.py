"""Known dimension values (for filter matching), loaded once from the analytics DB via the reader."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import psycopg

from app.semantic.layer import VALUE_QUERIES


@dataclass
class ValueIndex:
    values: dict[str, list[str]] = field(default_factory=dict)

    def aliases(self) -> dict[str, list[tuple[str, str]]]:
        """lower-cased phrase -> [(dimension, canonical value)]. A phrase can map to several dimensions."""
        out: dict[str, list[tuple[str, str]]] = {}

        def add(phrase: str, dim: str, value: str) -> None:
            phrase = phrase.lower().strip()
            if len(phrase) < 3:
                return
            entry = out.setdefault(phrase, [])
            if (dim, value) not in entry:
                entry.append((dim, value))

        supplier_first: dict[str, list[str]] = {}
        for dim, vals in self.values.items():
            for v in vals:
                add(v, dim, v)
                if "&" in v:
                    add(v.replace("&", "and"), dim, v)
                if "_" in v:
                    add(v.replace("_", " "), dim, v)
                if dim in ("customer_segment",):
                    add(v + "s" if not v.endswith("s") else v, dim, v)
                    if v.lower() == "small business":
                        add("small businesses", dim, v)
                if dim == "supplier":
                    supplier_first.setdefault(v.split()[0].lower(), []).append(v)
                if dim == "channel" and v == "store":
                    add("in-store", dim, v)
                    add("in store", dim, v)
                if dim == "traffic_source" and v == "email":
                    add("e-mail", dim, v)
        for first, names in supplier_first.items():
            if len(names) == 1 and len(first) >= 4:
                add(first, "supplier", names[0])
        return out


_lock = threading.Lock()
_cached: ValueIndex | None = None


def load_value_index(dsn: str) -> ValueIndex:
    global _cached
    with _lock:
        if _cached is not None:
            return _cached
        idx = ValueIndex()
        with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cur:
            for dim, q in VALUE_QUERIES.items():
                cur.execute(q)  # static registry SQL
                idx.values[dim] = sorted(str(r[0]) for r in cur.fetchall())
            conn.rollback()
        _cached = idx
        return idx


def reset_value_index_cache() -> None:
    global _cached
    with _lock:
        _cached = None
