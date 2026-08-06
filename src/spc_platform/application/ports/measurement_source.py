"""Port for anything that can supply raw measurement records (FR-D11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    """Identity of a raw source, for lineage and run records."""

    identity: str
    format: str
    location: str


@dataclass(frozen=True, slots=True)
class BatchRequest:
    """What to read from a source."""

    path: Path
    expected_rows: int | None = None
    exported_at: datetime | None = None


class MeasurementSource(Protocol):
    """Read raw measurement exports without interpreting them.

    Implementations live in ``infrastructure/readers/``. The port returns a
    filesystem path to a materialised raw file rather than a DataFrame, so the
    application layer never depends on pandas (TECH_STACK.md §3).
    """

    def describe(self) -> SourceDescriptor:
        """Return the source identity for lineage."""
        ...

    def materialise(self, request: BatchRequest, destination: Path) -> SourceDescriptor:
        """Copy or export the requested batch to ``destination``.

        Raises
        ------
        SourceUnavailableError
            If the source cannot be reached or read.
        """
        ...
