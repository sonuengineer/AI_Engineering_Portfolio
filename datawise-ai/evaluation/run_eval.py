"""Runs evaluation/datawise_eval.jsonl against a running DATAWISE API and reports accuracy.

Black-box: only uses the public HTTP contract (POST /api/v1/auth/login, POST /api/v1/questions/ask).

    python evaluation/run_eval.py --base-url http://localhost:8102 \
        --email demo@acme.example --password "$DEMO_USER_PASSWORD"

Writes evaluation/results/latest.json with per-case outcomes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

HERE = Path(__file__).resolve().parent


def _norm(dim: str, v: Any) -> str:
    return str(v)


def check_case(case: dict[str, Any], body: dict[str, Any]) -> tuple[bool, str]:
    if body.get("status") != case["expected_status"]:
        return False, f"status {body.get('status')} != {case['expected_status']}"
    chk = case.get("check")
    if not chk:
        return True, "status matched"
    cols: list[str] = body.get("columns", [])
    rows: list[list[Any]] = body.get("rows", [])
    t = chk["type"]
    if t == "row_count":
        ok = body.get("row_count") == chk["value"]
        return ok, f"row_count {body.get('row_count')} vs {chk['value']}"
    if chk["column"] not in cols:
        return False, f"column {chk['column']} missing from {cols}"
    ci = cols.index(chk["column"])
    tol = float(chk.get("tolerance", 0.01))
    if t == "scalar":
        if not rows:
            return False, "no rows"
        got = float(rows[0][ci])
        return abs(got - chk["value"]) <= tol, f"{got} vs {chk['value']}"
    if chk["dimension"] not in cols:
        return False, f"dimension {chk['dimension']} missing from {cols}"
    di = cols.index(chk["dimension"])
    if t == "top":
        if not rows:
            return False, "no rows"
        name, got = str(rows[0][di]), float(rows[0][ci])
        ok = name == chk["name"] and abs(got - chk["value"]) <= tol
        return ok, f"top {name}={got} vs {chk['name']}={chk['value']}"
    if t == "series":
        got_map = {_norm(chk["dimension"], r[di]): float(r[ci]) for r in rows}
        exp_map: dict[str, float] = chk["values"]
        if set(got_map) != set(exp_map):
            return False, f"keys differ: missing {sorted(set(exp_map) - set(got_map))[:3]}, " \
                          f"extra {sorted(set(got_map) - set(exp_map))[:3]}"
        bad = [k for k in exp_map if abs(got_map[k] - exp_map[k]) > tol]
        return not bad, f"{len(exp_map) - len(bad)}/{len(exp_map)} values match"
    return False, f"unknown check type {t}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default=os.environ.get("DATAWISE_BASE_URL", "http://localhost:8102"))
    p.add_argument("--email", default=os.environ.get("DATAWISE_EVAL_EMAIL", "demo@acme.example"))
    p.add_argument("--password", default=os.environ.get("DEMO_USER_PASSWORD", "change-me-demo-password"))
    p.add_argument("--dataset", default=str(HERE / "datawise_eval.jsonl"))
    p.add_argument("--min-accuracy", type=float, default=0.0, help="exit 1 if overall accuracy is below this")
    args = p.parse_args()

    cases = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines() if line.strip()]
    results: list[dict[str, Any]] = []
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        r = client.post("/api/v1/auth/login", json={"email": args.email, "password": args.password})
        r.raise_for_status()
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        provider = None
        for case in cases:
            t0 = time.perf_counter()
            for attempt in range(5):
                resp = client.post("/api/v1/questions/ask", json={"question": case["question"]}, headers=headers)
                if resp.status_code != 429:
                    break
                time.sleep(2 * (attempt + 1))  # respect the per-user rate limit
            wall_ms = int((time.perf_counter() - t0) * 1000)
            if resp.status_code != 200:
                ok, detail, body = False, f"HTTP {resp.status_code}: {resp.text[:200]}", {}
            else:
                body = resp.json()
                provider = body.get("provider")
                ok, detail = check_case(case, body)
            results.append({"id": case["id"], "category": case["category"], "question": case["question"],
                            "expected_status": case["expected_status"], "status": body.get("status"),
                            "passed": ok, "detail": detail, "latency_ms": body.get("latency_ms"),
                            "wall_ms": wall_ms, "sql": body.get("sql")})

    cats: dict[str, list[bool]] = {}
    for res in results:
        cats.setdefault(res["category"], []).append(res["passed"])
    total = sum(r["passed"] for r in results)
    accuracy = total / len(results) if results else 0.0
    latencies = sorted(r["latency_ms"] for r in results if r["latency_ms"] is not None)
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else 0

    print(f"DATAWISE eval -- provider={provider} cases={len(results)}")
    for cat, vals in cats.items():
        print(f"  {cat:<20} {sum(vals):>3}/{len(vals):<3} ({sum(vals) / len(vals) * 100:.1f}%)")
    print(f"  {'OVERALL':<20} {total:>3}/{len(results):<3} ({accuracy * 100:.1f}%)")
    print(f"  server latency p50={p50} ms p95={p95} ms")
    for res in results:
        if not res["passed"]:
            print(f"  FAIL {res['id']}: {res['detail']}")

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    summary = {"provider": provider, "cases": len(results), "passed": total, "accuracy": round(accuracy, 4),
               "by_category": {c: {"passed": sum(v), "total": len(v)} for c, v in cats.items()},
               "latency_ms": {"p50": p50, "p95": p95}, "results": results}
    (out_dir / "latest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if accuracy >= args.min_accuracy else 1


if __name__ == "__main__":
    sys.exit(main())
