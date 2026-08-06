#!/usr/bin/env python3
"""Run one raw export through ingest → transform → processed.

Composition root: wires filesystem readers and a DuckDB repository. Does not
belong under ``src/`` so import-linter layering stays intact.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spc_platform.application.ports.measurement_source import BatchRequest
from spc_platform.common.time import SystemClock
from spc_platform.config import load_settings
from spc_platform.config.profiles import Profile
from spc_platform.infrastructure.readers.file_source import (
    FileMeasurementSource,
    load_raw_frame,
)
from spc_platform.infrastructure.repositories import DuckDBMeasurementRepository
from spc_platform.pipelines.paths import PipelinePaths
from spc_platform.pipelines.run import PipelineDependencies, run_pipeline


def main(argv: list[str] | None = None) -> int:
    """CLI entry for a single-batch pipeline run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        type=Path,
        help="Path to a CSV or Parquet raw export",
    )
    parser.add_argument(
        "--raw-destination",
        type=Path,
        default=Path("data/raw/batch.parquet"),
        help="Where to materialise the immutable raw copy",
    )
    parser.add_argument(
        "--duckdb",
        type=Path,
        default=Path("data/processed/local.duckdb"),
        help="DuckDB file for the measurement repository",
    )
    parser.add_argument(
        "--quarantine",
        type=Path,
        default=Path("data/archive/quarantine"),
    )
    parser.add_argument(
        "--interim",
        type=Path,
        default=Path("data/interim"),
    )
    parser.add_argument(
        "--processed",
        type=Path,
        default=Path("data/processed"),
    )
    args = parser.parse_args(argv)

    settings = load_settings(Profile.LOCAL)
    source = FileMeasurementSource(identity=str(args.source.resolve()))
    descriptor = source.materialise(
        BatchRequest(path=args.source),
        args.raw_destination,
    )
    frame = load_raw_frame(Path(descriptor.location))
    repository = DuckDBMeasurementRepository(path=args.duckdb)
    try:
        result = run_pipeline(
            frame,
            source_identity=descriptor.identity,
            dependencies=PipelineDependencies(
                clock=SystemClock(),
                registry=settings.unit_registry(),
                paths=PipelinePaths(
                    quarantine_root=args.quarantine,
                    interim_directory=args.interim,
                    processed_directory=args.processed,
                ),
                repository=repository,
            ),
        )
    finally:
        repository.close()

    print(
        f"ok revision={result.data_revision} "
        f"rows={result.publish.row_count} "
        f"processed={result.publish.path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
