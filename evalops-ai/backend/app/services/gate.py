"""CI eval gate: threshold checks on a run plus optional regression check vs a baseline."""

from __future__ import annotations

from typing import Any


def check_thresholds(summary: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    """Return a list of human-readable failures (empty == pass)."""
    failures: list[str] = []
    metrics = summary.get("metrics") or {}
    for name, min_rate in (thresholds.get("min_pass_rate") or {}).items():
        m = metrics.get(name)
        if m is None or m.get("pass_rate") is None:
            failures.append(f"metric '{name}' has no scored results")
        elif m["pass_rate"] < float(min_rate):
            failures.append(f"{name} pass_rate {m['pass_rate']:.3f} < required {float(min_rate):.3f}")
    if "min_overall_pass_rate" in thresholds:
        v = summary.get("overall_pass_rate")
        if v is None or v < float(thresholds["min_overall_pass_rate"]):
            failures.append(f"overall_pass_rate {v} < required {thresholds['min_overall_pass_rate']}")
    if "max_error_rate" in thresholds and summary.get("error_rate", 0.0) > float(thresholds["max_error_rate"]):
        failures.append(f"error_rate {summary['error_rate']:.3f} > allowed {thresholds['max_error_rate']}")
    p95 = (summary.get("latency_ms") or {}).get("p95")
    if "max_p95_latency_ms" in thresholds and p95 is not None and p95 > float(thresholds["max_p95_latency_ms"]):
        failures.append(f"p95 latency {p95:.1f} ms > allowed {thresholds['max_p95_latency_ms']} ms")
    if "max_cost_usd" in thresholds and summary.get("cost_usd", 0.0) > float(thresholds["max_cost_usd"]):
        failures.append(f"cost {summary['cost_usd']:.6f} USD > allowed {thresholds['max_cost_usd']}")
    if "min_cases" in thresholds and summary.get("case_count", 0) < int(thresholds["min_cases"]):
        failures.append(f"case_count {summary.get('case_count', 0)} < required {thresholds['min_cases']}")
    return failures


def regression_failures(comparison: dict[str, Any]) -> list[str]:
    out = []
    for r in comparison["metrics"]:
        if r["regression"] and not r["is_estimate"]:
            out.append(f"regression in {r['metric']}: {r['baseline_pass_rate']:.3f} -> {r['candidate_pass_rate']:.3f} "
                       f"(tolerance {r['tolerance']})")
    for o in comparison["operational"]:
        if o["regression"]:
            out.append(f"regression in {o['name']}: {o['baseline']} -> {o['candidate']}")
    return out
