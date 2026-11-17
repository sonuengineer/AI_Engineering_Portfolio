"""API integration tests (FastAPI TestClient + real Postgres)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.ratelimit import limiter
from app.main import create_app
from app.worker import process_available

from conftest import PASSWORD
from helpers import CASES, build_project, jsonl


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


def login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json()["database"] == "ok"


def test_auth_errors_use_envelope(client, org_a):
    r = client.post("/api/v1/auth/login", json={"email": "admin@alpha.test", "password": "wrong-password"})
    assert r.status_code == 401
    body = r.json()["error"]
    assert body["code"] == "invalid_credentials" and body["request_id"] == r.headers["x-request-id"]
    assert client.get("/api/v1/projects").json()["error"]["code"] == "unauthorized"
    assert client.get("/api/v1/projects", headers={"Authorization": "Bearer garbage"}).status_code == 401
    r = client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"


def test_roles(client, org_a):
    viewer = login(client, "viewer@alpha.test")
    member = login(client, "member@alpha.test")
    admin = login(client, "admin@alpha.test")
    assert client.post("/api/v1/projects", json={"name": "P", "slug": "p"}, headers=viewer).status_code == 403
    assert client.post("/api/v1/projects", json={"name": "P", "slug": "p"}, headers=member).status_code == 201
    assert client.post("/api/v1/projects", json={"name": "P", "slug": "p"}, headers=member).status_code == 409
    assert client.get("/api/v1/audit-events", headers=member).status_code == 403
    events = client.get("/api/v1/audit-events", headers=admin).json()
    assert any(e["action"] == "project.create" for e in events)
    r = client.post("/api/v1/users", json={"email": "new@alpha.test", "password": "long-enough-pw", "role": "viewer"},
                    headers=admin)
    assert r.status_code == 201 and r.json()["role"] == "viewer"


def test_dataset_upload_validation_and_versioning(client, org_a):
    h = login(client, "member@alpha.test")
    pid = client.post("/api/v1/projects", json={"name": "P", "slug": "p"}, headers=h).json()["id"]
    did = client.post(f"/api/v1/projects/{pid}/datasets", json={"name": "d"}, headers=h).json()["id"]
    url = f"/api/v1/datasets/{did}/versions"
    r = client.post(url, files={"file": ("cases.csv", b"a,b", "text/csv")}, headers=h)
    assert r.status_code == 422 and "jsonl" in r.json()["error"]["message"]
    r = client.post(url, files={"file": ("cases.jsonl", b'{"input": 1}\n', "application/jsonl")}, headers=h)
    assert r.status_code == 422 and "line 1" in r.json()["error"]["message"]
    r = client.post(url, files={"file": ("cases.jsonl", jsonl(CASES), "application/jsonl")}, headers=h)
    assert r.status_code == 201 and r.json()["version"] == 1 and r.json()["case_count"] == 3
    again = client.post(url, files={"file": ("cases.jsonl", jsonl(CASES), "application/jsonl")}, headers=h)
    assert again.json()["id"] == r.json()["id"]  # identical content -> same immutable version
    v2 = client.post(url, files={"file": ("cases.jsonl", jsonl(CASES[:2]), "application/jsonl")}, headers=h)
    assert v2.json()["version"] == 2
    cases = client.get(f"/api/v1/dataset-versions/{r.json()['id']}/cases?limit=2", headers=h)
    assert len(cases.json()) == 2 and cases.headers["x-total-count"] == "3"
    assert cases.json()[0]["metadata"]["expected_keywords"] == ["30 days"]


def test_upload_size_limit(client, org_a, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_bytes", 100)
    h = login(client, "member@alpha.test")
    pid = client.post("/api/v1/projects", json={"name": "P", "slug": "p"}, headers=h).json()["id"]
    did = client.post(f"/api/v1/projects/{pid}/datasets", json={"name": "d"}, headers=h).json()["id"]
    r = client.post(f"/api/v1/datasets/{did}/versions", files={"file": ("c.jsonl", jsonl(CASES), "application/jsonl")},
                    headers=h)
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_target_config_rejects_secrets(client, org_a):
    h = login(client, "member@alpha.test")
    pid = client.post("/api/v1/projects", json={"name": "P", "slug": "p"}, headers=h).json()["id"]
    bad = client.post(f"/api/v1/projects/{pid}/targets", headers=h,
                      json={"name": "n", "kind": "http_nexus", "config": {"password": "hunter2"}})
    assert bad.status_code == 422 and "secret" in bad.json()["error"]["message"]
    ok = client.post(f"/api/v1/projects/{pid}/targets", headers=h,
                     json={"name": "n", "kind": "http_nexus", "config": {"password_env": "NEXUS_PASSWORD"}})
    assert ok.status_code == 201
    assert client.post(f"/api/v1/projects/{pid}/evaluators", headers=h,
                       json={"name": "e", "type": "does_not_exist"}).status_code == 422
    judge = client.post(f"/api/v1/projects/{pid}/evaluators", headers=h,
                        json={"name": "j", "type": "llm_judge", "gating": True}).json()
    assert judge["kind"] == "judge" and judge["gating"] is False  # judges never gate


def test_run_lifecycle_results_compare_traces_reports(client, org_a):
    proj = build_project(org_a["org_id"])
    h = login(client, "member@alpha.test")
    body = {"project_id": str(proj["project_id"]), "dataset_version_id": str(proj["dv_id"]),
            "target_ids": [str(proj["targets"]["good"]), str(proj["targets"]["bad"])],
            "evaluator_ids": [str(e) for e in proj["evaluators"]], "label": "api run", "seed": 3}
    r = client.post("/api/v1/runs", json=body, headers=h)
    assert r.status_code == 202
    good, bad = r.json()["run_ids"]
    assert client.get(f"/api/v1/runs/{good}", headers=h).json()["status"] == "queued"
    assert process_available("api-test") == 2
    detail = client.get(f"/api/v1/runs/{good}", headers=h).json()
    assert detail["status"] == "completed" and detail["is_deterministic_provider"] is True
    assert detail["progress_done"] == 3 and detail["summary"]["overall_pass_rate"] == 1.0
    listed = client.get(f"/api/v1/runs?project_id={proj['project_id']}", headers=h).json()
    assert {x["id"] for x in listed} == {good, bad}

    failed = client.get(f"/api/v1/runs/{bad}/results?failed_only=true", headers=h).json()
    assert [c["external_id"] for c in failed] == ["c1", "c3"]
    judge = next(sc for sc in failed[0]["scores"] if sc["metric"] == "judge")
    assert judge["status"] == "skipped" and judge["is_estimate"] is True

    cmp = client.get(f"/api/v1/compare?baseline={good}&candidate={bad}", headers=h).json()
    assert cmp["has_regression"] and cmp["cases"]["newly_failing"] == ["c1", "c3"]

    traces = client.get(f"/api/v1/runs/{good}/traces", headers=h).json()
    assert len(traces) == 3
    t = client.get(f"/api/v1/traces/{traces[0]['id']}", headers=h).json()
    assert t["spans"] and {"prompt", "model_call"} <= {s["span_type"] for s in t["spans"]}

    rj = client.get(f"/api/v1/runs/{bad}/report.json", headers=h)
    assert rj.status_code == 200 and json.loads(rj.text)["run"]["id"] == bad
    md = client.get(f"/api/v1/runs/{bad}/report.md", headers=h).text
    assert "# EvalOps run report" in md and "Failing cases (2)" in md and "not a real LLM" in md
    csv_text = client.get(f"/api/v1/runs/{bad}/results.csv", headers=h).text
    assert csv_text.splitlines()[0].startswith("external_id,passed") and len(csv_text.splitlines()) == 4


def test_tenant_isolation(client, org_a, org_b):
    proj = build_project(org_a["org_id"])
    a = login(client, "member@alpha.test")
    b = login(client, "admin@beta.test")
    body = {"project_id": str(proj["project_id"]), "dataset_version_id": str(proj["dv_id"]),
            "target_ids": [str(proj["targets"]["good"])], "evaluator_ids": []}
    run_id = client.post("/api/v1/runs", json=body, headers=a).json()["run_ids"][0]
    process_available("w")
    pid = proj["project_id"]
    assert client.get("/api/v1/projects", headers=b).json() == []
    for path in [f"/api/v1/projects/{pid}", f"/api/v1/projects/{pid}/datasets", f"/api/v1/projects/{pid}/targets",
                 f"/api/v1/runs/{run_id}", f"/api/v1/runs/{run_id}/results", f"/api/v1/runs/{run_id}/report.md",
                 f"/api/v1/dataset-versions/{proj['dv_id']}/cases", f"/api/v1/datasets/{proj['dataset_id']}"]:
        r = client.get(path, headers=b)
        assert r.status_code == 404, path
    assert client.get("/api/v1/runs", headers=b).json() == []
    trace_id = client.get(f"/api/v1/runs/{run_id}/traces", headers=a).json()[0]["id"]
    assert client.get(f"/api/v1/traces/{trace_id}", headers=b).status_code == 404
    assert client.get(f"/api/v1/compare?baseline={run_id}&candidate={run_id}", headers=b).status_code == 404
    # org B cannot launch a run on org A resources
    assert client.post("/api/v1/runs", json=body, headers=b).status_code == 404


def test_rate_limit(client, org_a, monkeypatch):
    from app.core.config import get_settings

    h = login(client, "viewer@alpha.test")
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 3)
    limiter.reset()
    codes = [client.get("/api/v1/projects", headers=h).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[-1] == 429
    assert client.get("/api/v1/projects", headers=h).json()["error"]["code"] == "rate_limited"
