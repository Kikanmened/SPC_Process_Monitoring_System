"""Structured operational logging (NFR-SE07). Separate from the audit trail."""

from __future__ import annotations

import logging
import sys
from typing import Protocol, cast

import structlog


class BoundLogger(Protocol):
    """Minimal structlog surface used at process boundaries."""

    def info(self, event: str, **kwargs: object) -> None:
        """Log an informational event."""

    def warning(self, event: str, **kwargs: object) -> None:
        """Log a warning event."""

    def error(self, event: str, **kwargs: object) -> None:
        """Log an error event."""


def configure_logging(*, json_logs: bool = True) -> None:
    """Configure structlog once at a process boundary (API, CLI, scheduler)."""
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_logs:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> BoundLogger:
    """Return a bound logger for a module name."""
    return cast(BoundLogger, structlog.get_logger(name))
