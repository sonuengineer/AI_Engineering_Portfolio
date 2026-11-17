"""Run report exports: JSON, Markdown, CSV."""

from __future__ import annotations

import csv
import io
from typing import Any


def _fmt(v: Any, digits: int = 3) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def build_json(run: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {"report_version": 1, "run": run, "cases": cases}


def build_markdown(run: dict[str, Any], cases: list[dict[str, Any]]) -> str:
    s = run.get("summary") or {}
    lat = s.get("latency_ms") or {}
    lines = [
        f"# EvalOps run report: {run['label']}",
        "",
        f"- Run id: `{run['id']}`",
        f"- Status: {run['status']}",
        f"- Target: {run.get('target_name')} ({run.get('target_kind')})",
        f"- Provider / model: {run.get('provider')} / {run.get('model') or '-'}",
        f"- Dataset hash: `{run['dataset_hash']}`",
        f"- Seed: {run['seed']}  Git SHA: {run.get('git_sha') or 'n/a'}",
        f"- Started: {run.get('started_at')}  Finished: {run.get('finished_at')}",
        "",
    ]
    if run.get("is_deterministic_provider"):
        lines += ["> Note: this run used a deterministic local/scripted provider, not a real LLM. "
                  "Scores describe that adapter/script, not model quality.", ""]
    lines += [
        "## Summary",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Cases | {s.get('case_count', 0)} |",
        f"| Overall pass rate | {_fmt(s.get('overall_pass_rate'))} |",
        f"| Error rate | {_fmt(s.get('error_rate'))} |",
        f"| Latency mean / p50 / p95 (ms) | {_fmt(lat.get('mean'), 1)} / {_fmt(lat.get('p50'), 1)} / "
        f"{_fmt(lat.get('p95'), 1)} |",
        f"| Tokens (in / out) | {(s.get('tokens') or {}).get('input', 0)} / {(s.get('tokens') or {}).get('output', 0)} |",
        f"| Estimated cost (USD) | {_fmt(s.get('cost_usd'), 6)} |",
        f"| Throughput (cases/s) | {_fmt(s.get('throughput_cases_per_sec'), 2)} |",
        "",
        "## Metrics",
        "",
        "| Metric | Type | Scored | Skipped | Pass rate | Mean |",
        "|---|---|---|---|---|---|",
    ]
    for name, m in (s.get("metrics") or {}).items():
        kind = "estimate (judge)" if m.get("is_estimate") else "deterministic"
        lines.append(f"| {name} | {kind} | {m['scored']} | {m['skipped']} | {_fmt(m.get('pass_rate'))} | "
                     f"{_fmt(m.get('mean'))} |")
    failing = [c for c in cases if c.get("passed") is False]
    lines += ["", f"## Failing cases ({len(failing)})", ""]
    for c in failing[:100]:
        why = c.get("error") or "; ".join(
            f"{sc['metric']}: {sc['explanation']}" for sc in c["scores"] if sc["status"] == "scored" and not sc["passed"]
        )
        lines.append(f"- `{c['external_id']}` -- {why[:300]}")
    lines.append("")
    return "\n".join(lines)


def build_csv(cases: list[dict[str, Any]]) -> str:
    metrics = sorted({sc["metric"] for c in cases for sc in c["scores"]})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["external_id", "passed", "error", "latency_ms", "input_tokens", "output_tokens", "cost_usd",
                "output_text", *metrics])
    for c in cases:
        by = {sc["metric"]: sc for sc in c["scores"]}
        w.writerow([
            c["external_id"], c["passed"], c["error"] or "", c["latency_ms"], c["input_tokens"], c["output_tokens"],
            c["cost_usd"], (c["output_text"] or "")[:1000],
            *[(by[m]["value"] if m in by and by[m]["status"] == "scored" else by[m]["status"] if m in by else "")
              for m in metrics],
        ])
    return buf.getvalue()
