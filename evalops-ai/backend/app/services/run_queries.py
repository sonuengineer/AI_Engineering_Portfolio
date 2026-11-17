"""DB read helpers for runs (org-scoped)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models import MetricScore, Run, RunResult, Target, TestCase


def get_run(session: Session, org_id: uuid.UUID, run_id: uuid.UUID) -> Run:
    run = session.get(Run, run_id)
    if run is None or run.org_id != org_id:
        raise NotFound("run not found")
    return run


def run_case_rows(session: Session, run: Run) -> list[dict[str, Any]]:
    results = session.scalars(select(RunResult).where(RunResult.run_id == run.id)).all()
    cases = {tc.id: tc for tc in session.scalars(
        select(TestCase).where(TestCase.dataset_version_id == run.dataset_version_id)).all()}
    scores: dict[uuid.UUID, list[MetricScore]] = {}
    for sc in session.scalars(select(MetricScore).where(MetricScore.run_id == run.id)).all():
        scores.setdefault(sc.run_result_id, []).append(sc)
    rows = []
    for r in sorted(results, key=lambda r: cases[r.test_case_id].position if r.test_case_id in cases else 0):
        tc = cases.get(r.test_case_id)
        rows.append({
            "id": str(r.id),
            "external_id": r.external_id,
            "input": tc.input if tc else None,
            "expected_output": tc.expected_output if tc else None,
            "tags": list(tc.tags) if tc else [],
            "output_text": r.output_text,
            "output_json": r.output_json,
            "latency_ms": r.latency_ms,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "tokens_estimated": r.tokens_estimated,
            "cost_usd": r.cost_usd,
            "error": r.error,
            "attempts": r.attempts,
            "passed": r.passed,
            "trace_id": str(r.trace_id) if r.trace_id else None,
            "scores": [
                {"metric": s.metric, "status": s.status, "value": s.value, "passed": s.passed,
                 "is_estimate": s.is_estimate, "gating": s.gating, "explanation": s.explanation, "details": s.details}
                for s in sorted(scores.get(r.id, []), key=lambda s: s.metric)
            ],
        })
    return rows


def run_dict(session: Session, run: Run) -> dict[str, Any]:
    target = session.get(Target, run.target_id)
    snap = run.config_snapshot or {}
    mc = snap.get("model_config") or {}
    provider = mc.get("provider") or ({"http_nexus": "nexus-http", "http_datawise": "datawise-http"}.get(
        target.kind if target else "", None))
    return {
        "id": str(run.id),
        "project_id": str(run.project_id),
        "experiment_id": str(run.experiment_id) if run.experiment_id else None,
        "dataset_version_id": str(run.dataset_version_id),
        "target_id": str(run.target_id),
        "target_name": target.name if target else None,
        "target_kind": target.kind if target else None,
        "provider": provider,
        "model": mc.get("model"),
        "is_deterministic_provider": provider in ("local", "mock_scripted"),
        "label": run.label,
        "status": run.status,
        "error": run.error,
        "seed": run.seed,
        "git_sha": run.git_sha,
        "dataset_hash": run.dataset_hash,
        "config_snapshot": snap,
        "summary": run.summary,
        "progress_done": run.progress_done,
        "progress_total": run.progress_total,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
