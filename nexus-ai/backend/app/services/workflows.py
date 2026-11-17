"""Workflow lifecycle: start, execute (LangGraph), resume after failure, query."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.investigation import build_graph
from app.agents.runtime import StepFailed
from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import Conflict, NotFound
from app.core.logging import get_logger
from app.models import ApprovalRequest, User, WorkflowRun, WorkflowStep
from app.models.base import utcnow
from app.services.audit import audit

log = get_logger(__name__)


def start_run(db: Session, user: User, goal: str) -> WorkflowRun:
    run = WorkflowRun(
        org_id=user.org_id,
        user_id=user.id,
        goal=goal,
        kind="investigation",
        status="running",
        token_budget=get_settings().workflow_token_budget,
        state={"goal": goal},
    )
    db.add(run)
    db.flush()
    audit(
        db,
        org_id=user.org_id,
        actor_id=user.id,
        action="workflow.start",
        target_type="workflow_run",
        target_id=run.id,
        details={"goal": goal[:300]},
    )
    db.commit()
    return run


def execute_run(run_id: str) -> None:
    """Runs (or resumes) the graph. Safe to call from a background task."""
    with session_factory()() as db:
        run = db.get(WorkflowRun, run_id)
        if run is None:
            return
        initial: dict[str, Any] = {**(run.state or {}), "run_id": run.id, "goal": run.goal}
    status, error = "completed", None
    final: dict[str, Any] = {}
    try:
        final = build_graph(run_id).invoke(initial)
    except StepFailed as exc:
        status, error = ("budget_exceeded" if exc.budget else "failed"), str(exc)
    except Exception as exc:  # noqa: BLE001 -- unexpected graph failure is recorded on the run
        status, error = "failed", f"{type(exc).__name__}: {exc}"
    with session_factory()() as db:
        run = db.get(WorkflowRun, run_id)
        assert run is not None
        plan = (final or run.state or {}).get("plan") or {}
        run.plan = plan.get("steps", [])
        if status == "completed":
            if plan.get("intent") == "unsupported":
                status, error = "failed", plan.get("rationale")
            elif final.get("report"):
                run.report = final["report"] | {
                    "analysis": final.get("analysis"),
                    "declining": final.get("declining", []),
                }
            pending = db.scalar(
                select(ApprovalRequest.id)
                .where(ApprovalRequest.run_id == run_id, ApprovalRequest.status == "pending")
                .limit(1)
            )
            if pending and status == "completed":
                status = "awaiting_approval"
        run.status, run.error = status, error
        run.finished_at = utcnow() if status in ("completed", "failed", "budget_exceeded") else None
        audit(
            db,
            org_id=run.org_id,
            actor_id=run.user_id,
            action="workflow.finish",
            target_type="workflow_run",
            target_id=run.id,
            outcome="success" if status in ("completed", "awaiting_approval") else "error",
            details={"status": status, "tokens_used": run.tokens_used},
        )
        db.commit()
    log.info("workflow_finished", run_id=run_id, status=status)


def resume_run(db: Session, user: User, run_id: str) -> WorkflowRun:
    run = get_run(db, user, run_id)
    if run.status not in ("failed", "interrupted"):
        raise Conflict(f"Only failed or interrupted runs can be resumed (status: {run.status})")
    for step in db.scalars(
        select(WorkflowStep).where(WorkflowStep.run_id == run.id, WorkflowStep.status != "completed")
    ):
        step.status = "pending"
    run.status, run.error, run.finished_at = "running", None, None
    audit(
        db, org_id=user.org_id, actor_id=user.id, action="workflow.resume", target_type="workflow_run", target_id=run.id
    )
    db.commit()
    return run


def stale_after_seconds() -> float:
    """A live run always shows step activity within one step's full retry budget."""
    s = get_settings()
    return s.workflow_step_timeout_s * s.workflow_step_max_attempts + 60.0


def mark_interrupted_runs(now: datetime | None = None) -> int:
    """Startup recovery: runs whose process died become resumable.

    Only runs with no step activity for longer than any live step could take are marked. Blindly
    marking every 'running' run would break runs owned by OTHER healthy API replicas during a
    rolling deploy.
    """
    cutoff = (now or utcnow()) - timedelta(seconds=stale_after_seconds())
    last_activity = (
        select(func.max(func.coalesce(WorkflowStep.finished_at, WorkflowStep.started_at)))
        .where(WorkflowStep.run_id == WorkflowRun.id)
        .scalar_subquery()
    )
    with session_factory()() as db:
        runs = list(
            db.scalars(
                select(WorkflowRun).where(
                    WorkflowRun.status == "running",
                    func.coalesce(last_activity, WorkflowRun.created_at) < cutoff,
                )
            )
        )
        for r in runs:
            r.status, r.error = "interrupted", "process stopped during execution; resume to continue"
        db.commit()
        return len(runs)


def get_run(db: Session, user: User, run_id: str) -> WorkflowRun:
    run = db.get(WorkflowRun, run_id)
    if run is None or run.org_id != user.org_id:
        raise NotFound("Workflow run not found")
    return run


def list_steps(db: Session, run_id: str) -> list[WorkflowStep]:
    return list(db.scalars(select(WorkflowStep).where(WorkflowStep.run_id == run_id).order_by(WorkflowStep.seq)))
