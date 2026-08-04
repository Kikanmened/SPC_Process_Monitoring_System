"""Timezone-aware time utilities and the injectable Clock.

No module reads the wall clock directly. SEMI E148 alignment and Ruff ``DTZ``
both require that every timestamp crossing a boundary is timezone-aware
(SYSTEM_ARCHITECTURE.md §9, CODING_STANDARDS.md §2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from spc_platform.common.errors import NaiveDatetimeError


@runtime_checkable
class Clock(Protocol):
    """Injected time source. Implementations must return timezone-aware datetimes."""

    def now(self) -> datetime:
        """Return the current instant as a timezone-aware datetime."""
        ...


class SystemClock:
    """UTC wall clock. Used at composition roots, never inside analytics."""

    def now(self) -> datetime:
        """Return ``datetime.now(UTC)``."""
        return datetime.now(UTC)


class FixedClock:
    """Deterministic clock for tests. Rejects a naive instant at construction."""

    def __init__(self, instant: datetime) -> None:
        self._instant = require_aware(instant, field_name="instant")

    def now(self) -> datetime:
        """Return the fixed instant."""
        return self._instant


def require_aware(value: datetime, *, field_name: str = "timestamp") -> datetime:
    """Return ``value`` if timezone-aware; raise ``NaiveDatetimeError`` otherwise.

    Parameters
    ----------
    value
        Candidate datetime.
    field_name
        Name used in the error context so the caller can locate the field.
    """
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise NaiveDatetimeError(
            f"{field_name} must be timezone-aware",
            field_name=field_name,
        )
    return value
