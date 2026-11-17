"""Lightweight tracing: spans recorded in memory per case, redacted, persisted to Postgres.

If OTEL_EXPORTER_OTLP_ENDPOINT is set and the `otlp` extra is installed, the same (redacted)
spans are also exported via OTLP/HTTP using the OpenTelemetry SDK.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redaction import redact
from app.models import Span, Trace

log = get_logger(__name__)


@dataclass
class SpanRecord:
    id: uuid.UUID
    name: str
    span_type: str
    parent_id: uuid.UUID | None
    started_at: dt.datetime
    t0: float
    ended_at: dt.datetime | None = None
    duration_ms: float | None = None
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)

    def set(self, **attrs: Any) -> None:
        self.attributes.update(attrs)


class TraceRecorder:
    def __init__(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.id = uuid.uuid4()
        self.name = name
        self.attributes = attributes or {}
        self.started_at = dt.datetime.now(dt.UTC)
        self._t0 = time.perf_counter()
        self.spans: list[SpanRecord] = []
        self._stack: list[uuid.UUID] = []
        self.status = "ok"
        self.duration_ms: float | None = None
        self.ended_at: dt.datetime | None = None

    def _now(self) -> dt.datetime:
        # Wall clock on Windows is coarse (~1-15 ms); derive span timestamps from perf_counter instead.
        return self.started_at + dt.timedelta(seconds=time.perf_counter() - self._t0)

    @contextmanager
    def span(self, name: str, span_type: str, **attributes: Any) -> Iterator[SpanRecord]:
        rec = SpanRecord(
            id=uuid.uuid4(), name=name, span_type=span_type,
            parent_id=self._stack[-1] if self._stack else None,
            started_at=self._now(), t0=time.perf_counter(), attributes=dict(attributes),
        )
        self.spans.append(rec)
        self._stack.append(rec.id)
        try:
            yield rec
        except Exception as exc:
            rec.status = "error"
            rec.attributes["error"] = f"{type(exc).__name__}: {exc}"[:500]
            raise
        finally:
            self._stack.pop()
            rec.duration_ms = (time.perf_counter() - rec.t0) * 1000.0
            rec.ended_at = rec.started_at + dt.timedelta(milliseconds=rec.duration_ms)

    def finish(self, status: str = "ok") -> None:
        self.status = status
        self.duration_ms = (time.perf_counter() - self._t0) * 1000.0
        self.ended_at = self.started_at + dt.timedelta(milliseconds=self.duration_ms)

    def persist(self, session: Session, org_id: uuid.UUID, run_id: uuid.UUID | None) -> uuid.UUID:
        if self.duration_ms is None:
            self.finish()
        session.add(Trace(
            id=self.id, org_id=org_id, run_id=run_id, name=self.name, started_at=self.started_at,
            ended_at=self.ended_at, duration_ms=self.duration_ms, status=self.status,
            attributes=redact(self.attributes),
        ))
        session.flush()
        for s in self.spans:
            session.add(Span(
                id=s.id, org_id=org_id, trace_id=self.id, parent_span_id=s.parent_id, name=s.name,
                span_type=s.span_type, started_at=s.started_at, ended_at=s.ended_at, duration_ms=s.duration_ms,
                status=s.status, attributes=redact(s.attributes),
            ))
        _export_otel(self)
        return self.id


# --------------------------------------------------------------------------- optional OTLP export

_otel_lock = threading.Lock()
_otel_tracer: Any = None
_otel_checked = False


def _get_otel_tracer() -> Any:
    global _otel_tracer, _otel_checked
    with _otel_lock:
        if _otel_checked:
            return _otel_tracer
        _otel_checked = True
        endpoint = get_settings().otel_exporter_otlp_endpoint
        if not endpoint:
            return None
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError:
            log.warning("otel_exporter_missing", hint="uv sync --extra otlp")
            return None
        provider = TracerProvider(resource=Resource.create({"service.name": "evalops-ai"}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")))
        _otel_tracer = provider.get_tracer("evalops")
        return _otel_tracer


def _otel_attr(v: Any) -> Any:
    if isinstance(v, str | bool | int | float):
        return v
    return str(v)[:1000]


def _export_otel(rec: TraceRecorder) -> None:
    tracer = _get_otel_tracer()
    if tracer is None:
        return
    from opentelemetry import trace as otel_trace

    def ns(t: dt.datetime) -> int:
        return int(t.timestamp() * 1e9)

    root = tracer.start_span(rec.name, start_time=ns(rec.started_at),
                             attributes={k: _otel_attr(v) for k, v in redact(rec.attributes).items()})
    handles: dict[uuid.UUID, Any] = {}
    for s in rec.spans:
        parent = handles.get(s.parent_id, root) if s.parent_id else root
        ctx = otel_trace.set_span_in_context(parent)
        attrs = {k: _otel_attr(v) for k, v in redact(s.attributes).items()}
        attrs["evalops.span_type"] = s.span_type
        h = tracer.start_span(s.name, context=ctx, start_time=ns(s.started_at), attributes=attrs)
        handles[s.id] = h
    for s in rec.spans:
        handles[s.id].end(end_time=ns(s.ended_at or s.started_at))
    root.end(end_time=ns(rec.ended_at or rec.started_at))
