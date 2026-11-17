"""Ingestion worker: `python -m app.worker`. Polls the job table; safe to run N replicas."""

import signal
import time

from app.core.db import session_factory
from app.core.logging import configure_logging, get_logger
from app.ingestion.jobs import claim_next, run_job
from app.ingestion.storage import get_storage

_running = True


def _stop(*_: object) -> None:
    global _running
    _running = False


def main() -> None:
    configure_logging()
    log = get_logger("worker")
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    storage = get_storage()
    log.info("worker_started")
    while _running:
        with session_factory()() as db:
            job = claim_next(db)
            if job is None:
                time.sleep(1.0)
                continue
            run_job(db, job, storage)
    log.info("worker_stopped")


if __name__ == "__main__":
    main()
