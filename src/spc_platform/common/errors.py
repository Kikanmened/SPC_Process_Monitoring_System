"""Typed exception hierarchy for the platform.

Rooted at ``SPCPlatformError`` so callers can distinguish a platform failure
from a library failure. Every subclass carries actionable context as attributes
rather than a prose message alone (CODING_STANDARDS.md §5).

Domain invariant violations raise ``spc_platform.domain.errors.DomainError`` —
``domain/`` cannot import this package (import-linter). Application and
analytics code translate or raise the types below.
"""

from __future__ import annotations


class SPCPlatformError(Exception):
    """Root of every platform exception.

    Parameters
    ----------
    message
        Human-readable summary. Prefer attributes for structured context.
    **context
        Named fields attached to the exception for logging and callers.
    """

    def __init__(self, message: str, **context: object) -> None:
        self.context: dict[str, object] = dict(context)
        super().__init__(message)

    def __str__(self) -> str:
        """Render the message with structured context attached."""
        if not self.context:
            return super().__str__()
        details = ", ".join(f"{key}={value!r}" for key, value in self.context.items())
        return f"{super().__str__()} ({details})"


class ConfigurationError(SPCPlatformError):
    """Unknown key, missing required value, or failed validation at load."""


class UnknownUnitError(SPCPlatformError):
    """A unit outside the registry, or an undeclared conversion."""


class NaiveDatetimeError(SPCPlatformError):
    """A timezone-naive datetime reached a boundary that forbids it."""


class SchemaValidationError(SPCPlatformError):
    """A record or batch failed a declared data-zone schema."""


class NoActiveBaselineError(SPCPlatformError):
    """No approved active baseline exists for the requested parameter."""


class InsufficientDataError(SPCPlatformError):
    """Fewer observations than the configured or statistical minimum."""


class UnstableProcessError(SPCPlatformError):
    """Capability or similar analysis refused because the process is not in control."""


class DegenerateSeriesError(SPCPlatformError):
    """A series that makes a statistic undefined (e.g. zero range)."""


class AuditWriteError(SPCPlatformError):
    """The audit record could not be written; the action must not proceed."""


class UnauthorisedActionError(SPCPlatformError):
    """The actor's role does not permit the requested action."""
