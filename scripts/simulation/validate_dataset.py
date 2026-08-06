"""Check a written dataset against the manifest that travels with it.

Answers two questions an operator needs before trusting a dataset: are the
measurements statistically what the configuration asked for, and are these the
same bytes the manifest was written for?

Examples
--------
Validate the default dataset::

    uv run python scripts/simulation/validate_dataset.py data/synthetic/fab-12m

Show every check rather than only the failures::

    uv run python scripts/simulation/validate_dataset.py data/synthetic/fab-12m --verbose
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spc_platform.common.errors import SPCPlatformError
from spc_platform.simulation import (
    MANIFEST_FILENAME,
    Check,
    DatasetFormat,
    content_digest,
    read_manifest,
    read_measurements,
    validate_dataset,
)
from spc_platform.simulation.manifests import MEASUREMENTS_STEM


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for this script."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory", type=Path, help="a written dataset directory")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print every check, not only the failures",
    )
    return parser


def _find_measurements(directory: Path) -> Path:
    for dataset_format in DatasetFormat:
        candidate = directory / f"{MEASUREMENTS_STEM}{dataset_format.suffix}"
        if candidate.is_file():
            return candidate
    message = f"no measurement table in {directory}"
    raise FileNotFoundError(message)


def main(argv: list[str] | None = None) -> int:
    """Validate one written dataset. Returns a process exit code."""
    args = build_parser().parse_args(argv)

    try:
        manifest = read_manifest(args.directory / MANIFEST_FILENAME)
        frame = read_measurements(_find_measurements(args.directory))
    except (SPCPlatformError, FileNotFoundError) as error:
        print(f"Cannot read dataset: {error}", file=sys.stderr)
        return 1

    failures: list[str] = []

    digest = content_digest(frame)
    if digest != manifest.content_digest:
        failures.append(
            f"content digest {digest} does not match the manifest's {manifest.content_digest}"
        )
    if len(frame) != manifest.row_count:
        failures.append(f"{len(frame)} rows on disk, manifest says {manifest.row_count}")

    report = validate_dataset(frame, manifest)
    print(report.summary() if args.verbose else _failures_only(report.failures))

    if failures:
        print("\nThe dataset and its manifest do not correspond:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)

    return 0 if report.passed and not failures else 1


def _failures_only(failures: tuple[Check, ...]) -> str:
    if not failures:
        return "All statistical checks passed."
    lines = [check.describe() for check in failures]
    return "\n".join([*lines, f"\n{len(failures)} statistical checks failed."])


if __name__ == "__main__":
    sys.exit(main())
