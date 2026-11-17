"""The question pipeline: guardrails -> planner -> compiler -> validator -> executor -> insight -> persist.

No FastAPI imports here; routers call this and serialize the result.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.llm.base import PlannerProvider, ProviderError
from app.models import AuditEvent, QueryHistory, User
from app.schemas.api import AskResponse, Usage, Validation
from app.schemas.plan import Clarification, QueryPlan
from app.services.compiler import PlanError, compile_plan
from app.services.executor import ExecutionError, execute_readonly
from app.services.guardrails import check_question
from app.services.insight import build_insight
from app.services.validator import validate_sql

log = get_logger("datawise.ask")


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


class AskService:
    def __init__(self, settings: Settings, planner: PlannerProvider) -> None:
        self.settings = settings
        self.planner = planner

    # ---------------------------------------------------------------- persistence

    def _persist(self, db: Session, user: User, question: str, resp: AskResponse, request_id: str | None,
                 detail: str | None = None) -> AskResponse:
        hist = QueryHistory(
            org_id=user.org_id, user_id=user.id, question=question, status=resp.status if detail is None else "error",
            plan=resp.plan, sql=resp.sql, row_count=resp.row_count, provider=resp.provider,
            latency_ms=resp.latency_ms, detail=detail or resp.rejection_reason,
        )
        db.add(hist)
        db.flush()
        db.add(AuditEvent(
            org_id=user.org_id, user_id=user.id, action="question.asked", request_id=request_id,
            detail={"query_id": hist.id, "status": hist.status, "provider": resp.provider,
                    "row_count": resp.row_count, "validation_ok": resp.validation.ok},
        ))
        db.commit()
        resp.query_id = hist.id
        log.info("question_processed", query_id=hist.id, status=hist.status, provider=resp.provider,
                 latency_ms=resp.latency_ms, row_count=resp.row_count, org_id=user.org_id)
        return resp

    def _base(self) -> dict[str, Any]:
        return {"provider": self.planner.name, "model": self.planner.model}

    # ---------------------------------------------------------------- entry points

    def ask(self, db: Session, user: User, question: str, request_id: str | None) -> AskResponse:
        t0 = time.perf_counter()
        question = question.strip()
        blocked = check_question(question)
        if blocked:
            category, reason = blocked
            resp = AskResponse(status="rejected", rejection_reason=reason,
                               validation=Validation(ok=False, issues=[f"guardrail:{category}"]),
                               latency_ms=_ms(t0), **self._base())
            return self._persist(db, user, question, resp, request_id)

        try:
            outcome, usage = self.planner.plan(question)
        except ProviderError as e:
            raise AppError(502, "planner_error", str(e)) from e
        usage_out = Usage(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                          estimated_cost_usd=usage.estimated_cost_usd)

        if outcome.kind == "reject":
            resp = AskResponse(status="rejected", rejection_reason=outcome.reason or "Request rejected by planner",
                               validation=Validation(ok=False, issues=["planner:reject"]),
                               latency_ms=_ms(t0), usage=usage_out, **self._base())
            return self._persist(db, user, question, resp, request_id)
        if outcome.kind == "clarify" or outcome.plan is None:
            clar = outcome.clarification or Clarification(question="Could you rephrase the question?", options=[])
            resp = AskResponse(status="needs_clarification", clarification=clar,
                               validation=Validation(ok=False, issues=[]), latency_ms=_ms(t0),
                               usage=usage_out, **self._base())
            return self._persist(db, user, question, resp, request_id)

        return self.run_plan(db, user, question, outcome.plan, request_id, t0=t0, usage=usage_out)

    def run_plan(self, db: Session, user: User, question: str, plan: QueryPlan, request_id: str | None,
                 t0: float | None = None, usage: Usage | None = None) -> AskResponse:
        t0 = t0 if t0 is not None else time.perf_counter()
        usage = usage or Usage()
        s = self.settings
        plan_dict = plan.model_dump(mode="json")
        try:
            compiled = compile_plan(plan, s.max_rows)
        except PlanError as e:
            resp = AskResponse(status="needs_clarification", plan=plan_dict,
                               clarification=Clarification(question="The plan is not valid: " + "; ".join(e.issues),
                                                           options=[]),
                               validation=Validation(ok=False, issues=e.issues), latency_ms=_ms(t0), usage=usage,
                               **self._base())
            return self._persist(db, user, question, resp, request_id)

        validation = validate_sql(compiled.sql, s.max_rows)
        if not validation.ok:
            resp = AskResponse(status="rejected", plan=plan_dict, sql=compiled.sql,
                               validation=Validation(ok=False, issues=validation.issues),
                               rejection_reason="Generated SQL failed safety validation and was not executed.",
                               latency_ms=_ms(t0), usage=usage, **self._base())
            return self._persist(db, user, question, resp, request_id)

        try:
            result = execute_readonly(compiled.sql, s.analytics_reader_database_url, s.max_rows,
                                      s.statement_timeout_ms)
        except ExecutionError as e:
            resp = AskResponse(status="rejected", plan=plan_dict, sql=compiled.sql,
                               validation=Validation(ok=True, issues=[]), latency_ms=_ms(t0), usage=usage,
                               **self._base())
            self._persist(db, user, question, resp, request_id, detail=f"{e.code}: {e.message}")
            status = 504 if e.code == "query_timeout" else 502
            raise AppError(status, e.code, e.message) from e

        ins = build_insight(plan, result.columns, result.rows, result.truncated)
        issues = list(ins.issues)
        resp = AskResponse(
            status="answered", plan=plan_dict, sql=compiled.sql,
            validation=Validation(ok=not issues, issues=issues),
            columns=result.columns, rows=result.rows, row_count=len(result.rows),
            insight=ins.text, insight_provenance=ins.provenance, chart=ins.chart,
            latency_ms=_ms(t0), usage=usage, **self._base(),
        )
        return self._persist(db, user, question, resp, request_id)
