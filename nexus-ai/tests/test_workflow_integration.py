import pytest
from conftest import get_user
from sqlalchemy import select

from app.agents import investigation
from app.core.config import get_settings
from app.models import ApprovalRequest, OutboxMessage, WorkflowRun, WorkflowStep
from app.services.workflows import execute_run, resume_run, start_run
from app.tools.registry import ApprovalRequired, ToolContext, execute

GOAL = "Investigate declining purchases among our top ten customers"


@pytest.fixture(scope="module")
def run(client, manager):
    r = client.post("/api/v1/workflows", headers=manager, json={"goal": GOAL})
    assert r.status_code == 202
    # TestClient runs background tasks before returning, so the run is finished here.
    return client.get(f"/api/v1/workflows/{r.json()['id']}", headers=manager).json()


def test_investigation_completes_with_all_agents(run):
    assert run["status"] == "awaiting_approval", run["error"]
    assert [s["name"] for s in run["steps"]] == [
        "supervisor",
        "data_agent",
        "research_agent",
        "analysis_agent",
        "report_agent",
        "action_agent",
    ]
    assert all(s["status"] == "completed" for s in run["steps"])
    assert run["tokens_used"] > 0 and run["tokens_used"] <= run["token_budget"]


def test_report_separates_evidence_from_hypotheses_and_matches_seed(run):
    md = run["report"]["markdown"]
    assert "EVIDENCE:" in md and "HYPOTHESIS (" in md and "Limitations" in md
    findings = {f["customer_name"]: f for f in run["report"]["analysis"]["findings"]}
    # Seeded causes must be recovered from the records.
    assert "pricing" in findings["Northwind Fabrication"]["hypotheses"][0]["statement"].lower()
    assert any("quality" in h["statement"].lower() for h in findings["Harbor Marine Systems"]["hypotheses"])
    assert any("delivery" in h["statement"].lower() for h in findings["Bluepeak Energy"]["hypotheses"])
    assert any("budget" in h["statement"].lower() for h in findings["Summit Foods Processing"]["hypotheses"])
    assert any("contract" in h["statement"].lower() for h in findings["Ironclad Construction"]["hypotheses"])
    # Growing customer must not be reported as declining.
    assert "Riverside Medical Devices" not in findings
    # Every evidence item carries a source that was actually gathered.
    for f in findings.values():
        assert all(e["source"] for e in f["evidence"])


def test_revenue_numbers_match_database(run, db):
    from sqlalchemy import text

    nw = next(c for c in run["report"]["declining"] if c["name"] == "Northwind Fabrication")
    w = nw["window"]
    recent = db.execute(
        text(
            "SELECT COALESCE(SUM(amount),0) FROM erp_orders o JOIN crm_customers c ON c.id=o.customer_id "
            "WHERE c.name='Northwind Fabrication' AND o.status='completed' "
            "AND o.order_date > :mid AND o.order_date <= :end"
        ),
        {"mid": w["mid"], "end": w["end"]},
    ).scalar()
    assert round(float(recent), 2) == round(nw["recent_revenue"], 2)


def test_drafts_require_approval_and_never_auto_send(run, db):
    approvals = run["approvals"]
    assert len(approvals) >= 5 and all(a["status"] == "pending" for a in approvals)
    assert db.scalar(select(OutboxMessage).where(OutboxMessage.approval_id.in_([a["id"] for a in approvals]))) is None
    body = approvals[0]["payload"]["body"]
    assert "%" not in body and "revenue" not in body.lower()  # no internal numbers leaked to customers


def test_send_email_tool_blocked_without_approval(db):
    user = get_user(db, "manager@acme.example")
    with pytest.raises(ApprovalRequired):
        execute(
            "send_email",
            {"to": "a@b.example", "subject": "s", "body": "b", "idempotency_key": "k" * 10},
            ToolContext(db=db, user=user),
        )


def test_analyst_cannot_approve(client, analyst, run):
    r = client.post(f"/api/v1/approvals/{run['approvals'][0]['id']}/approve", headers=analyst, json={})
    assert r.status_code == 403


def test_approve_sends_once_idempotently_and_reject(client, manager, run, db):
    a0, a1 = run["approvals"][0]["id"], run["approvals"][1]["id"]
    r = client.post(
        f"/api/v1/approvals/{a0}/approve", headers=manager, json={"note": "ok", "subject": "Edited subject"}
    )
    assert r.status_code == 200 and r.json()["status"] == "executed"
    again = client.post(f"/api/v1/approvals/{a0}/approve", headers=manager, json={})
    assert again.json()["status"] == "executed"
    msgs = list(db.scalars(select(OutboxMessage).where(OutboxMessage.approval_id == a0)))
    assert len(msgs) == 1 and msgs[0].subject == "Edited subject"
    rj = client.post(f"/api/v1/approvals/{a1}/reject", headers=manager, json={"note": "not now"})
    assert rj.json()["status"] == "rejected"
    assert client.post(f"/api/v1/approvals/{a1}/approve", headers=manager, json={}).status_code == 409


def test_run_completes_when_all_approvals_decided(client, manager, run):
    for a in run["approvals"]:
        client.post(f"/api/v1/approvals/{a['id']}/reject", headers=manager, json={})
    assert client.get(f"/api/v1/workflows/{run['id']}", headers=manager).json()["status"] == "completed"


def test_cross_tenant_cannot_see_run_or_approvals(client, globex, run):
    assert client.get(f"/api/v1/workflows/{run['id']}", headers=globex).status_code == 404
    assert client.get("/api/v1/approvals", headers=globex).json() == []
    assert (
        client.post(f"/api/v1/approvals/{run['approvals'][2]['id']}/approve", headers=globex, json={}).status_code
        == 404
    )


def test_unsupported_goal_fails_cleanly(client, manager):
    r = client.post("/api/v1/workflows", headers=manager, json={"goal": "Write a poem about the ocean waves"})
    run = client.get(f"/api/v1/workflows/{r.json()['id']}", headers=manager).json()
    assert run["status"] == "failed" and "only supports" in run["error"]


def test_budget_exceeded(db, monkeypatch):
    user = get_user(db, "manager@acme.example")
    run = start_run(db, user, GOAL)
    run.token_budget = 400  # enough for the plan, not for the analysis
    db.commit()
    execute_run(run.id)
    db.expire_all()
    r = db.get(WorkflowRun, run.id)
    assert r.status == "budget_exceeded" and "budget" in r.error


def test_transient_failure_is_retried(db, monkeypatch):
    calls = {"n": 0}
    real = investigation.AGENTS["research_agent"]

    def flaky(ctx, state):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("simulated connector outage")
        return real(ctx, state)

    monkeypatch.setitem(investigation.AGENTS, "research_agent", flaky)
    user = get_user(db, "manager@acme.example")
    run = start_run(db, user, GOAL)
    execute_run(run.id)
    db.expire_all()
    step = db.scalar(select(WorkflowStep).where(WorkflowStep.run_id == run.id, WorkflowStep.name == "research_agent"))
    assert step.status == "completed" and step.attempts == 2
    assert db.get(WorkflowRun, run.id).status == "awaiting_approval"


def test_failed_run_resumes_from_checkpoint(db, monkeypatch):
    def broken(ctx, state):
        raise ValueError("bad input -- non retryable")

    real = investigation.AGENTS["report_agent"]
    monkeypatch.setitem(investigation.AGENTS, "report_agent", broken)
    user = get_user(db, "manager@acme.example")
    run = start_run(db, user, GOAL)
    execute_run(run.id)
    db.expire_all()
    assert db.get(WorkflowRun, run.id).status == "failed"
    steps = {s.name: s for s in db.scalars(select(WorkflowStep).where(WorkflowStep.run_id == run.id))}
    assert steps["analysis_agent"].status == "completed" and steps["report_agent"].status == "failed"
    finished_before = steps["data_agent"].finished_at

    monkeypatch.setitem(investigation.AGENTS, "report_agent", real)
    resume_run(db, user, run.id)
    execute_run(run.id)
    db.expire_all()
    assert db.get(WorkflowRun, run.id).status == "awaiting_approval"
    steps = {s.name: s for s in db.scalars(select(WorkflowStep).where(WorkflowStep.run_id == run.id))}
    assert steps["data_agent"].finished_at == finished_before  # completed step was not re-run
    assert steps["report_agent"].status == "completed"


def test_draft_tool_is_idempotent_per_run(db):
    n = db.scalar(select(ApprovalRequest.id).limit(1))
    assert n is not None
    keys = [a.idempotency_key for a in db.scalars(select(ApprovalRequest))]
    assert len(keys) == len(set(keys))


def test_step_timeout_setting_exists():
    assert get_settings().workflow_step_timeout_s > 0


def test_shared_documents_do_not_create_false_hypotheses(run):
    findings = {f["customer_name"]: f for f in run["report"]["analysis"]["findings"]}
    nw = findings["Northwind Fabrication"]
    assert not any("delivery" in h["statement"].lower() for h in nw["hypotheses"])
    assert all("Bluepeak" not in e["statement"] for e in nw["evidence"])


def test_startup_recovery_only_marks_stale_runs(db):
    from datetime import timedelta

    from app.models.base import utcnow
    from app.services.workflows import mark_interrupted_runs, stale_after_seconds

    user = get_user(db, "manager@acme.example")
    fresh = start_run(db, user, GOAL)  # owned by a live replica: must be left alone
    stale = start_run(db, user, GOAL)
    stale.created_at = utcnow() - timedelta(seconds=stale_after_seconds() + 5)
    db.commit()
    mark_interrupted_runs()
    db.expire_all()
    assert db.get(WorkflowRun, fresh.id).status == "running"
    assert db.get(WorkflowRun, stale.id).status == "interrupted"
    fresh.status = "failed"  # tidy up so other tests are unaffected
    db.commit()
