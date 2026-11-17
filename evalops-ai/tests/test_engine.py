"""Run engine end-to-end against real Postgres with deterministic providers."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.engine import targets as targets_mod
from app.evaluators.base import CaseData
from app.llm.base import GenerationResult, TransientProviderError
from app.models import MetricScore, Run, RunResult, Span, Trace
from app.services.compare_runs import compare_runs
from app.services.runs import create_runs
from app.services.tracing import TraceRecorder
from app.worker import claim_next_run, process_available

from helpers import build_project


def _create(org, proj, target, **kw):
    with session_scope() as s:
        runs = create_runs(s, org_id=org["org_id"], user_id=None, project_id=proj["project_id"],
                           dataset_version_id=proj["dv_id"], target_ids=[proj["targets"][target]],
                           evaluator_ids=proj["evaluators"], **kw)
        return runs[0].id


def _run(run_id):
    with session_scope() as s:
        r = s.get(Run, run_id)
        return r.status, dict(r.summary), dict(r.config_snapshot), r.dataset_hash


def test_worker_claims_and_executes_scripted_run(org_a):
    proj = build_project(org_a["org_id"])
    rid = _create(org_a, proj, "good", seed=7)
    assert process_available("test-worker") == 1
    status, summary, snap, dhash = _run(rid)
    assert status == "completed"
    assert summary["case_count"] == 3 and summary["error_rate"] == 0
    assert summary["overall_pass_rate"] == 1.0
    assert summary["metrics"]["judge"]["skipped"] == 3 and summary["metrics"]["judge"]["is_estimate"]
    # reproducibility: snapshot carries config, dataset hash, prompt hash, seed
    assert snap["dataset"]["content_hash"] == dhash and snap["params"]["seed"] == 7
    assert snap["model_config"]["provider"] == "mock_scripted" and snap["prompt_version"]["content_hash"] == "h"
    assert claim_next_run("test-worker") is None  # queue drained


def test_skip_locked_claims_each_run_once(org_a):
    proj = build_project(org_a["org_id"])
    ids = {_create(org_a, proj, "good"), _create(org_a, proj, "bad")}
    claimed = {claim_next_run("w1"), claim_next_run("w2")}
    assert claimed == ids and claim_next_run("w3") is None


def test_local_provider_run_records_tokens_cost_and_traces(org_a):
    proj = build_project(org_a["org_id"])
    rid = _create(org_a, proj, "local")
    process_available("w")
    status, summary, _, _ = _run(rid)
    assert status == "completed"
    assert summary["tokens"]["total"] > 0 and summary["cost_usd"] > 0
    assert summary["metrics"]["citations"]["pass_rate"] == 0.0  # local adapter returns no citations
    assert summary["metrics"]["keywords"]["pass_rate"] == 1.0
    with session_scope() as s:
        results = s.scalars(select(RunResult).where(RunResult.run_id == rid)).all()
        assert all(r.tokens_estimated for r in results)
        traces = s.scalars(select(Trace).where(Trace.run_id == rid)).all()
        assert len(traces) == 3
        spans = s.scalars(select(Span).where(Span.trace_id.in_([t.id for t in traces]))).all()
        types = {sp.span_type for sp in spans}
        assert {"prompt", "model_call", "eval", "tool"} <= types
        # PII from case c3's input must be redacted in stored span attributes
        blob = " ".join(str(sp.attributes) for sp in spans)
        assert "someone@example.com" not in blob and "[REDACTED_EMAIL]" in blob
        # spans are ordered in time within a trace and nested
        root = next(sp for sp in spans if sp.name == "execute_case" and sp.trace_id == traces[0].id)
        children = [sp for sp in spans if sp.parent_span_id == root.id]
        assert children and all(c.started_at >= root.started_at for c in children)


def test_regression_between_scripted_runs(org_a):
    proj = build_project(org_a["org_id"])
    a = _create(org_a, proj, "good")
    b = _create(org_a, proj, "bad")
    process_available("w")
    with session_scope() as s:
        cmp = compare_runs(s, org_a["org_id"], a, b, tolerance=0.02)
    assert cmp["has_regression"] and cmp["same_dataset"]
    assert cmp["cases"]["newly_failing"] == ["c1", "c3"]
    assert "citations" in cmp["regressions"] and "judge" not in cmp["regressions"]


class _Flaky:
    name = "mock_scripted"
    is_real_llm = False

    def __init__(self, fail_times):
        self.calls = 0
        self.fail_times = fail_times

    def generate(self, request, model):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TransientProviderError("503 from upstream")
        return GenerationResult(text="Payment is due within 30 days.", provider="mock_scripted", model=model)


def test_retries_with_backoff_then_error_capture(org_a, monkeypatch):
    proj = build_project(org_a["org_id"])
    flaky = _Flaky(fail_times=2)
    monkeypatch.setattr(targets_mod, "get_provider", lambda name: flaky)
    rid = _create(org_a, proj, "good", concurrency=1, max_retries=2)
    with session_scope() as s:
        s.get(Run, rid).config_snapshot = {**s.get(Run, rid).config_snapshot,
                                           "params": {"concurrency": 1, "timeout_s": 5, "max_retries": 2, "seed": 0,
                                                      "backoff_base_s": 0.01}}
    process_available("w")
    with session_scope() as s:
        results = sorted(s.scalars(select(RunResult).where(RunResult.run_id == rid)).all(), key=lambda r: r.external_id)
        assert results[0].attempts == 3 and results[0].error is None  # 2 transient failures, then success
        assert all(r.error is None for r in results[1:])

    always = _Flaky(fail_times=10**6)
    monkeypatch.setattr(targets_mod, "get_provider", lambda name: always)
    rid2 = _create(org_a, proj, "good", max_retries=1)
    with session_scope() as s:
        run = s.get(Run, rid2)
        run.config_snapshot = {**run.config_snapshot, "params": {**run.config_snapshot["params"], "backoff_base_s": 0.01}}
    process_available("w")
    status, summary, _, _ = _run(rid2)
    assert status == "completed" and summary["error_rate"] == 1.0 and summary["overall_pass_rate"] == 0.0
    with session_scope() as s:
        r = s.scalars(select(RunResult).where(RunResult.run_id == rid2)).first()
        assert r.attempts == 2 and "transient" in r.error
        assert s.scalars(select(MetricScore).where(MetricScore.run_id == rid2)).first() is None


def test_unbuildable_target_fails_run(org_a, monkeypatch):
    proj = build_project(org_a["org_id"])
    rid = _create(org_a, proj, "good")

    def boom(snapshot):
        raise RuntimeError("no executor")

    monkeypatch.setattr("app.engine.runner.build_executor", boom)
    process_available("w")
    status, _, _, _ = _run(rid)
    assert status == "failed"


# ------------------------------------------------------------------ HTTP target contract mapping

def _mock_client(handler):
    real = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    return factory


def test_nexus_executor_maps_contract(monkeypatch):
    seen = {"logins": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v1/auth/login":
            seen["logins"] += 1
            return httpx.Response(200, json={"access_token": "tok", "token_type": "bearer"})
        assert req.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json={
            "conversation_id": "c", "answer": "Due in 30 days.", "provider": "local", "model": "m",
            "citations": [{"chunk_id": "x", "document_id": "uuid-1", "document_title": "Billing Policy", "page": 1,
                           "snippet": "s"}],
            "contexts": ["Payment is due within 30 days."], "usage": {"input_tokens": 10, "output_tokens": 4,
                                                                      "estimated_cost_usd": 0.0001},
            "latency_ms": 12})

    monkeypatch.setattr(targets_mod.httpx, "Client", _mock_client(handler))
    monkeypatch.setenv("NEXUS_EMAIL", "u@x.io")
    monkeypatch.setenv("NEXUS_PASSWORD", "pw-from-env")
    ex = targets_mod.build_executor({"target": {"kind": "http_nexus", "config": {"base_url": "http://nexus"}}})
    tr = TraceRecorder("t")
    out = ex.execute(CaseData(external_id="1", input="When is payment due?"), tr, 5)
    out2 = ex.execute(CaseData(external_id="2", input="again"), tr, 5)
    assert out.text == "Due in 30 days." and out.citations == ["Billing Policy"]
    assert out.contexts == ["Payment is due within 30 days."] and out.cost_usd == 0.0001
    assert out2.input_tokens == 10 and seen["logins"] == 1  # token cached
    assert {s.span_type for s in tr.spans} >= {"http", "retrieval"}


def test_datawise_executor_maps_contract_and_classifies_errors(monkeypatch):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/login"):
            return httpx.Response(200, json={"access_token": "t"})
        q = req.read().decode()
        if "boom" in q:
            return httpx.Response(503, json={})
        return httpx.Response(200, json={
            "status": "answered", "plan": {}, "sql": "SELECT 1", "validation": {"ok": True, "issues": []},
            "columns": ["region", "revenue"], "rows": [["North", 1.5]], "row_count": 1, "insight": "North leads.",
            "clarification": None, "rejection_reason": None, "provider": "local", "latency_ms": 3})

    monkeypatch.setattr(targets_mod.httpx, "Client", _mock_client(handler))
    monkeypatch.setenv("DATAWISE_EMAIL", "u@x.io")
    monkeypatch.setenv("DATAWISE_PASSWORD", "pw")
    ex = targets_mod.build_executor({"target": {"kind": "http_datawise", "config": {"base_url": "http://dw"}}})
    out = ex.execute(CaseData(external_id="1", input="revenue by region"), TraceRecorder("t"), 5)
    assert out.status == "answered" and out.rows == [["North", 1.5]] and out.sql == "SELECT 1"
    with pytest.raises(TransientProviderError):
        ex.execute(CaseData(external_id="2", input="boom"), TraceRecorder("t"), 5)


def test_http_target_without_credentials_errors(monkeypatch):
    monkeypatch.delenv("NEXUS_EMAIL", raising=False)
    monkeypatch.delenv("NEXUS_PASSWORD", raising=False)
    ex = targets_mod.build_executor({"target": {"kind": "http_nexus", "config": {"base_url": "http://nexus",
                                                                                   "email_env": "NOPE_EMAIL"}}})
    from app.llm.base import ProviderError

    with pytest.raises(ProviderError, match="credentials"):
        ex.execute(CaseData(external_id="1", input="q"), TraceRecorder("t"), 5)
