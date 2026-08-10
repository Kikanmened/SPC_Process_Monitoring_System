"""Domain-layer errors.

``domain/`` imports nothing from this repository, so these do not inherit from
``SPCPlatformError`` in ``common/``. Application code may wrap them.
"""

from __future__ import annotations


class DomainError(Exception):
    """An invariant of the fab vocabulary was violated."""

    def __init__(self, message: str, **context: object) -> None:
        self.context: dict[str, object] = dict(context)
        super().__init__(message)

    def __str__(self) -> str:
        """Render the message with structured context attached."""
        if not self.context:
            return super().__str__()
        details = ", ".join(f"{key}={value!r}" for key, value in self.context.items())
        return f"{super().__str__()} ({details})"


class DomainInvariantError(DomainError):
    """A construction-time invariant failed (slot range, limit ordering, …)."""


class DispositionRequiredError(DomainError):
    """Closure attempted without a disposition and reason (FR-A03, AC-B2)."""


class UnknownDispositionError(DomainError):
    """A disposition outside the permitted set."""
