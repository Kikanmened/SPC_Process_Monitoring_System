"""Time the generator and report its throughput and memory footprint.

The generator sits in front of every integration and end-to-end test, so its
cost is paid on every run of those tiers. This script exists to notice when that
cost changes, and to size a dataset before asking CI to build one.

Examples
--------
Time the default configuration::

    uv run python scripts/simulation/benchmark_generator.py

Compare three lot counts, three repeats each::

    uv run python scripts/simulation/benchmark_generator.py --lots 50 200 500 --repeat 3
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path

from spc_platform.common.errors import SPCPlatformError
from spc_platform.common.time import SystemClock
from spc_platform.config import load_reference_data
from spc_platform.infrastructure.vcs import current_code_revision
from spc_platform.simulation import GeneratorConfig, generate_dataset, load_generator_config

DEFAULT_CONFIG = Path("configs/simulation/default.yaml")
_BYTES_PER_MIB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class Timing:
    """What one lot count cost."""

    lots: int
    rows: int
    seconds: tuple[float, ...]
    peak_mib: float

    @property
    def median_seconds(self) -> float:
        """Median wall-clock time across repeats."""
        return statistics.median(self.seconds)

    @property
    def rows_per_second(self) -> float:
        """Throughput at the median time."""
        return self.rows / self.median_seconds if self.median_seconds > 0 else float("inf")


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
        "--lots",
        type=int,
        nargs="+",
        default=None,
        help="lot counts to time (default: the configured one)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=3,
        help="runs per lot count; the median is reported (default: 3)",
    )
    return parser


def _time_one(config: GeneratorConfig, lots: int, repeat: int) -> Timing:
    reference = load_reference_data()
    scaled = config.model_copy(
        update={"schedule": config.schedule.model_copy(update={"lots": lots})}
    )
    clock = SystemClock()
    revision = current_code_revision()

    def run() -> int:
        return len(generate_dataset(scaled, reference, code_revision=revision, clock=clock).frame)

    # Timed with the allocation tracer off. It intercepts every allocation, and
    # the generator makes a great many, so leaving it on during the timed runs
    # inflates them several-fold — reporting a cost nobody running the generator
    # will ever pay, which is the opposite of what a benchmark is for.
    durations: list[float] = []
    rows = 0
    for _ in range(repeat):
        started = time.perf_counter()
        rows = run()
        durations.append(time.perf_counter() - started)

    # One further, untimed run for the footprint.
    tracemalloc.start()
    run()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    return Timing(lots=lots, rows=rows, seconds=tuple(durations), peak_mib=peak / _BYTES_PER_MIB)


def main(argv: list[str] | None = None) -> int:
    """Run the benchmark. Returns a process exit code."""
    args = build_parser().parse_args(argv)

    try:
        config = load_generator_config(args.config)
    except SPCPlatformError as error:
        print(f"Cannot load configuration: {error}", file=sys.stderr)
        return 1

    lot_counts = args.lots or [config.schedule.lots]
    header = f"{'lots':>7}  {'rows':>10}  {'median s':>9}  {'rows/s':>10}  {'peak MiB':>9}"
    print(header)
    print("-" * len(header))

    for lots in lot_counts:
        timing = _time_one(config, lots, args.repeat)
        print(
            f"{timing.lots:>7}  {timing.rows:>10}  {timing.median_seconds:>9.3f}  "
            f"{timing.rows_per_second:>10,.0f}  {timing.peak_mib:>9.1f}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
