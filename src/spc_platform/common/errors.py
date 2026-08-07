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


class UnsupportedChartError(SPCPlatformError):
    """The configured chart type does not apply to this parameter's data."""


class AuditWriteError(SPCPlatformError):
    """The audit record could not be written; the action must not proceed."""


class UnauthorisedActionError(SPCPlatformError):
    """The actor's role does not permit the requested action."""


class SimulationConfigError(SPCPlatformError):
    """Generator configuration is internally inconsistent, or disagrees with reference data."""


class GroundTruthError(SPCPlatformError):
    """A dataset and the manifest describing its injected faults do not correspond."""


class InsufficientSitesError(SPCPlatformError):
    """Too few measurement sites for a spatial classification to be meaningful."""


class DuplicateMeasurementKeyError(SPCPlatformError):
    """The declared measurement key is not unique within a batch."""


class SourceUnavailableError(SPCPlatformError):
    """A measurement source adapter cannot reach or read its source."""


class UnitConversionError(SPCPlatformError):
    """No declared conversion exists between the source and target units."""


class AmbiguousRemeasurementError(SPCPlatformError):
    """Two records claim the same key with no resolvable ordering."""


class SubgroupingError(SPCPlatformError):
    """The declared subgrouping strategy cannot be applied to the series."""


class PipelinePublishError(SPCPlatformError):
    """A pipeline stage could not publish atomically to its destination zone."""


class ViewDataUnavailableError(SPCPlatformError):
    """A view model could not be built; the UI must render the reason, not invent data."""
