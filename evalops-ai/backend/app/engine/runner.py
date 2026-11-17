"""Run engine: executes every case of a dataset version against one target.

Concurrency via a thread pool (bounded by run concurrency), per-call timeout, retries with
exponential backoff + seeded jitter on transient errors, error capture per case, tracing, and
evaluation. Each worker thread uses its own DB session.
"""

from __future__ import annotations

import datetime as dt
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.logging import get_logger
from app.engine.targets import backoff_seconds, build_executor
from app.evaluators import run_evaluator
from app.evaluators.base import CaseData, TargetOutput
from app.llm.base import ProviderError, TransientProviderError
from app.models import MetricScore, Run, RunResult, TestCase
from app.services.aggregation import ResultRow, ScoreRow, case_passed, summarize
from app.services.tracing import TraceRecorder

log = get_logger(__name__)


def _case_from_row(tc: TestCase) -> CaseData:
    return CaseData(
        external_id=tc.external_id, input=tc.input, expected_output=tc.expected_output,
        reference_contexts=list(tc.reference_contexts or []), expected_citations=list(tc.expected_citations or []),
        tags=list(tc.tags or []), metadata=dict(tc.meta or {}),
    )


def _process_case(
    run_id: uuid.UUID, org_id: uuid.UUID, tc_id: uuid.UUID, case: CaseData, executor: Any,
    snapshot: dict[str, Any], rng_lock: threading.Lock, rng: random.Random,
) -> None:
    params = snapshot["params"]
    timeout_s = float(params["timeout_s"])
    max_retries = int(params["max_retries"])
    tracer = TraceRecorder(f"case {case.external_id}", {"run_id": str(run_id), "external_id": case.external_id,
                                                         "target_kind": snapshot["target"]["kind"]})
    out = TargetOutput()
    error: str | None = None
    attempts = 0
    latency_ms: float | None = None
    with tracer.span("execute_case", "tool", external_id=case.external_id) as root:
        while True:
            attempts += 1
            t0 = time.perf_counter()
            try:
                out = executor.execute(case, tracer, timeout_s)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                error = None
                break
            except TransientProviderError as exc:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                error = f"transient: {exc}"
                if attempts > max_retries:
                    break
                with rng_lock:
                    jitter = rng.uniform(0, 0.1)
                time.sleep(backoff_seconds(attempts - 1, base=float(params.get("backoff_base_s", 0.25))) + jitter)
            except ProviderError as exc:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                error = str(exc)
                break
            except Exception as exc:  # unexpected executor bug: capture, do not crash the run
                latency_ms = (time.perf_counter() - t0) * 1000.0
                error = f"{type(exc).__name__}: {exc}"
                break
        root.set(attempts=attempts, error=error)
    out.latency_ms = latency_ms
    out.error = error

    outcomes = []
    if error is None and snapshot["evaluators"]:
        with tracer.span("evaluate", "eval", evaluator_count=len(snapshot["evaluators"])):
            for ev in snapshot["evaluators"]:
                with tracer.span(f"eval:{ev['name']}", "eval", evaluator_type=ev["type"]) as sp:
                    o = run_evaluator(ev["type"], case, out, dict(ev.get("params") or {}), ev.get("threshold"))
                    sp.set(status=o.status, value=o.value, passed=o.passed)
                outcomes.append((ev, o))
    tracer.finish("error" if error else "ok")

    score_rows = [ScoreRow(case.external_id, ev["name"], o.status, o.value, o.passed, o.is_estimate,
                           bool(ev.get("gating", True))) for ev, o in outcomes]
    passed = case_passed(score_rows, error)
    with session_scope() as s:
        trace_id = tracer.persist(s, org_id, run_id)
        rr = RunResult(
            org_id=org_id, run_id=run_id, test_case_id=tc_id, external_id=case.external_id,
            output_text=out.text if error is None else None,
            output_json=out.to_json() if error is None else None,
            latency_ms=latency_ms, input_tokens=out.input_tokens, output_tokens=out.output_tokens,
            tokens_estimated=out.tokens_estimated, cost_usd=out.cost_usd, error=error[:2000] if error else None,
            attempts=attempts, passed=passed, trace_id=trace_id,
        )
        s.add(rr)
        s.flush()
        for ev, o in outcomes:
            s.add(MetricScore(
                org_id=org_id, run_id=run_id, run_result_id=rr.id, evaluator_config_id=ev.get("id"),
                metric=ev["name"], status=o.status, value=o.value, passed=o.passed,
                is_estimate=o.is_estimate, gating=bool(ev.get("gating", True)), explanation=o.explanation,
                details=o.details,
            ))
        s.execute(update(Run).where(Run.id == run_id).values(progress_done=Run.progress_done + 1))


def recompute_summary(session: Session, run: Run) -> dict[str, Any]:
    results = session.scalars(select(RunResult).where(RunResult.run_id == run.id)).all()
    by_id = {r.id: r.external_id for r in results}
    scores = session.scalars(select(MetricScore).where(MetricScore.run_id == run.id)).all()
    wall = None
    if run.started_at and run.finished_at:
        wall = (run.finished_at - run.started_at).total_seconds()
    return summarize(
        [ResultRow(r.external_id, r.latency_ms, r.input_tokens, r.output_tokens, r.cost_usd, r.error, r.passed)
         for r in results],
        [ScoreRow(by_id.get(sc.run_result_id, ""), sc.metric, sc.status, sc.value, sc.passed, sc.is_estimate,
                  sc.gating) for sc in scores],
        wall,
    )


def execute_run(run_id: uuid.UUID) -> str:
    """Execute a run that has already been claimed (status=running). Returns the final status."""
    with session_scope() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise ValueError(f"run {run_id} not found")
        snapshot = dict(run.config_snapshot)
        org_id = run.org_id
        rows = s.scalars(
            select(TestCase).where(TestCase.dataset_version_id == run.dataset_version_id).order_by(TestCase.position)
        ).all()
        cases = [(tc.id, _case_from_row(tc)) for tc in rows]
        run.progress_total = len(cases)
        if run.started_at is None:
            run.started_at = dt.datetime.now(dt.UTC)
    log.info("run_started", run_id=str(run_id), cases=len(cases), target_kind=snapshot["target"]["kind"])
    try:
        executor = build_executor(snapshot)
    except Exception as exc:
        _finish(run_id, "failed", f"could not build target executor: {exc}")
        return "failed"
    rng = random.Random(int(snapshot["params"].get("seed", 0)))
    rng_lock = threading.Lock()
    try:
        with ThreadPoolExecutor(max_workers=max(1, int(snapshot["params"]["concurrency"]))) as pool:
            futures = [pool.submit(_process_case, run_id, org_id, tc_id, case, executor, snapshot, rng_lock, rng)
                       for tc_id, case in cases]
            for f in futures:
                f.result()
    except Exception as exc:
        log.error("run_failed", run_id=str(run_id), error=str(exc)[:300])
        _finish(run_id, "failed", f"{type(exc).__name__}: {exc}"[:2000])
        return "failed"
    finally:
        executor.close()
    _finish(run_id, "completed", None)
    log.info("run_completed", run_id=str(run_id))
    return "completed"


def _finish(run_id: uuid.UUID, status: str, error: str | None) -> None:
    with session_scope() as s:
        run = s.get(Run, run_id)
        assert run is not None
        run.status = status
        run.error = error
        run.finished_at = dt.datetime.now(dt.UTC)
        s.flush()
        run.summary = recompute_summary(s, run)
