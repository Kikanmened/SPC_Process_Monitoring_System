"""Filesystem measurement source for CSV and Parquet exports."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from spc_platform.application.ports.measurement_source import (
    BatchRequest,
    SourceDescriptor,
)
from spc_platform.common.errors import SourceUnavailableError


class FileMeasurementSource:
    """Copy a local CSV or Parquet export into the raw zone (FR-D11)."""

    def __init__(self, *, identity: str | None = None) -> None:
        self._identity = identity

    def describe(self) -> SourceDescriptor:
        """Return a generic descriptor when no batch has been materialised yet."""
        return SourceDescriptor(
            identity=self._identity or "file",
            format="unknown",
            location="",
        )

    def materialise(self, request: BatchRequest, destination: Path) -> SourceDescriptor:
        """Copy ``request.path`` to ``destination``, preserving bytes.

        Raises
        ------
        SourceUnavailableError
            If the source path cannot be read or the destination cannot be written.
        """
        source = request.path
        if not source.is_file():
            raise SourceUnavailableError(
                "measurement source path does not exist or is not a file",
                path=str(source),
            )
        suffix = source.suffix.lower()
        if suffix not in {".csv", ".parquet"}:
            raise SourceUnavailableError(
                "unsupported measurement export format",
                path=str(source),
                format=suffix or "(none)",
            )
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except OSError as exc:
            raise SourceUnavailableError(
                "failed to materialise measurement source into the raw zone",
                path=str(source),
                destination=str(destination),
                reason=str(exc),
            ) from exc

        if request.expected_rows is not None:
            actual = _count_rows(destination, suffix)
            if actual != request.expected_rows:
                raise SourceUnavailableError(
                    "materialised batch row count does not match the manifest",
                    path=str(source),
                    expected_rows=request.expected_rows,
                    actual_rows=actual,
                )

        return SourceDescriptor(
            identity=self._identity or str(source.resolve()),
            format=suffix.lstrip("."),
            location=str(destination.resolve()),
        )


def load_raw_frame(path: Path) -> pd.DataFrame:
    """Load a materialised raw CSV or Parquet into a DataFrame for ingestion.

    Used by composition roots after ``materialise``. Pipelines receive the
    frame; they do not call this adapter.
    """
    if not path.is_file():
        raise SourceUnavailableError(
            "raw frame path does not exist",
            path=str(path),
        )
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            return pd.read_csv(path)
        if suffix == ".parquet":
            return pd.read_parquet(path)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise SourceUnavailableError(
            "failed to read materialised raw frame",
            path=str(path),
            reason=str(exc),
        ) from exc
    raise SourceUnavailableError(
        "unsupported raw frame format",
        path=str(path),
        format=suffix or "(none)",
    )


def _count_rows(path: Path, suffix: str) -> int:
    """Count data rows without altering the file."""
    if suffix == ".csv":
        # Header row is not a measurement.
        with path.open(encoding="utf-8") as handle:
            return max(sum(1 for _ in handle) - 1, 0)
    frame = pd.read_parquet(path)
    return len(frame)
