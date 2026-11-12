"""structlog JSON logging with the mandatory POC fields (poc_id, phase, associate_id, request_id)."""
import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    s = get_settings()

    def add_static(_, __, event_dict):
        event_dict.setdefault("poc_id", s.poc_id)
        event_dict.setdefault("phase", s.phase)
        event_dict.setdefault("associate_id", s.associate_id)
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_static,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = "app"):
    # initial values are bound lazily (at first use), so module-level loggers pick up configure_logging()'s processors
    return structlog.get_logger(name, phase=get_settings().phase)
