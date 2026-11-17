from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core.db import get_db
from app.models import ApprovalRequest, User, WorkflowRun
from app.schemas.api import ApprovalOut, DecisionIn, RunDetailOut, RunOut, StepOut, WorkflowIn
from app.services import approvals as approval_service
from app.services import workflows as wf

router = APIRouter(tags=["workflows"])


@router.post("/workflows", response_model=RunOut, status_code=202)
def start(
    body: WorkflowIn, bg: BackgroundTasks, user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)
) -> WorkflowRun:
    run = wf.start_run(db, user, body.goal)
    bg.add_task(wf.execute_run, run.id)
    return run


@router.get("/workflows", response_model=list[RunOut])
def list_runs(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[WorkflowRun]:
    return list(
        db.scalars(
            select(WorkflowRun)
            .where(WorkflowRun.org_id == user.org_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(50)
        )
    )


@router.get("/workflows/{run_id}", response_model=RunDetailOut)
def get_run(run_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> RunDetailOut:
    run = wf.get_run(db, user, run_id)
    steps = [StepOut.model_validate(s) for s in wf.list_steps(db, run.id)]
    approvals = [
        ApprovalOut.model_validate(a)
        for a in db.scalars(
            select(ApprovalRequest).where(ApprovalRequest.run_id == run.id).order_by(ApprovalRequest.created_at)
        )
    ]
    return RunDetailOut(**RunOut.model_validate(run).model_dump(), report=run.report, steps=steps, approvals=approvals)


@router.post("/workflows/{run_id}/resume", response_model=RunOut, status_code=202)
def resume(
    run_id: str, bg: BackgroundTasks, user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)
) -> WorkflowRun:
    run = wf.resume_run(db, user, run_id)
    bg.add_task(wf.execute_run, run.id)
    return run


@router.get("/approvals", response_model=list[ApprovalOut])
def list_approvals(
    status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[ApprovalRequest]:
    stmt = select(ApprovalRequest).where(ApprovalRequest.org_id == user.org_id)
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    return list(db.scalars(stmt.order_by(ApprovalRequest.created_at.desc()).limit(200)))


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalOut)
def approve(
    approval_id: str, body: DecisionIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ApprovalRequest:
    return approval_service.approve(db, user, approval_id, body.note, body.subject, body.body)


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalOut)
def reject(
    approval_id: str, body: DecisionIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ApprovalRequest:
    return approval_service.reject(db, user, approval_id, body.note)
