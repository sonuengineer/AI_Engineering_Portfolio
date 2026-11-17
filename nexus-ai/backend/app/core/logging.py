"""Structured JSON logging with request-id context. Never log secrets or full prompts."""

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

_SECRET_RE = re.compile(r"(api[_-]?key|authorization|password|secret|token)(\"?\s*[:=]\s*\"?)([^\s\",}]+)", re.I)


def _redact(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key, value in list(event_dict.items()):
        if any(s in key.lower() for s in ("password", "secret", "token", "api_key", "authorization")):
            event_dict[key] = "[REDACTED]"
        elif isinstance(value, str):
            event_dict[key] = _SECRET_RE.sub(r"\1\2[REDACTED]", value)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "nexus") -> Any:
    return structlog.get_logger(name)
