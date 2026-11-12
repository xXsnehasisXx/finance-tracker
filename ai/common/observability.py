"""Structured logging (structlog JSON) and minimal OpenTelemetry for the AI components.

Every log line carries poc_id / phase / associate_id. Tracing is opt-in-safe: spans always work (no-op safe) and are
printed to the console only when OTEL_CONSOLE=true. LangSmith tracing is enabled purely by environment variables.
"""
import os
import sys
from contextlib import contextmanager

import structlog
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

_configured = {"phase": None}
_provider = None


def configure_logging(phase: int, stream=None) -> None:
    """stream: where JSON logs go (default stdout). The MCP server process MUST pass sys.stderr: stdout is its protocol channel."""
    _configured["phase"] = phase

    def add_static(_, __, event_dict):
        event_dict.setdefault("poc_id", os.getenv("POC_ID", "POC-02"))
        event_dict.setdefault("phase", _configured["phase"])
        event_dict.setdefault("associate_id", os.getenv("ASSOCIATE_ID", "unknown"))
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_static,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str, phase: int | None = None):
    """Phase is bound per logger so events from different phases in one process (e.g. Streamlit: RAG + agent) stay correct."""
    if _configured["phase"] is None:
        configure_logging(phase or 2)
    return structlog.get_logger(name, phase=phase) if phase is not None else structlog.get_logger(name)


def langsmith_enabled() -> bool:
    return os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true" and bool(os.getenv("LANGCHAIN_API_KEY"))


def traceable_if_enabled(**kwargs):
    """@traceable decorator that is a harmless no-op when LangSmith credentials are absent."""
    from langsmith import traceable

    return traceable(**kwargs)


def _get_provider():
    global _provider
    if _provider is None:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

        _provider = TracerProvider()
        if os.getenv("OTEL_CONSOLE", "false").lower() == "true":
            _provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout)))
    return _provider


@contextmanager
def span(name: str, **attributes):
    with _get_provider().get_tracer("poc-02-ai").start_as_current_span(name) as s:
        s.set_attribute("poc_id", os.getenv("POC_ID", "POC-02"))
        for k, v in attributes.items():
            if v is not None:
                s.set_attribute(k, v if isinstance(v, (str, bool, int, float)) else str(v))
        yield s
