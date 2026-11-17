"""Checkpointed step execution: per-step DB session, timeout, retries, budget, persistence.

Each graph node runs through `run_step`. A completed step's output is stored in workflow_steps and
merged into workflow_runs.state, so a resumed run skips completed steps (recovery).
"""

from __future__ import annotations

import concurrent.futures as cf
import contextvars
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import AppError, Forbidden
from app.core.telemetry import tracer
from app.llm import LLMRequest, Usage, traced_generate
from app.llm.base import T
from app.models import User, WorkflowRun, WorkflowStep
from app.models.base import utcnow
from app.services.audit import record_usage
from app.tools.registry import ToolContext, ToolError, execute

_POOL = cf.ThreadPoolExecutor(max_workers=8, thread_name_prefix="wf-step")


class BudgetExceeded(RuntimeError):
    pass


class StepFailed(RuntimeError):
    def __init__(self, step: str, message: str, *, budget: bool = False):
        super().__init__(f"{step}: {message}")
        self.step = step
        self.budget = budget


NON_RETRYABLE = (BudgetExceeded, ToolError, Forbidden, AppError, ValueError)


@dataclass
class StepContext:
    db: Session
    user: User
    run: WorkflowRun
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens: int = 0

    def tool(self, name: str, **args: Any) -> BaseModel:
        out, rec = execute(name, args, ToolContext(db=self.db, user=self.user, run_id=self.run.id))
        self.tool_calls.append(
            {"tool": rec.tool, "args": rec.args, "ok": rec.ok, "latency_ms": rec.latency_ms, "summary": rec.summary}
        )
        return out

    def llm(self, request: LLMRequest, schema: type[T], purpose: str) -> T:
        projected = self.run.tokens_used + self.tokens + len(request.system + request.user) // 4
        if projected > self.run.token_budget:
            raise BudgetExceeded(f"token budget {self.run.token_budget} would be exceeded")
        result, usage = traced_generate(request, schema)
        self._charge(usage, purpose)
        return result

    def _charge(self, usage: Usage, purpose: str) -> None:
        self.tokens += usage.input_tokens + usage.output_tokens
        record_usage(
            self.db, org_id=self.user.org_id, user_id=self.user.id, purpose=purpose, usage=usage, run_id=self.run.id
        )
        self.tool_calls.append(
            {
                "tool": f"llm:{purpose}",
                "args": {},
                "ok": True,
                "latency_ms": usage.latency_ms,
                "summary": f"{usage.provider}/{usage.model} {usage.input_tokens}+{usage.output_tokens} tok",
            }
        )


StepFn = Callable[[StepContext, dict[str, Any]], dict[str, Any]]


def run_step(run_id: str, seq: int, name: str, agent: str, fn: StepFn, state: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    Session_ = session_factory()
    with Session_() as db:
        step = db.scalar(select(WorkflowStep).where(WorkflowStep.run_id == run_id, WorkflowStep.name == name))
        if step is not None and step.status == "completed":
            return step.output or {}  # checkpoint hit (resume)
        if step is None:
            step = WorkflowStep(run_id=run_id, seq=seq, name=name, agent=agent)
            db.add(step)
            db.commit()
        step_id = step.id

    last_error = "unknown"
    for attempt in range(1, s.workflow_step_max_attempts + 1):
        with Session_() as db:
            st = db.get(WorkflowStep, step_id)
            assert st is not None
            st.status, st.attempts, st.started_at, st.error = "running", attempt, utcnow(), None
            db.commit()
        cancelled = threading.Event()
        span = tracer.start_span(
            f"workflow.step {name}",
            attributes={
                "workflow.run_id": run_id,
                "workflow.step": name,
                "workflow.agent": agent,
                "workflow.attempt": attempt,
            },
        )
        with trace.use_span(span, end_on_exit=False):
            step_ctx = contextvars.copy_context()  # child spans in the worker thread nest under this step
        fut = _POOL.submit(step_ctx.run, _execute, run_id, step_id, fn, state, cancelled)
        try:
            result = fut.result(timeout=s.workflow_step_timeout_s)
            span.set_attribute("workflow.outcome", "completed")
            span.end()
            return result
        except cf.TimeoutError:
            cancelled.set()
            last_error = f"timed out after {s.workflow_step_timeout_s}s"
            retryable = True
            budget = False
        except NON_RETRYABLE as exc:
            last_error, retryable, budget = f"{type(exc).__name__}: {exc}", False, isinstance(exc, BudgetExceeded)
        except Exception as exc:  # noqa: BLE001 -- transient failure, retry with backoff
            last_error, retryable, budget = f"{type(exc).__name__}: {exc}", True, False
        span.set_attribute("workflow.outcome", "failed")
        span.set_attribute("workflow.retryable", retryable)
        span.set_status(Status(StatusCode.ERROR, last_error[:200]))
        span.end()
        with Session_() as db:
            st = db.get(WorkflowStep, step_id)
            assert st is not None
            st.status, st.error, st.finished_at = "failed", last_error[:2000], utcnow()
            db.commit()
        if not retryable or attempt == s.workflow_step_max_attempts:
            raise StepFailed(name, last_error, budget=budget)
        time.sleep(min(0.25 * 2 ** (attempt - 1), 2.0))
    raise StepFailed(name, last_error)


def _execute(
    run_id: str, step_id: str, fn: StepFn, state: dict[str, Any], cancelled: threading.Event
) -> dict[str, Any]:
    with session_factory()() as db:
        run = db.get(WorkflowRun, run_id)
        assert run is not None
        user = db.get(User, run.user_id)
        assert user is not None
        ctx = StepContext(db=db, user=user, run=run)
        update = fn(ctx, state)
        if cancelled.is_set():  # timed out: discard all writes from this attempt
            db.rollback()
            return update
        step = db.get(WorkflowStep, step_id)
        assert step is not None
        step.status, step.output, step.tool_calls, step.finished_at = "completed", update, ctx.tool_calls, utcnow()
        run.tokens_used += ctx.tokens
        run.state = {**(run.state or {}), **update}  # checkpoint
        db.commit()
        return update
