from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import IdMixin, TimestampMixin


class WorkflowRun(IdMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    goal: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="running")
    # running | awaiting_approval | completed | failed | budget_exceeded
    plan: Mapped[list[str]] = mapped_column(JSONB, default=list)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # checkpointed graph state
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    token_budget: Mapped[int] = mapped_column(Integer)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowStep(IdMixin, Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (UniqueConstraint("run_id", "name", name="uq_step_run_name"),)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(60))
    agent: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|completed|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApprovalRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "approval_requests"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_approval_idem"),)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_runs.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60))  # e.g. send_email
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rationale: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|executed
    idempotency_key: Mapped[str] = mapped_column(String(120))
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class OutboxMessage(IdMixin, TimestampMixin, Base):
    """Local demo email connector: 'sending' writes here instead of a real SMTP server."""

    __tablename__ = "outbox_messages"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_outbox_idem"),)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    to_address: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    approval_id: Mapped[str] = mapped_column(ForeignKey("approval_requests.id"))


class AuditEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str | None] = mapped_column(String(60))
    target_id: Mapped[str | None] = mapped_column(String(60))
    outcome: Mapped[str] = mapped_column(String(20), default="success")
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))


class UsageRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "usage_records"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    run_id: Mapped[str | None] = mapped_column(String(36))
    purpose: Mapped[str] = mapped_column(String(60))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
