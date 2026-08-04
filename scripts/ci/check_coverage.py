"""Fail on a coverage drop in the two layers where coverage is load-bearing.

TESTING_STRATEGY.md §6: coverage is a diagnostic, not a target. A
repository-wide percentage averages critical code together with glue and tells
you nothing. What matters is that ``domain/`` and ``analytics/`` never lose
coverage they once had, because a lost line there is an untested invariant or
an untested statistic.

Reads ``coverage.json`` (written by ``coverage json``) and compares each
tracked area against ``.coverage-baseline.json``. Run with ``--update`` to
record a new baseline after a deliberate, reviewed improvement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

REPO_ROOT = Path(__file__).resolve().parents[2]
COVERAGE_JSON = REPO_ROOT / "coverage.json"
BASELINE_JSON = REPO_ROOT / ".coverage-baseline.json"

TRACKED_AREAS = ("src/spc_platform/domain", "src/spc_platform/analytics")

# Coverage percentages move by fractions of a point when an unrelated file is
# added. Anything larger than this is a real regression.
TOLERANCE = 0.05


class AreaCoverage(TypedDict):
    """Measured coverage for one tracked area."""

    covered: int
    total: int
    percent: float


def measure(report: dict[str, object], area: str) -> AreaCoverage | None:
    """Return branch-inclusive coverage for one area, or None if it has no code."""
    files = report.get("files")
    if not isinstance(files, dict):
        message = "coverage.json has no 'files' section"
        raise ValueError(message)

    covered = 0
    total = 0
    for name, entry in files.items():
        if not name.startswith(area):
            continue
        summary = entry["summary"]
        covered += summary["covered_lines"] + summary["covered_branches"]
        total += summary["num_statements"] + summary["num_branches"]

    if total == 0:
        return None
    return AreaCoverage(covered=covered, total=total, percent=100.0 * covered / total)


def main() -> int:
    update = "--update" in sys.argv[1:]

    if not COVERAGE_JSON.exists():
        print(f"No coverage report at {COVERAGE_JSON.relative_to(REPO_ROOT)}.")
        print("Run `make coverage`, which produces it before calling this check.")
        return 1

    report = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    baseline: dict[str, float] = {}
    if BASELINE_JSON.exists():
        baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))["areas"]

    measured: dict[str, float] = {}
    failures: list[str] = []

    for area in TRACKED_AREAS:
        coverage = measure(report, area)
        if coverage is None:
            print(f"{area}: no executable code yet, nothing to compare")
            continue

        percent = coverage["percent"]
        measured[area] = round(percent, 2)
        previous = baseline.get(area)
        if previous is None:
            print(f"{area}: {percent:.2f}% (no baseline recorded)")
            continue

        verdict = "ok" if percent >= previous - TOLERANCE else "DROP"
        print(
            f"{area}: {percent:.2f}% "
            f"({coverage['covered']}/{coverage['total']}), baseline {previous:.2f}% [{verdict}]"
        )
        if verdict == "DROP":
            failures.append(f"{area} fell from {previous:.2f}% to {percent:.2f}%")

    if update:
        BASELINE_JSON.write_text(
            json.dumps({"areas": measured}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Baseline written to {BASELINE_JSON.relative_to(REPO_ROOT)}")
        return 0

    if failures:
        print("\nCoverage regression:")
        for failure in failures:
            print(f"  {failure}")
        print("\nAdd the missing tests, or record a reviewed baseline change with --update.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
