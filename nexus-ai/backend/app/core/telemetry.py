"""OpenTelemetry tracing.

Spans are always created through the OTel API. Without configuration the API is a no-op (near-zero
cost). When OTEL_EXPORTER_OTLP_ENDPOINT is set, spans are exported via OTLP/HTTP in batches.

Privacy rule: span attributes carry ids, sizes, providers and token counts -- never prompt text,
document text or email bodies.
"""

from __future__ import annotations

import os

from opentelemetry import trace

tracer = trace.get_tracer("nexus")
_configured = False


def configure_tracing(service_name: str = "nexus-api") -> bool:
    """Install an exporting TracerProvider if an OTLP endpoint is configured. Idempotent."""
    global _configured
    if _configured or not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured = True
    return True
