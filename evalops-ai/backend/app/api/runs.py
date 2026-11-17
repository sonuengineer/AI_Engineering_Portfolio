"""Runs, results, compare, traces, reports, audit."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select

from app.api.deps import DB, Admin, CurrentUser, Member, get_project_or_404, request_id
from app.core.errors import NotFound, ValidationFailed
from app.models import AuditEvent, Run, Span, Trace
from app.schemas import AuditOut, RunCreate, SpanOut, TraceOut
from app.services import audit, reports
from app.services.compare_runs import compare_runs
from app.services.run_queries import get_run, run_case_rows, run_dict
from app.services.runs import create_runs

router = APIRouter(prefix="/api/v1", tags=["runs"])


@router.post("/runs", status_code=202)
def create_run(body: RunCreate, p: Member, db: DB, request: Request) -> dict[str, Any]:
    get_project_or_404(db, p, body.project_id)
    runs = create_runs(
        db, org_id=p.org_id, user_id=p.user_id, project_id=body.project_id,
        dataset_version_id=body.dataset_version_id, target_ids=body.target_ids, evaluator_ids=body.evaluator_ids,
        experiment_id=body.experiment_id, label=body.label, concurrency=body.concurrency, timeout_s=body.timeout_s,
        max_retries=body.max_retries, seed=body.seed,
    )
    for r in runs:
        audit.record(db, org_id=p.org_id, user_id=p.user_id, action="run.create", resource_type="run",
                     resource_id=r.id, details={"target_id": str(r.target_id)}, request_id=request_id(request))
    db.commit()
    return {"run_ids": [str(r.id) for r in runs], "status": "queued"}


@router.get("/runs")
def list_runs(
    p: CurrentUser, db: DB, project_id: uuid.UUID | None = None, experiment_id: uuid.UUID | None = None,
    status: str | None = None, limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    q = select(Run).where(Run.org_id == p.org_id)
    if project_id:
        q = q.where(Run.project_id == project_id)
    if experiment_id:
        q = q.where(Run.experiment_id == experiment_id)
    if status:
        q = q.where(Run.status == status)
    rows = db.scalars(q.order_by(Run.created_at.desc()).limit(limit)).all()
    return [{k: v for k, v in run_dict(db, r).items() if k != "config_snapshot"} for r in rows]


@router.get("/runs/{run_id}")
def get_run_detail(run_id: uuid.UUID, p: CurrentUser, db: DB) -> dict[str, Any]:
    return run_dict(db, get_run(db, p.org_id, run_id))


@router.get("/runs/{run_id}/results")
def get_run_results(
    run_id: uuid.UUID, p: CurrentUser, db: DB, failed_only: bool = False, metric: str | None = None,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    run = get_run(db, p.org_id, run_id)
    rows = run_case_rows(db, run)
    if failed_only:
        rows = [r for r in rows if r["passed"] is False]
    if metric:
        rows = [r for r in rows if any(s["metric"] == metric and s["status"] == "scored" and not s["passed"]
                                       for s in r["scores"])]
    if tag:
        rows = [r for r in rows if tag in r["tags"]]
    return rows


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: uuid.UUID, p: Member, db: DB, request: Request) -> dict[str, Any]:
    run = get_run(db, p.org_id, run_id)
    if run.status != "queued":
        raise ValidationFailed("only queued runs can be cancelled")
    run.status = "cancelled"
    audit.record(db, org_id=p.org_id, user_id=p.user_id, action="run.cancel", resource_type="run",
                 resource_id=run.id, request_id=request_id(request))
    db.commit()
    return {"id": str(run.id), "status": run.status}


@router.get("/compare")
def compare(
    p: CurrentUser, db: DB, baseline: uuid.UUID, candidate: uuid.UUID,
    tolerance: float = Query(default=0.02, ge=0, le=1),
    latency_tolerance_pct: float = Query(default=0.25, ge=0, le=10),
) -> dict[str, Any]:
    return compare_runs(db, p.org_id, baseline, candidate, tolerance=tolerance,
                        latency_tolerance_pct=latency_tolerance_pct)


@router.get("/runs/{run_id}/traces", response_model=list[TraceOut])
def list_traces(run_id: uuid.UUID, p: CurrentUser, db: DB) -> list[Trace]:
    get_run(db, p.org_id, run_id)
    return list(db.scalars(select(Trace).where(Trace.run_id == run_id).order_by(Trace.started_at)))


@router.get("/traces/{trace_id}", response_model=TraceOut)
def get_trace(trace_id: uuid.UUID, p: CurrentUser, db: DB) -> TraceOut:
    t = db.get(Trace, trace_id)
    if t is None or t.org_id != p.org_id:
        raise NotFound("trace not found")
    out = TraceOut.model_validate(t)
    out.spans = [SpanOut.model_validate(s) for s in db.scalars(
        select(Span).where(Span.trace_id == t.id).order_by(Span.started_at))]
    return out


@router.get("/runs/{run_id}/report.json")
def report_json(run_id: uuid.UUID, p: CurrentUser, db: DB) -> Response:
    import json

    run = get_run(db, p.org_id, run_id)
    body = reports.build_json(run_dict(db, run), run_case_rows(db, run))
    return Response(json.dumps(body, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="evalops-run-{run.id}.json"'})


@router.get("/runs/{run_id}/report.md")
def report_md(run_id: uuid.UUID, p: CurrentUser, db: DB) -> PlainTextResponse:
    run = get_run(db, p.org_id, run_id)
    return PlainTextResponse(reports.build_markdown(run_dict(db, run), run_case_rows(db, run)),
                             media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="evalops-run-{run.id}.md"'})


@router.get("/runs/{run_id}/results.csv")
def report_csv(run_id: uuid.UUID, p: CurrentUser, db: DB) -> PlainTextResponse:
    run = get_run(db, p.org_id, run_id)
    return PlainTextResponse(reports.build_csv(run_case_rows(db, run)), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="evalops-run-{run.id}.csv"'})


@router.get("/audit-events", response_model=list[AuditOut])
def list_audit(p: Admin, db: DB, limit: int = Query(default=100, ge=1, le=1000)) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).where(AuditEvent.org_id == p.org_id)
                           .order_by(AuditEvent.created_at.desc()).limit(limit)))
