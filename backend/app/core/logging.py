"""Structured JSON logging via structlog.

All logs emitted by InsightFlow services are structured JSON records.
Loggers bind request_id / workflow_id at the middleware boundary and
propagate through the async context.
"""

import logging
import sys
from typing import Any

import structlog

from app.core.config import settings

# structlog's processor type annotation is imprecise; the concrete processors
# below are all valid callables matching its Processor protocol.
Processor = Any


def configure_logging() -> None:
    """Configure structlog as the global logging processor chain."""

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Redirect stdlib logging to structlog to keep one log stream.
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=settings.log_level.upper())


def get_logger(name: str = "insightflow") -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
