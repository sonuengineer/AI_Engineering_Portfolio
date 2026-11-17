from conftest import PASSWORD
from sqlalchemy import select

from app.ingestion.jobs import drain
from app.ingestion.storage import get_storage
from app.models import AuditEvent, Document


def test_health_and_ready(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    r = client.get("/readyz")
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_login_failure_is_generic_and_audited(client, db):
    r1 = client.post("/api/v1/auth/login", json={"email": "manager@acme.example", "password": "wrong"})
    r2 = client.post("/api/v1/auth/login", json={"email": "nobody@acme.example", "password": "wrong"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"]["message"] == r2.json()["error"]["message"]
    assert "request_id" in r1.json()["error"] and r1.headers["x-request-id"]
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "auth.login", AuditEvent.outcome == "denied"))


def test_requires_auth(client):
    assert client.get("/api/v1/documents").status_code == 401
    assert client.get("/api/v1/documents", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_me_reports_provider(client, analyst):
    me = client.get("/api/v1/auth/me", headers=analyst).json()
    assert me["role"] == "analyst" and me["org_name"] == "Acme Industrial Supply" and me["llm_provider"] == "local"


def test_ask_contract_used_by_evalops(client, analyst):
    r = client.post("/api/v1/chat/ask", headers=analyst, json={"question": "When did the Ironclad contract expire?"})
    assert r.status_code == 200
    body = r.json()
    for key in ("conversation_id", "answer", "provider", "model", "citations", "contexts", "usage", "latency_ms"):
        assert key in body
    assert "30 June 2026" in body["answer"]
    assert body["citations"][0]["document_title"].startswith("Ironclad")
    assert {"chunk_id", "document_id", "document_title", "page", "snippet"} <= set(body["citations"][0])
    # follow-up in the same conversation is stored as history
    r2 = client.post(
        "/api/v1/chat/ask",
        headers=analyst,
        json={"question": "Which quotation is pending for Ironclad?", "conversation_id": body["conversation_id"]},
    )
    assert r2.json()["conversation_id"] == body["conversation_id"]
    msgs = client.get(f"/api/v1/conversations/{body['conversation_id']}/messages", headers=analyst).json()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]


def test_pdf_answers_have_page_citations(client, analyst):
    body = client.post(
        "/api/v1/chat/ask", headers=analyst, json={"question": "What was the root cause of the adhesion failure?"}
    ).json()
    pages = {c["page"] for c in body["citations"] if c["document_title"].startswith("Harbor Marine")}
    assert 2 in pages


def test_conversation_isolation_between_users(client, analyst, manager):
    cid = client.post("/api/v1/chat/ask", headers=analyst, json={"question": "payment terms?"}).json()[
        "conversation_id"
    ]
    assert client.get(f"/api/v1/conversations/{cid}/messages", headers=manager).status_code == 404
    r = client.post("/api/v1/chat/ask", headers=manager, json={"question": "x y z", "conversation_id": cid})
    assert r.status_code == 404


def test_tenant_isolation_documents_and_retrieval(client, analyst, globex, db):
    gx_doc = db.scalar(select(Document).where(Document.title == "Globex Confidential Pricing"))
    assert client.get(f"/api/v1/documents/{gx_doc.id}", headers=analyst).status_code == 404
    titles = [d["title"] for d in client.get("/api/v1/documents", headers=analyst).json()]
    assert "Globex Confidential Pricing" not in titles
    body = client.post(
        "/api/v1/chat/ask", headers=analyst, json={"question": "What is the Globex margin target for Electrical?"}
    ).json()
    assert all("Globex" not in c["document_title"] for c in body["citations"])
    gbody = client.post(
        "/api/v1/chat/ask", headers=globex, json={"question": "What is the Globex margin target for Electrical?"}
    ).json()
    assert "41 percent" in gbody["answer"]


def test_upload_flow_and_validation(client, analyst, viewer, db):
    files = {
        "file": (
            "returns_faq.md",
            b"# Returns FAQ\n\nDamaged pallets must be reported within 48 hours of delivery.",
            "text/markdown",
        )
    }
    assert client.post("/api/v1/documents/upload", headers=viewer, files=files).status_code == 403
    r = client.post("/api/v1/documents/upload", headers=analyst, files=files)
    assert r.status_code == 202 and r.json()["status"] == "pending"
    doc_id = r.json()["id"]
    assert client.post("/api/v1/documents/upload", headers=analyst, files=files).status_code == 409  # duplicate
    drain(db, get_storage())
    assert client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()["status"] == "ready"
    ans = client.post(
        "/api/v1/chat/ask", headers=analyst, json={"question": "How quickly must damaged pallets be reported?"}
    ).json()
    assert "48 hours" in ans["answer"]
    bad = client.post(
        "/api/v1/documents/upload", headers=analyst, files={"file": ("x.pdf", b"MZ fake exe", "application/pdf")}
    )
    assert bad.status_code == 415 and bad.json()["error"]["code"] == "upload_rejected"


def test_flagged_injection_document_visible_but_marked(client, analyst):
    docs = {d["title"]: d for d in client.get("/api/v1/documents", headers=analyst).json()}
    assert docs["Suspicious Vendor Note"]["meta"]["flagged_chunks"] == 1
    body = client.post(
        "/api/v1/chat/ask", headers=analyst, json={"question": "When is the partner portal migration scheduled?"}
    ).json()
    assert body["citations"] and body["citations"][0]["flagged"] is True


def test_url_ingestion_blocks_non_allowlisted_host(client, analyst):
    r = client.post("/api/v1/documents/url", headers=analyst, json={"url": "http://169.254.169.254/latest/meta-data"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsafe_url"


def test_validation_error_envelope(client, analyst):
    r = client.post("/api/v1/chat/ask", headers=analyst, json={"question": ""})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_memory_crud_and_isolation(client, analyst, manager):
    item = client.put("/api/v1/memory", headers=analyst, json={"key": "preferred_currency", "value": "USD"}).json()
    assert client.get("/api/v1/memory", headers=analyst).json()[0]["key"] == "preferred_currency"
    assert client.delete(f"/api/v1/memory/{item['id']}", headers=manager).status_code == 404
    assert client.delete(f"/api/v1/memory/{item['id']}", headers=analyst).status_code == 204


def test_admin_endpoints_require_roles(client, analyst, manager):
    assert client.get("/api/v1/admin/audit", headers=analyst).status_code == 403
    assert client.get("/api/v1/admin/audit", headers=manager).status_code == 200
    assert client.get("/api/v1/admin/users", headers=manager).status_code == 403
    usage = client.get("/api/v1/admin/usage", headers=manager).json()
    assert any(u["purpose"] == "chat" and u["provider"] == "local" for u in usage["by_purpose"])


def test_password_constant_is_used():
    assert PASSWORD


def test_denied_tool_call_audit_survives_rollback(db):
    import pytest
    from conftest import get_user

    from app.tools.registry import ApprovalRequired, ToolContext, execute

    user = get_user(db, "manager@acme.example")
    with pytest.raises(ApprovalRequired):
        execute(
            "send_email",
            {"to": "a@b.example", "subject": "s", "body": "b", "idempotency_key": "k" * 10},
            ToolContext(db=db, user=user),
        )
    db.rollback()  # what the request handler does after the error
    row = db.scalar(select(AuditEvent).where(AuditEvent.action == "tool.send_email", AuditEvent.outcome == "blocked"))
    assert row is not None


def test_delete_document_removes_stored_object(client, manager, analyst, db):
    from app.ingestion.jobs import drain
    from app.ingestion.storage import get_storage

    files = {"file": ("temp_note.md", b"# Temp\n\nThis note will be deleted shortly after upload.", "text/markdown")}
    doc = client.post("/api/v1/documents/upload", headers=analyst, files=files).json()
    drain(db, get_storage())
    key = db.get(Document, doc["id"]).storage_path
    assert get_storage().get(key)
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=manager).status_code == 204
    import pytest

    with pytest.raises(FileNotFoundError):
        get_storage().get(key)
