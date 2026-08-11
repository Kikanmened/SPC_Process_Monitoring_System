#!/usr/bin/env python3
"""Run one or more scheduled jobs (optionally verifying idempotency)."""

from __future__ import annotations

import argparse
import json
import sys

from spc_platform.infrastructure.composition import build_local_bundle
from spc_platform.infrastructure.runtime_paths import resolve_runtime_paths
from spc_platform.scheduler.runner import run_job, run_job_twice
from spc_platform.scheduler.types import JobName


def main(argv: list[str] | None = None) -> int:
    """CLI entry for ops job execution."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "jobs",
        nargs="+",
        help="Job names: ingest evaluate notify daily-report archive backup",
    )
    parser.add_argument(
        "--twice",
        action="store_true",
        help="Run each job twice and require identical fingerprints (NFR-R01)",
    )
    args = parser.parse_args(argv)
    paths = resolve_runtime_paths()
    bundle = build_local_bundle()
    outcomes = []
    for name in args.jobs:
        job = JobName(name)
        if args.twice:
            first, second = run_job_twice(bundle.services, job, paths)
            outcomes.append(
                {
                    "job": job.value,
                    "fingerprint": first.fingerprint,
                    "second_fingerprint": second.fingerprint,
                    "idempotent": first.fingerprint == second.fingerprint,
                    "detail": first.detail,
                }
            )
        else:
            result = run_job(bundle.services, job, paths)
            outcomes.append(
                {
                    "job": job.value,
                    "fingerprint": result.fingerprint,
                    "detail": result.detail,
                }
            )
    print(json.dumps(outcomes, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
