"""Filesystem destinations for a pipeline run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PipelinePaths:
    """Zone directories used by ingest and publish."""

    quarantine_root: Path
    interim_directory: Path | None = None
    processed_directory: Path | None = None
