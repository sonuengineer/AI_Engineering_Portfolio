"""Background run worker. Claims queued runs with SELECT ... FOR UPDATE SKIP LOCKED.

Run standalone (`python -m app.worker`) or embedded in the API process (RUN_WORKER_IN_API=true).
"""

from __future__ import annotations

import os
import socket
import threading
import time
import uuid

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.logging import configure_logging, get_logger
from app.engine.runner import execute_run

log = get_logger(__name__)

_CLAIM_SQL = text(
    """
    UPDATE runs SET status = 'running', started_at = now(), worker_id = :worker
    WHERE id = (
        SELECT id FROM runs WHERE status = 'queued' ORDER BY created_at
        FOR UPDATE SKIP LOCKED LIMIT 1
    )
    RETURNING id
    """
)


def claim_next_run(worker_id: str) -> uuid.UUID | None:
    with session_scope() as s:
        row = s.execute(_CLAIM_SQL, {"worker": worker_id}).first()
        return row[0] if row else None


def process_available(worker_id: str, max_runs: int | None = None) -> int:
    """Drain the queue (used by tests and the CLI). Returns number of runs processed."""
    n = 0
    while max_runs is None or n < max_runs:
        run_id = claim_next_run(worker_id)
        if run_id is None:
            break
        try:
            execute_run(run_id)
        except Exception as exc:  # never let the worker die
            log.error("worker_run_crashed", run_id=str(run_id), error=str(exc)[:300])
        n += 1
    return n


def worker_loop(stop: threading.Event, worker_id: str | None = None) -> None:
    worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    poll = get_settings().worker_poll_seconds
    log.info("worker_started", worker_id=worker_id)
    while not stop.is_set():
        try:
            if process_available(worker_id, max_runs=1) == 0:
                stop.wait(poll)
        except Exception as exc:
            log.error("worker_loop_error", error=str(exc)[:300])
            stop.wait(poll * 5)
    log.info("worker_stopped", worker_id=worker_id)


def main() -> None:
    configure_logging(get_settings().log_level)
    stop = threading.Event()
    try:
        worker_loop(stop)
    except KeyboardInterrupt:
        stop.set()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
