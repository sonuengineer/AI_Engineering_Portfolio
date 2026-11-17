"""Human-in-the-loop approvals. The only path that can trigger an external side effect."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Forbidden, NotFound
from app.models import ApprovalRequest, User, WorkflowRun
from app.models.base import utcnow
from app.services.audit import audit
from app.tools.registry import ROLE_RANK, ToolContext, execute

APPROVER_MIN_ROLE = "manager"


def _load(db: Session, user: User, approval_id: str, lock: bool = True) -> ApprovalRequest:
    stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    if lock:
        stmt = stmt.with_for_update()  # serialize concurrent decisions on the same request
    req = db.scalar(stmt)
    if req is None or req.org_id != user.org_id:
        raise NotFound("Approval request not found")
    return req


def _check_approver(user: User) -> None:
    if ROLE_RANK.get(user.role, -1) < ROLE_RANK[APPROVER_MIN_ROLE]:
        raise Forbidden("Only managers or admins can decide approval requests")


def approve(
    db: Session,
    user: User,
    approval_id: str,
    note: str | None,
    edited_subject: str | None = None,
    edited_body: str | None = None,
) -> ApprovalRequest:
    _check_approver(user)
    req = _load(db, user, approval_id)
    if req.status == "executed":
        return req  # idempotent: approving twice never sends twice
    if req.status != "pending":
        raise Conflict(f"Request is already {req.status}")
    payload = dict(req.payload)
    if edited_subject:
        payload["subject"] = edited_subject
    if edited_body:
        payload["body"] = edited_body
    req.payload = payload
    req.status, req.decided_by, req.decided_at, req.decision_note = "approved", user.id, utcnow(), note
    audit(
        db,
        org_id=user.org_id,
        actor_id=user.id,
        action="approval.approve",
        target_type="approval_request",
        target_id=req.id,
        details={"action": req.action},
    )
    if req.action == "send_email":
        out, _rec = execute(
            "send_email",
            {
                "to": payload["to"],
                "subject": payload["subject"],
                "body": payload["body"],
                "idempotency_key": req.idempotency_key,
            },
            ToolContext(db=db, user=user, run_id=req.run_id, approved_action_id=req.id),
        )
        req.result = out.model_dump()
        req.status = "executed"
    _maybe_complete_run(db, req.run_id)
    db.commit()
    return req


def reject(db: Session, user: User, approval_id: str, note: str | None) -> ApprovalRequest:
    _check_approver(user)
    req = _load(db, user, approval_id)
    if req.status != "pending":
        raise Conflict(f"Request is already {req.status}")
    req.status, req.decided_by, req.decided_at, req.decision_note = "rejected", user.id, utcnow(), note
    audit(
        db,
        org_id=user.org_id,
        actor_id=user.id,
        action="approval.reject",
        target_type="approval_request",
        target_id=req.id,
    )
    _maybe_complete_run(db, req.run_id)
    db.commit()
    return req


def _maybe_complete_run(db: Session, run_id: str | None) -> None:
    if not run_id:
        return
    db.flush()
    pending = db.scalar(
        select(ApprovalRequest.id).where(ApprovalRequest.run_id == run_id, ApprovalRequest.status == "pending").limit(1)
    )
    run = db.get(WorkflowRun, run_id)
    if run is not None and pending is None and run.status == "awaiting_approval":
        run.status, run.finished_at = "completed", utcnow()
