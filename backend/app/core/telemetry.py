"""Minimal OpenTelemetry: SDK tracer + console exporter (no collector). Spans are no-ops safe if unconfigured."""
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from app.core.config import get_settings

_provider = None


def setup_tracing() -> None:
    global _provider
    if _provider is not None:
        return
    _provider = TracerProvider()
    if get_settings().otel_console:
        _provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))


def get_tracer(name: str = "poc-02"):
    setup_tracing()
    return _provider.get_tracer(name)


@contextmanager
def span(name: str, **attributes):
    with get_tracer().start_as_current_span(name) as s:
        for k, v in attributes.items():
            if v is not None:
                s.set_attribute(k, v if isinstance(v, (str, bool, int, float)) else str(v))
        yield s
