"""Measure in-process latency of chat Q&A and the investigation workflow.

Usage: python -m scripts.benchmark_latency [--n 30] [--out ../docs/benchmarks/latency.json]
Runs against DATABASE_URL with the configured providers. Results describe THIS machine only.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_factory
from app.models import User, WorkflowRun
from app.services.chat import ask
from app.services.workflows import execute_run, start_run

QUESTIONS = [
    "What discount can an account manager approve?",
    "Why did Harbor Marine Systems reject batch MC-5521?",
    "When did the Ironclad contract expire?",
    "Which customer had late hydraulic deliveries?",
    "What are the standard payment terms?",
    "What is the capital of France?",
]


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return round(s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))], 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default="../docs/benchmarks/latency.json")
    a = ap.parse_args()
    s = get_settings()
    with session_factory()() as db:
        user = db.scalar(select(User).where(User.email == "manager@acme.example"))
        assert user is not None, "seed the database first"
        lat: list[float] = []
        for i in range(a.n):
            t0 = time.perf_counter()
            ask(db, user, QUESTIONS[i % len(QUESTIONS)], None)
            lat.append((time.perf_counter() - t0) * 1000)
        wf: list[float] = []
        for _ in range(a.runs):
            run = start_run(db, user, "Investigate declining purchases among our top ten customers")
            t0 = time.perf_counter()
            execute_run(run.id)
            wf.append((time.perf_counter() - t0) * 1000)
            db.expire_all()
            assert db.get(WorkflowRun, run.id).status == "awaiting_approval"  # type: ignore[union-attr]
    result = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "machine": f"{platform.system()} {platform.release()} / Python {platform.python_version()}",
        "llm_provider": s.llm_provider,
        "embedding_provider": s.embedding_provider,
        "chat_ask_ms": {"n": a.n, "p50": pct(lat, 50), "p95": pct(lat, 95), "mean": round(statistics.mean(lat), 1)},
        "investigation_ms": {"n": a.runs, "p50": pct(wf, 50), "max": round(max(wf), 1)},
        "note": "In-process service calls (no HTTP), local Postgres in Docker, warm caches. "
        "With a remote LLM provider, model latency dominates and these numbers do not apply.",
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
