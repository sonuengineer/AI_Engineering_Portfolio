"""Baseline vs candidate comparison and regression detection. Pure functions."""

from __future__ import annotations

from typing import Any


def compare_summaries(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    tolerance: float = 0.02,
    metric_tolerances: dict[str, float] | None = None,
    latency_tolerance_pct: float = 0.25,
) -> dict[str, Any]:
    """Per-metric pass-rate deltas. Regression if candidate drops by more than tolerance (absolute)."""
    metric_tolerances = metric_tolerances or {}
    rows: list[dict[str, Any]] = []
    b_metrics: dict[str, Any] = baseline.get("metrics", {})
    c_metrics: dict[str, Any] = candidate.get("metrics", {})
    for name in sorted(set(b_metrics) | set(c_metrics)):
        b = b_metrics.get(name, {})
        c = c_metrics.get(name, {})
        bp, cp = b.get("pass_rate"), c.get("pass_rate")
        tol = metric_tolerances.get(name, tolerance)
        delta = (cp - bp) if (bp is not None and cp is not None) else None
        rows.append({
            "metric": name,
            "baseline_pass_rate": bp,
            "candidate_pass_rate": cp,
            "baseline_mean": b.get("mean"),
            "candidate_mean": c.get("mean"),
            "delta": delta,
            "tolerance": tol,
            "is_estimate": bool(b.get("is_estimate") or c.get("is_estimate")),
            "regression": delta is not None and delta < -tol,
        })
    ops: list[dict[str, Any]] = []
    bo, co = baseline.get("overall_pass_rate"), candidate.get("overall_pass_rate")
    ops.append({
        "name": "overall_pass_rate", "baseline": bo, "candidate": co,
        "delta": (co - bo) if (bo is not None and co is not None) else None,
        "regression": bo is not None and co is not None and (co - bo) < -tolerance,
    })
    be, ce = baseline.get("error_rate", 0.0), candidate.get("error_rate", 0.0)
    ops.append({"name": "error_rate", "baseline": be, "candidate": ce, "delta": ce - be,
                "regression": (ce - be) > tolerance})
    bl = (baseline.get("latency_ms") or {}).get("p95")
    cl = (candidate.get("latency_ms") or {}).get("p95")
    lat_reg = bool(bl and cl and cl > bl * (1 + latency_tolerance_pct) and (cl - bl) > 5.0)
    ops.append({"name": "latency_p95_ms", "baseline": bl, "candidate": cl,
                "delta": (cl - bl) if (bl is not None and cl is not None) else None, "regression": lat_reg})
    bc, cc = baseline.get("cost_usd", 0.0), candidate.get("cost_usd", 0.0)
    ops.append({"name": "cost_usd", "baseline": bc, "candidate": cc, "delta": cc - bc, "regression": False})
    # Judge metrics (estimates) are reported but never count as a regression by default.
    det_regressions = [r["metric"] for r in rows if r["regression"] and not r["is_estimate"]]
    op_regressions = [o["name"] for o in ops if o["regression"]]
    return {
        "metrics": rows,
        "operational": ops,
        "regressions": det_regressions + op_regressions,
        "has_regression": bool(det_regressions or op_regressions),
    }


def diff_cases(
    baseline_cases: dict[str, bool | None], candidate_cases: dict[str, bool | None]
) -> dict[str, list[str]]:
    """Case-level diff keyed by external_id: newly failing / newly passing / missing."""
    newly_failing = sorted(k for k, v in candidate_cases.items() if v is False and baseline_cases.get(k) is True)
    newly_passing = sorted(k for k, v in candidate_cases.items() if v is True and baseline_cases.get(k) is False)
    still_failing = sorted(k for k, v in candidate_cases.items() if v is False and baseline_cases.get(k) is False)
    only_baseline = sorted(set(baseline_cases) - set(candidate_cases))
    only_candidate = sorted(set(candidate_cases) - set(baseline_cases))
    return {
        "newly_failing": newly_failing,
        "newly_passing": newly_passing,
        "still_failing": still_failing,
        "only_in_baseline": only_baseline,
        "only_in_candidate": only_candidate,
    }
