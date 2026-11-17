from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core.db import get_db
from app.models import AuditEvent, OutboxMessage, UsageRecord, User
from app.schemas.api import AuditOut, UserOut
from app.tools.registry import REGISTRY

router = APIRouter(tags=["admin"])


@router.get("/admin/users", response_model=list[UserOut])
def users(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).where(User.org_id == user.org_id).order_by(User.email)))


@router.get("/admin/audit", response_model=list[AuditOut])
def audit_log(
    action: str | None = None,
    limit: int = 100,
    user: User = Depends(require_role("manager")),
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(AuditEvent.org_id == user.org_id)
    if action:
        stmt = stmt.where(AuditEvent.action.like(f"{action}%"))
    return list(db.scalars(stmt.order_by(AuditEvent.created_at.desc()).limit(min(limit, 500))))


@router.get("/admin/usage")
def usage(user: User = Depends(require_role("manager")), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.execute(
        select(
            UsageRecord.purpose,
            UsageRecord.provider,
            UsageRecord.model,
            func.count(),
            func.sum(UsageRecord.input_tokens),
            func.sum(UsageRecord.output_tokens),
            func.sum(UsageRecord.estimated_cost_usd),
            func.avg(UsageRecord.latency_ms),
        )
        .where(UsageRecord.org_id == user.org_id)
        .group_by(UsageRecord.purpose, UsageRecord.provider, UsageRecord.model)
    ).all()
    return {
        "by_purpose": [
            {
                "purpose": p,
                "provider": pr,
                "model": m,
                "calls": n,
                "input_tokens": int(ti or 0),
                "output_tokens": int(to or 0),
                "estimated_cost_usd": float(c or 0),
                "avg_latency_ms": round(float(lat or 0), 1),
            }
            for p, pr, m, n, ti, to, c, lat in rows
        ],
        "note": "Local adapter token counts are character-based estimates; cost is 0 for local.",
    }


@router.get("/admin/outbox")
def outbox(user: User = Depends(require_role("manager")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(OutboxMessage)
        .where(OutboxMessage.org_id == user.org_id)
        .order_by(OutboxMessage.created_at.desc())
        .limit(100)
    )
    return [
        {
            "id": m.id,
            "to": m.to_address,
            "subject": m.subject,
            "body": m.body,
            "approval_id": m.approval_id,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]


@router.get("/tools")
def tools(_: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "side_effect": t.side_effect,
            "min_role": t.min_role,
            "requires_approval": t.requires_approval,
            "mcp_exposed": t.mcp_exposed,
            "input_schema": t.input_model.model_json_schema(),
        }
        for t in REGISTRY.values()
    ]
