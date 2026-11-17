"""S3 storage adapter (moto at the AWS boundary), OpenTelemetry spans, ingestion lock heartbeat."""

import time

import pytest
from conftest import get_user
from moto import mock_aws
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import select

from app.ingestion import jobs
from app.ingestion.storage import S3Storage
from app.models import Document, IngestionJob

# ---------------------------------------------------------------- S3 adapter


@pytest.fixture
def s3():
    with mock_aws():
        store = S3Storage("nexus-test-bucket", region="us-east-1")
        store.ensure_bucket()
        yield store


def test_s3_roundtrip_delete_and_missing_key(s3):
    s3.put("org1/abc.pdf", b"%PDF-1.4 bytes")
    assert s3.get("org1/abc.pdf") == b"%PDF-1.4 bytes"
    s3.delete("org1/abc.pdf")
    with pytest.raises(FileNotFoundError):
        s3.get("org1/abc.pdf")
    s3.delete("org1/abc.pdf")  # deleting twice is fine (idempotent)


@pytest.mark.parametrize("key", ["", "/abs/key", "org/../other/key"])
def test_s3_rejects_unsafe_keys(s3, key):
    with pytest.raises(ValueError):
        s3.put(key, b"x")


def test_s3_objects_encrypted_at_rest_on_aws(s3):
    s3.put("org1/enc.txt", b"secret-ish")
    head = s3._s3.head_object(Bucket=s3.bucket, Key="org1/enc.txt")
    assert head["ServerSideEncryption"] == "AES256"


def test_get_storage_selects_s3_backend(monkeypatch):
    from app.core.config import get_settings
    from app.ingestion.storage import get_storage

    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
    get_settings.cache_clear()
    try:
        store = get_storage()
        assert isinstance(store, S3Storage) and store.sse is None  # no SSE header for S3-compatible stores
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------- tracing

_exporter = InMemorySpanExporter()


@pytest.fixture(scope="module", autouse=True)
def _tracing():
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_exporter))
    trace.set_tracer_provider(provider)  # global; the app's ProxyTracer picks it up
    yield


def test_chat_spans_nest_and_carry_no_text(db):
    from app.services.chat import ask

    _exporter.clear()
    secret_question = "When did the Ironclad contract expire?"
    ask(db, get_user(db, "analyst@acme.example"), secret_question, None)
    spans = {s.name: s for s in _exporter.get_finished_spans()}
    assert {"chat.ask", "retrieval.hybrid_search", "llm.generate"} <= set(spans)
    root = spans["chat.ask"]
    assert spans["retrieval.hybrid_search"].parent.span_id == root.context.span_id
    assert spans["llm.generate"].parent.span_id == root.context.span_id
    assert spans["llm.generate"].attributes["llm.provider"] == "local"
    for s in spans.values():  # privacy: no prompt or question text in attributes
        assert all(secret_question not in str(v) for v in s.attributes.values())


def test_workflow_tool_spans_are_children_of_step_spans_across_threads(db):
    from app.services.workflows import execute_run, start_run

    _exporter.clear()
    run = start_run(db, get_user(db, "manager@acme.example"), "Investigate declining purchases among top ten customers")
    execute_run(run.id)
    spans = _exporter.get_finished_spans()
    by_id = {s.context.span_id: s for s in spans}
    step = next(s for s in spans if s.name == "workflow.step data_agent")
    tool = next(s for s in spans if s.name == "tool.get_top_customers")
    assert tool.parent is not None and by_id[tool.parent.span_id] is step  # propagated into the worker thread
    assert step.attributes["workflow.outcome"] == "completed"


# ---------------------------------------------------------------- heartbeat


def test_long_ingestion_job_keeps_its_lock_fresh(db, monkeypatch, client, analyst):
    from app.ingestion.storage import get_storage

    files = {
        "file": ("slow_doc.md", b"# Slow\n\nA document whose indexing is artificially slowed down.", "text/markdown")
    }
    doc_id = client.post("/api/v1/documents/upload", headers=analyst, files=files).json()["id"]
    real_index = jobs.index_document

    def slow_index(*a, **kw):
        time.sleep(0.6)
        return real_index(*a, **kw)

    monkeypatch.setattr(jobs, "index_document", slow_index)
    monkeypatch.setattr(jobs, "HEARTBEAT_INTERVAL_S", 0.1)
    job = jobs.claim_next(db)
    assert job is not None and job.document_id == doc_id
    claimed_at = job.locked_at
    jobs.run_job(db, job, get_storage())
    db.expire_all()
    done = db.scalar(select(IngestionJob).where(IngestionJob.document_id == doc_id))
    assert done.status == "done" and done.locked_at > claimed_at  # heartbeat refreshed the lock
    assert db.get(Document, doc_id).status == "ready"
