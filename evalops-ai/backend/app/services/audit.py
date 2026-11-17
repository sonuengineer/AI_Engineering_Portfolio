"""Audit trail writer."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.redaction import redact
from app.models import AuditEvent


def record(
    session: Session, *, org_id: uuid.UUID | None, user_id: uuid.UUID | None, action: str,
    resource_type: str = "", resource_id: str | uuid.UUID | None = None, details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> None:
    session.add(AuditEvent(
        org_id=org_id, user_id=user_id, action=action, resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None, details=redact(details or {}), request_id=request_id,
    ))
