"""Generate a synthetic dataset and its ground-truth manifest.

Thin by design (scripts/README.md): argument parsing and reporting only. Every
decision that affects a number lives in ``spc_platform.simulation``, where it is
typed and tested.

Examples
--------
Write the default twelve-month dataset to ``data/synthetic/``::

    uv run python scripts/simulation/generate_dataset.py

Generate a short CSV replica for exercising ingestion, under a different seed::

    uv run python scripts/simulation/generate_dataset.py \
        --lots 60 --format csv --seed 7 --dataset-id fab-smoke
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spc_platform.common.errors import SPCPlatformError
from spc_platform.common.time import SystemClock
from spc_platform.config import load_reference_data
from spc_platform.infrastructure.vcs import current_code_revision
from spc_platform.simulation import (
    DatasetFormat,
    DatasetManifest,
    GeneratorConfig,
    generate_dataset,
    load_generator_config,
    validate_dataset,
    write_dataset,
)

DEFAULT_CONFIG = Path("configs/simulation/default.yaml")
DEFAULT_OUTPUT = Path("data/synthetic")


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for this script."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"generator configuration (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"root of the synthetic zone (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--format",
        type=DatasetFormat,
        choices=tuple(DatasetFormat),
        default=DatasetFormat.PARQUET,
        help="on-disk format for the measurement table (default: parquet)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="override the configured seed, for a second realisation of the same fab",
    )
    parser.add_argument(
        "--dataset-id",
        default=None,
        help="override the configured dataset id, which names the output directory",
    )
    parser.add_argument(
        "--lots",
        type=int,
        default=None,
        help="override the configured lot count, for a shorter dataset",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="write without checking the data against the manifest (not for committed datasets)",
    )
    return parser


def _apply_overrides(config: GeneratorConfig, args: argparse.Namespace) -> GeneratorConfig:
    """Apply the command-line overrides, re-validating the result.

    ``model_copy`` alone would skip validation, so a nonsensical override would
    only surface as a strange dataset. Round-tripping through the model keeps
    the configuration's own rules in force.
    """
    updates = {
        key: value
        for key, value in (("seed", args.seed), ("dataset_id", args.dataset_id))
        if value is not None
    }
    if args.lots is not None:
        updates["schedule"] = config.schedule.model_copy(update={"lots": args.lots})
    if not updates:
        return config
    return GeneratorConfig.model_validate(config.model_copy(update=updates).model_dump())


def main(argv: list[str] | None = None) -> int:
    """Generate, validate, and write one dataset. Returns a process exit code."""
    args = build_parser().parse_args(argv)

    try:
        config = _apply_overrides(load_generator_config(args.config), args)
        dataset = generate_dataset(
            config,
            load_reference_data(),
            code_revision=current_code_revision(),
            clock=SystemClock(),
        )
    except SPCPlatformError as error:
        print(f"Generation failed: {error}", file=sys.stderr)
        return 1

    if not args.skip_validation:
        report = validate_dataset(dataset.frame, dataset.manifest)
        if not report.passed:
            # Writing anyway would put a dataset on disk whose manifest
            # misdescribes it, and every score taken against it would be wrong
            # in a way nothing downstream can detect.
            print(report.summary(), file=sys.stderr)
            print("\nRefusing to write: the data does not match its manifest.", file=sys.stderr)
            return 1

    paths, manifest = write_dataset(dataset, args.output, dataset_format=args.format)
    _report(paths.directory, manifest)
    return 0


def _report(directory: Path, manifest: DatasetManifest) -> None:
    print(f"Wrote {directory}")
    for label, value in (
        ("dataset_revision", manifest.dataset_revision),
        ("rows", manifest.row_count),
        ("seed", manifest.seed),
        ("code_revision", manifest.code_revision),
        ("content_digest", manifest.content_digest),
        ("faults", len(manifest.faults)),
    ):
        print(f"  {label:<17} {value}")


if __name__ == "__main__":
    sys.exit(main())
