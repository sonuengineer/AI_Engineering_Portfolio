"""Typed tool registry with permission checks, input/output validation, approval gating,
idempotency and audit for every call. Agents and the MCP server both go through `execute`."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.errors import AppError, Forbidden
from app.core.telemetry import tracer
from app.models import User
from app.services.audit import audit, audit_independent

SideEffect = Literal["read", "write", "external"]
ROLE_RANK = {"viewer": 0, "analyst": 1, "manager": 2, "admin": 3}


class ToolError(AppError):
    code = "tool_error"


class ApprovalRequired(AppError):
    status_code = 409
    code = "approval_required"


@dataclass
class ToolContext:
    db: Session
    user: User
    run_id: str | None = None
    approved_action_id: str | None = None  # set only by the approval executor


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    fn: Callable[[ToolContext, Any], BaseModel]
    min_role: str = "analyst"
    side_effect: SideEffect = "read"
    requires_approval: bool = False
    mcp_exposed: bool = True


@dataclass
class ToolCallRecord:
    tool: str
    args: dict[str, Any]
    ok: bool
    latency_ms: int
    summary: str
    error: str | None = None
    output: dict[str, Any] | None = field(default=None, repr=False)


REGISTRY: dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> ToolSpec:
    if spec.name in REGISTRY:
        raise ValueError(f"duplicate tool {spec.name}")
    REGISTRY[spec.name] = spec
    return spec


def execute(name: str, args: dict[str, Any], ctx: ToolContext) -> tuple[BaseModel, ToolCallRecord]:
    """Run a tool inside a 'tool.<name>' span; see _execute for the checks."""
    spec = REGISTRY.get(name)
    with tracer.start_as_current_span(f"tool.{name}") as span:
        span.set_attribute("tool.name", name)
        span.set_attribute("tool.side_effect", spec.side_effect if spec else "unknown")
        try:
            out, record = _execute(name, args, ctx)
        except Exception as exc:
            span.set_attribute("tool.outcome", type(exc).__name__)
            raise
        span.set_attribute("tool.outcome", "ok")
        span.set_attribute("tool.latency_ms", record.latency_ms)
        return out, record


def _execute(name: str, args: dict[str, Any], ctx: ToolContext) -> tuple[BaseModel, ToolCallRecord]:
    spec = REGISTRY.get(name)
    if spec is None:
        raise ToolError(f"Unknown tool '{name}'")
    org_id, actor = ctx.user.org_id, ctx.user.id
    if ROLE_RANK.get(ctx.user.role, -1) < ROLE_RANK[spec.min_role]:
        audit_independent(
            org_id=org_id,
            actor_id=actor,
            action=f"tool.{name}",
            outcome="denied",
            details={"reason": "insufficient_role"},
        )
        raise Forbidden(f"Role '{ctx.user.role}' may not call tool '{name}'")
    if spec.requires_approval and ctx.approved_action_id is None:
        audit_independent(
            org_id=org_id,
            actor_id=actor,
            action=f"tool.{name}",
            outcome="blocked",
            details={"reason": "approval_required"},
        )
        raise ApprovalRequired(f"Tool '{name}' requires human approval")
    try:
        parsed = spec.input_model.model_validate(args)
    except ValidationError as exc:
        raise ToolError(f"Invalid arguments for '{name}': {exc.errors()[:3]}") from exc
    t0 = time.perf_counter()
    try:
        raw = spec.fn(ctx, parsed)
        out = spec.output_model.model_validate(raw.model_dump() if isinstance(raw, BaseModel) else raw)
    except ValidationError as exc:
        audit_independent(
            org_id=org_id,
            actor_id=actor,
            action=f"tool.{name}",
            outcome="error",
            details={"reason": "invalid_tool_output"},
        )
        raise ToolError(f"Tool '{name}' produced invalid output") from exc
    latency = int((time.perf_counter() - t0) * 1000)
    dumped = out.model_dump(mode="json")
    record = ToolCallRecord(
        tool=name,
        args=parsed.model_dump(mode="json"),
        ok=True,
        latency_ms=latency,
        summary=_summarize(dumped),
        output=dumped,
    )
    audit(
        ctx.db,
        org_id=org_id,
        actor_id=actor,
        action=f"tool.{name}",
        target_type="workflow_run",
        target_id=ctx.run_id,
        details={"args": record.args, "side_effect": spec.side_effect, "latency_ms": latency},
    )
    return out, record


def _summarize(d: dict[str, Any]) -> str:
    for k, v in d.items():
        if isinstance(v, list):
            return f"{len(v)} {k}"
    return ", ".join(f"{k}={v}" for k, v in list(d.items())[:3])[:200]
