"""Postgres-backed job queue using SELECT ... FOR UPDATE SKIP LOCKED.

Why not Celery/ARQ: one fewer infrastructure dependency for the vertical slice, transactional
enqueue (the job row commits atomically with the document row), and easy inspection. See ADR-002.
"""

from __future__ import annotations

import threading
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ingestion.indexer import index_document
from app.ingestion.storage import ObjectStorage
from app.models import Document, IngestionJob
from app.models.base import utcnow

log = get_logger(__name__)
STALE_AFTER = timedelta(minutes=10)
# While a job runs, its lock is refreshed this often, so a long job is never mistaken for a dead
# worker's job and reclaimed by a second worker. Must stay well below STALE_AFTER.
HEARTBEAT_INTERVAL_S = 60.0


def _heartbeat(job_id: str, stop: threading.Event) -> None:
    from app.core.db import session_factory

    while not stop.wait(HEARTBEAT_INTERVAL_S):
        try:
            with session_factory()() as hb:
                hb.execute(
                    update(IngestionJob)
                    .where(IngestionJob.id == job_id, IngestionJob.status == "processing")
                    .values(locked_at=utcnow())
                )
                hb.commit()
        except Exception as exc:  # noqa: BLE001 -- a missed beat is retried; the job itself continues
            log.warning("ingestion_heartbeat_failed", job_id=job_id, error_type=type(exc).__name__)


def enqueue(db: Session, doc: Document) -> IngestionJob:
    job = IngestionJob(org_id=doc.org_id, document_id=doc.id)
    db.add(job)
    return job


def claim_next(db: Session) -> IngestionJob | None:
    """Claim one job. Also reclaims jobs whose worker died (stale lock)."""
    stmt = (
        select(IngestionJob)
        .where(
            or_(
                IngestionJob.status == "queued",
                (IngestionJob.status == "processing") & (IngestionJob.locked_at < utcnow() - STALE_AFTER),
            )
        )
        .order_by(IngestionJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        return None
    job.status = "processing"
    job.locked_at = utcnow()
    job.attempts += 1
    db.commit()
    return job


def run_job(db: Session, job: IngestionJob, storage: ObjectStorage) -> None:
    doc = db.get(Document, job.document_id)
    if doc is None:
        job.status = "failed"
        job.last_error = "document deleted"
        db.commit()
        return
    doc.status = "processing"
    db.commit()
    stop = threading.Event()
    beat = threading.Thread(target=_heartbeat, args=(job.id, stop), daemon=True, name=f"ingest-hb-{job.id[:8]}")
    beat.start()
    try:
        n = index_document(db, doc, storage)
        doc.status = "ready"
        doc.error = None
        job.status = "done"
        job.finished_at = utcnow()
        db.commit()
        log.info("ingestion_done", document_id=doc.id, chunks=n)
    except Exception as exc:  # noqa: BLE001 -- record any failure on the job
        db.rollback()
        job_id = job.id
        reloaded_job = db.get(IngestionJob, job_id)
        assert reloaded_job is not None
        job = reloaded_job
        reloaded_doc = db.get(Document, job.document_id)
        assert reloaded_doc is not None
        doc = reloaded_doc
        job.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        retry = job.attempts < job.max_attempts and not isinstance(exc, ValueError)
        job.status = "queued" if retry else "failed"
        doc.status = "pending" if retry else "failed"
        doc.error = None if retry else job.last_error
        db.commit()
        log.warning(
            "ingestion_failed", document_id=doc.id, attempt=job.attempts, retry=retry, error_type=type(exc).__name__
        )
    finally:
        stop.set()  # always stop the heartbeat, success or failure


def drain(db: Session, storage: ObjectStorage, limit: int = 100) -> int:
    """Process queued jobs synchronously (used by tests, seed and INGESTION_INLINE mode)."""
    n = 0
    while n < limit:
        job = claim_next(db)
        if job is None:
            break
        run_job(db, job, storage)
        n += 1
    return n
