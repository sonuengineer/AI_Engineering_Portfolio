"""Reproducible demo seed for EvalOps AI.

Creates: demo org + users (admin/member/viewer, password from DEMO_USER_PASSWORD), a second org for
tenant-isolation demos, projects, datasets (from ../benchmarks/*.jsonl), prompts, model configs,
targets, evaluators, experiments -- and then EXECUTES demo runs with the deterministic `local` and
`mock_scripted` providers. Every stored score comes from actually running the engine.

NEXUS / DATAWISE runs are executed only if those APIs answer /healthz and credentials are set
(NEXUS_EMAIL/NEXUS_PASSWORD, DATAWISE_EMAIL/DATAWISE_PASSWORD); otherwise their targets are left
configured with no runs.

Usage (from backend/):
    uv run python -m scripts.seed            # seed if empty
    uv run python -m scripts.seed --reset    # wipe all EvalOps data first
    uv run python -m scripts.seed --skip-runs
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import Base, session_scope
from app.core.security import hash_password
from app.engine.runner import execute_run
from app.models import (
    Dataset,
    EvaluatorConfig,
    Experiment,
    ModelConfig,
    Org,
    Project,
    PromptTemplate,
    PromptVersion,
    Run,
    Target,
    User,
)
from app.services.datasets import create_version, parse_jsonl
from app.services.runs import create_runs

BENCH = Path(__file__).resolve().parents[2] / "benchmarks"
DEMO_EMAILS = {"admin": "admin@evalops.local", "member": "member@evalops.local", "viewer": "viewer@evalops.local"}


def reset(session: Session) -> None:
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    session.execute(text(f"TRUNCATE {tables} CASCADE"))


def _dataset(session: Session, org: Org, project: Project, name: str, desc: str, filename: str) -> Any:
    ds = Dataset(org_id=org.id, project_id=project.id, name=name, description=desc)
    session.add(ds)
    session.flush()
    cases = parse_jsonl((BENCH / filename).read_bytes(), max_cases=10000)
    return create_version(session, ds, cases, notes=f"seeded from benchmarks/{filename}", source_filename=filename)


def _prompt(session: Session, org: Org, project: Project, name: str, system: str, user_t: str) -> PromptVersion:
    t = PromptTemplate(org_id=org.id, project_id=project.id, name=name, description="seeded")
    session.add(t)
    session.flush()
    pv = PromptVersion(org_id=org.id, template_id=t.id, version=1, system_prompt=system, user_template=user_t,
                       content_hash=hashlib.sha256(f"{system}\x00{user_t}".encode()).hexdigest())
    session.add(pv)
    session.flush()
    return pv


def _mc(session: Session, org: Org, project: Project, name: str, provider: str, model: str,
        params: dict[str, Any] | None = None, pin: float = 0.0, pout: float = 0.0) -> ModelConfig:
    mc = ModelConfig(org_id=org.id, project_id=project.id, name=name, provider=provider, model=model,
                     params=params or {}, price_in_per_1k=pin, price_out_per_1k=pout)
    session.add(mc)
    session.flush()
    return mc


def _target(session: Session, org: Org, project: Project, name: str, kind: str, mc: ModelConfig | None = None,
            pv: PromptVersion | None = None, config: dict[str, Any] | None = None) -> Target:
    t = Target(org_id=org.id, project_id=project.id, name=name, kind=kind, model_config_id=mc.id if mc else None,
               prompt_version_id=pv.id if pv else None, config=config or {})
    session.add(t)
    session.flush()
    return t


EvalSpec = tuple[str, str, str, dict[str, Any], float | None]


def _evals(session: Session, org: Org, project: Project, specs: list[EvalSpec]) -> list[EvaluatorConfig]:
    out = []
    for name, type_, kind, params, threshold in specs:
        ev = EvaluatorConfig(org_id=org.id, project_id=project.id, name=name, type=type_, kind=kind, params=params,
                             threshold=threshold, gating=kind == "deterministic")
        session.add(ev)
        out.append(ev)
    session.flush()
    return out


def _reachable(base_url: str) -> bool:
    try:
        return httpx.get(base_url.rstrip("/") + "/healthz", timeout=3.0).status_code == 200
    except httpx.HTTPError:
        return False


def seed(skip_runs: bool = False) -> dict[str, Any]:
    s = get_settings()
    password = s.demo_user_password or os.environ.get("DEMO_USER_PASSWORD")
    if not password or len(password) < 10:
        sys.exit("DEMO_USER_PASSWORD must be set (>= 10 chars); see .env.example")
    planned: list[dict[str, Any]] = []
    with session_scope() as db:
        if db.scalar(select(Org).where(Org.slug == "acme-eval")):
            print("already seeded (use --reset to rebuild)")
            return {"status": "exists"}
        org = Org(name="Acme Eval Labs (demo)", slug="acme-eval")
        other = Org(name="Globex Research (isolation demo)", slug="globex")
        db.add_all([org, other])
        db.flush()
        pw = hash_password(password)
        users = {role: User(org_id=org.id, email=email, display_name=f"Demo {role}", password_hash=pw, role=role)
                 for role, email in DEMO_EMAILS.items()}
        db.add_all(users.values())
        db.add(User(org_id=other.id, email="admin@globex.local", display_name="Globex admin", password_hash=pw,
                    role="admin"))
        db.flush()
        admin = users["admin"]

        # ---------------------------------------------------------------- support QA (RAG-style) demo
        p1 = Project(org_id=org.id, name="Support Assistant QA", slug="support-qa",
                     description="RAG-style QA over a synthetic help-center KB. Demo runs use the deterministic "
                                 "local adapter and scripted outputs (not real LLMs).")
        db.add(p1)
        db.flush()
        dv1 = _dataset(db, org, p1, "support_faq", "22 help-center questions with contexts, citations and scripted "
                       "v1/v2 outputs", "demo_support_qa_v1.jsonl")
        pv1 = _prompt(db, org, p1, "grounded-answer",
                      "Answer using only the provided context. Cite the context ids you used.",
                      "Context:\n{{contexts}}\n\nQuestion: {{input}}\nAnswer:")
        mc_local = _mc(db, org, p1, "local-extractive", "local", "local-extractive-v1")
        mc_v1 = _mc(db, org, p1, "scripted-v1 (baseline fixture)", "mock_scripted", "scripted", {"script": "v1"},
                    0.00015, 0.0006)
        mc_v2 = _mc(db, org, p1, "scripted-v2 (regressed fixture)", "mock_scripted", "scripted", {"script": "v2"},
                    0.00015, 0.0006)
        _mc(db, org, p1, "gemini-2.5-flash (needs GEMINI_API_KEY)", "gemini", "gemini-2.5-flash", {"temperature": 0},
            0.0003, 0.0025)
        t_local = _target(db, org, p1, "Local extractive adapter", "llm", mc_local, pv1)
        t_v1 = _target(db, org, p1, "Scripted assistant v1", "llm", mc_v1, pv1)
        t_v2 = _target(db, org, p1, "Scripted assistant v2", "llm", mc_v2, pv1)
        ev1 = _evals(db, org, p1, [
            ("answer_match", "normalized_match", "deterministic", {"allow_containment": True}, None),
            ("keywords", "contains", "deterministic", {}, 1.0),
            ("citations", "citation_correctness", "deterministic", {}, 1.0),
            ("context_recall", "context_recall_lexical", "deterministic", {"overlap": 0.5}, 1.0),
            ("groundedness", "groundedness_lexical", "deterministic", {"overlap": 0.6}, 0.8),
            ("latency_under_2s", "latency_threshold", "deterministic", {"max_ms": 2000}, None),
            ("cost_under_1c", "cost_threshold", "deterministic", {"max_usd": 0.01}, None),
            ("judge_correctness", "llm_judge", "judge", {"criteria": "factual correctness vs reference"}, 4.0),
        ])
        exp1 = Experiment(org_id=org.id, project_id=p1.id, name="Assistant v1 vs v2 regression check",
                          description="Scripted fixtures: v2 intentionally breaks 8 cases.", dataset_id=dv1.dataset_id)
        db.add(exp1)
        db.flush()
        ev1_ids = [e.id for e in ev1]
        planned += [
            dict(project_id=p1.id, dataset_version_id=dv1.id, target_ids=[t_local.id], evaluator_ids=ev1_ids,
                 experiment_id=exp1.id, label="local-extractive baseline"),
            dict(project_id=p1.id, dataset_version_id=dv1.id, target_ids=[t_v1.id], evaluator_ids=ev1_ids,
                 experiment_id=exp1.id, label="scripted v1 (baseline)"),
            dict(project_id=p1.id, dataset_version_id=dv1.id, target_ids=[t_v2.id], evaluator_ids=ev1_ids,
                 experiment_id=exp1.id, label="scripted v2 (candidate)"),
        ]

        # ---------------------------------------------------------------- structured extraction demo
        p2 = Project(org_id=org.id, name="Invoice Extraction", slug="invoice-extraction",
                     description="Structured JSON extraction checks (schema validity, numeric tolerance).")
        db.add(p2)
        db.flush()
        dv2 = _dataset(db, org, p2, "invoices", "10 invoice snippets with expected JSON", "demo_extraction_v1.jsonl")
        pv2 = _prompt(db, org, p2, "extract-invoice", "Extract vendor, invoice_number, total, currency as JSON.",
                      "{{input}}")
        mc2a = _mc(db, org, p2, "scripted-v1", "mock_scripted", "scripted", {"script": "v1"})
        mc2b = _mc(db, org, p2, "scripted-v2", "mock_scripted", "scripted", {"script": "v2"})
        t2a = _target(db, org, p2, "Extractor v1 (scripted)", "llm", mc2a, pv2)
        t2b = _target(db, org, p2, "Extractor v2 (scripted)", "llm", mc2b, pv2)
        ev2 = _evals(db, org, p2, [
            ("schema_valid", "json_schema_valid", "deterministic", {}, None),
            ("total_within_1pct", "numeric_tolerance", "deterministic", {"json_field": "total", "rel_tol": 0.01}, None),
            ("exact_json", "exact_match", "deterministic", {}, None),
            ("invoice_number_format", "regex", "deterministic", {"pattern": "INV-[0-9]{4}"}, None),
        ])
        exp2 = Experiment(org_id=org.id, project_id=p2.id, name="Extractor v1 vs v2", dataset_id=dv2.dataset_id)
        db.add(exp2)
        db.flush()
        planned += [
            dict(project_id=p2.id, dataset_version_id=dv2.id, target_ids=[t2a.id, t2b.id],
                 evaluator_ids=[e.id for e in ev2], experiment_id=exp2.id, label=""),
        ]

        # ---------------------------------------------------------------- NEXUS AI (black-box HTTP)
        p3 = Project(org_id=org.id, name="NEXUS AI RAG benchmark", slug="nexus-rag",
                     description="Benchmarks NEXUS AI /api/v1/chat/ask as a black-box HTTP target.")
        db.add(p3)
        db.flush()
        dv3 = _dataset(db, org, p3, "nexus_rag_v1", "32 questions over the NEXUS synthetic seed corpus",
                       "nexus_rag_v1.jsonl")
        t3 = _target(db, org, p3, "NEXUS AI (local dev)", "http_nexus", config={
            "base_url_env": "NEXUS_BASE_URL", "email_env": "NEXUS_EMAIL", "password_env": "NEXUS_PASSWORD",
            "citation_key": "document_title"})
        ev3 = _evals(db, org, p3, [
            ("citations", "citation_correctness", "deterministic", {}, 1.0),
            ("keywords", "contains", "deterministic", {}, 1.0),
            ("unanswerable_refusal", "regex", "deterministic", {}, None),
            ("no_leak_or_injection", "not_contains", "deterministic", {}, None),
            ("context_precision", "context_precision_lexical", "deterministic", {"overlap": 0.5}, 0.3),
            ("context_recall", "context_recall_lexical", "deterministic", {"overlap": 0.5}, 1.0),
            ("groundedness", "groundedness_lexical", "deterministic", {"overlap": 0.6}, 0.8),
            ("latency_under_10s", "latency_threshold", "deterministic", {"max_ms": 10000}, None),
        ])
        nexus_plan = dict(project_id=p3.id, dataset_version_id=dv3.id, target_ids=[t3.id],
                          evaluator_ids=[e.id for e in ev3], label="NEXUS benchmark (live HTTP)")

        # ---------------------------------------------------------------- DATAWISE AI (black-box HTTP)
        p4 = Project(org_id=org.id, name="DATAWISE AI SQL benchmark", slug="datawise-sql",
                     description="Benchmarks DATAWISE AI /api/v1/questions/ask (answerable, ambiguous, unsafe).")
        db.add(p4)
        db.flush()
        dv4 = _dataset(db, org, p4, "datawise_sql_v1", "18 answerable + 5 ambiguous + 7 unsafe questions",
                       "datawise_sql_v1.jsonl")
        t4 = _target(db, org, p4, "DATAWISE AI (local dev)", "http_datawise", config={
            "base_url_env": "DATAWISE_BASE_URL", "email_env": "DATAWISE_EMAIL", "password_env": "DATAWISE_PASSWORD"})
        ev4 = _evals(db, org, p4, [
            ("status", "status_match", "deterministic", {}, None),
            ("result_rows", "sql_result_match", "deterministic", {"round_digits": 2}, None),
            ("latency_under_10s", "latency_threshold", "deterministic", {"max_ms": 10000}, None),
        ])
        datawise_plan = dict(project_id=p4.id, dataset_version_id=dv4.id, target_ids=[t4.id],
                             evaluator_ids=[e.id for e in ev4], label="DATAWISE benchmark (live HTTP)")

        # Globex org: one project so tenant isolation is visible
        db.add(Project(org_id=other.id, name="Globex private project", slug="globex-private",
                       description="Must never be visible to Acme users."))
        org_id, admin_id = org.id, admin.id

    summary: dict[str, Any] = {"runs": []}
    if skip_runs:
        return summary
    if _reachable(s.nexus_base_url) and s.nexus_email and s.nexus_password:
        planned.append(nexus_plan)
    else:
        print(f"NEXUS not reachable at {s.nexus_base_url} or credentials unset: target configured, no run")
    if _reachable(s.datawise_base_url) and s.datawise_email and s.datawise_password:
        planned.append(datawise_plan)
    else:
        print(f"DATAWISE not reachable at {s.datawise_base_url} or credentials unset: target configured, no run")
    for plan in planned:
        with session_scope() as db:
            runs = create_runs(db, org_id=org_id, user_id=admin_id, concurrency=4, timeout_s=60, max_retries=2,
                               seed=42, **plan)
            ids = [r.id for r in runs]
            for r in runs:
                r.status = "running"  # claimed directly by the seed process
        for rid in ids:
            status = execute_run(rid)
            with session_scope() as db:
                run = db.get(Run, rid)
                assert run is not None
                print(f"run {rid} [{run.label}] -> {status}; overall_pass_rate="
                      f"{run.summary.get('overall_pass_rate')} error_rate={run.summary.get('error_rate')}")
                summary["runs"].append({"id": str(rid), "label": run.label, "status": status})
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--skip-runs", action="store_true")
    args = ap.parse_args()
    if args.reset:
        with session_scope() as db:
            reset(db)
        print("reset: all EvalOps tables truncated")
    seed(skip_runs=args.skip_runs)


if __name__ == "__main__":
    main()
