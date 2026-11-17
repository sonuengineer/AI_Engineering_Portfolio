"""structlog JSON logging. Never log secrets or prompt/output bodies."""

from __future__ import annotations

import logging
import sys
from typing import Any, TextIO

import structlog


class _StdStream:
    """Resolves sys.stdout/sys.stderr at write time (they may be swapped, e.g. by pytest)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def write(self, s: str) -> int:
        return getattr(sys, self.name).write(s)

    def flush(self) -> None:
        getattr(sys, self.name).flush()


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    out: Any = _StdStream("stderr" if stream is sys.stderr else "stdout")
    logging.basicConfig(format="%(message)s", stream=out, level=getattr(logging, level.upper(), 20))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), 20)),
        logger_factory=structlog.PrintLoggerFactory(file=out),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = "evalops") -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger(name)
