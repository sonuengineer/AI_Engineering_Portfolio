"""Run-level metric aggregation. Pure functions (unit tested without a DB)."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass
class ResultRow:
    external_id: str
    latency_ms: float | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    error: str | None
    passed: bool | None


@dataclass
class ScoreRow:
    external_id: str
    metric: str
    status: str
    value: float | None
    passed: bool | None
    is_estimate: bool
    gating: bool = True


def percentile(values: Sequence[float], p: float) -> float | None:
    """Linear-interpolated percentile (same as numpy's default 'linear' method)."""
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    k = (len(xs) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(xs[int(k)])
    return float(xs[lo] + (xs[hi] - xs[lo]) * (k - lo))


def case_passed(scores: Iterable[ScoreRow], error: str | None) -> bool | None:
    """A case passes if it has no error and every scored gating, non-estimate metric passed.

    Returns None when no gating metric produced a score (nothing to judge on).
    Judge/estimate metrics never decide pass/fail (see ADR 0003).
    """
    if error:
        return False
    gating = [s for s in scores if s.gating and not s.is_estimate and s.status == "scored"]
    if not gating:
        return None
    return all(bool(s.passed) for s in gating)


def summarize(results: Sequence[ResultRow], scores: Sequence[ScoreRow], wall_seconds: float | None) -> dict[str, Any]:
    n = len(results)
    errors = sum(1 for r in results if r.error)
    latencies = [r.latency_ms for r in results if r.latency_ms is not None and not r.error]
    judged = [r for r in results if r.passed is not None]
    metrics: dict[str, dict[str, Any]] = {}
    for s in scores:
        m = metrics.setdefault(
            s.metric,
            {"scored": 0, "skipped": 0, "errors": 0, "passed": 0, "values": [], "is_estimate": s.is_estimate,
             "gating": s.gating},
        )
        if s.status == "scored":
            m["scored"] += 1
            if s.passed:
                m["passed"] += 1
            if s.value is not None:
                m["values"].append(s.value)
        elif s.status == "skipped":
            m["skipped"] += 1
        else:
            m["errors"] += 1
    metric_summary: dict[str, dict[str, Any]] = {}
    for name, m in sorted(metrics.items()):
        vals: list[float] = m.pop("values")
        metric_summary[name] = {
            **m,
            "pass_rate": (m["passed"] / m["scored"]) if m["scored"] else None,
            "mean": (sum(vals) / len(vals)) if vals else None,
        }
    total_in = sum(r.input_tokens for r in results)
    total_out = sum(r.output_tokens for r in results)
    return {
        "case_count": n,
        "error_count": errors,
        "error_rate": errors / n if n else 0.0,
        "cases_judged": len(judged),
        "cases_passed": sum(1 for r in judged if r.passed),
        "overall_pass_rate": (sum(1 for r in judged if r.passed) / len(judged)) if judged else None,
        "latency_ms": {
            "mean": (sum(latencies) / len(latencies)) if latencies else None,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "max": max(latencies) if latencies else None,
        },
        "tokens": {"input": total_in, "output": total_out, "total": total_in + total_out},
        "cost_usd": round(sum(r.cost_usd for r in results), 8),
        "wall_seconds": wall_seconds,
        "throughput_cases_per_sec": (n / wall_seconds) if wall_seconds and wall_seconds > 0 else None,
        "metrics": metric_summary,
    }
