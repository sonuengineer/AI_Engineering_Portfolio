from typing import Any

from sqlalchemy.orm import Session

from app.core.context import request_id_var
from app.llm.base import Usage
from app.models import AuditEvent, UsageRecord


def audit(
    db: Session,
    *,
    org_id: str,
    actor_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            org_id=org_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            details=details or {},
            request_id=request_id_var.get(),
        )
    )


def audit_independent(
    *,
    org_id: str,
    actor_id: str | None,
    action: str,
    outcome: str,
    details: dict[str, Any] | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
) -> None:
    """Write an audit event in its own transaction.

    Used for denials and blocks: the caller's transaction is usually rolled back by the error that
    follows, which would otherwise erase the security-relevant record.
    """
    from app.core.db import session_factory

    with session_factory()() as s:
        audit(
            s,
            org_id=org_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            details=details,
        )
        s.commit()


def record_usage(
    db: Session,
    *,
    org_id: str,
    user_id: str | None,
    purpose: str,
    usage: Usage,
    run_id: str | None = None,
) -> None:
    db.add(
        UsageRecord(
            org_id=org_id,
            user_id=user_id,
            run_id=run_id,
            purpose=purpose,
            provider=usage.provider,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_usd=usage.estimated_cost_usd,
            latency_ms=usage.latency_ms,
            note="token counts are estimates" if usage.tokens_are_estimates else None,
        )
    )
