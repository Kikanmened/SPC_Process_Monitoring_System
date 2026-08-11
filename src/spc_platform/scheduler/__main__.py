"""``python -m spc_platform.scheduler`` entry point."""

from __future__ import annotations

import argparse
import time

from spc_platform.infrastructure.composition import build_local_bundle
from spc_platform.infrastructure.runtime_paths import resolve_runtime_paths
from spc_platform.observability.logging import configure_logging, get_logger
from spc_platform.scheduler.runner import run_job
from spc_platform.scheduler.types import JobName

_DEFAULT_JOBS = (
    JobName.INGEST,
    JobName.EVALUATE,
    JobName.NOTIFY,
    JobName.ARCHIVE,
    JobName.BACKUP,
)


def main(argv: list[str] | None = None) -> int:
    """Run scheduled jobs once or in a loop."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the job set once and exit",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run forever with --interval seconds between cycles",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=900,
        help="Loop interval in seconds (default 900)",
    )
    parser.add_argument(
        "jobs",
        nargs="*",
        help="Optional job names; default is the standard set",
    )
    args = parser.parse_args(argv)
    configure_logging(json_logs=True)
    log = get_logger("spc.scheduler")
    paths = resolve_runtime_paths()
    bundle = build_local_bundle()
    selected = tuple(JobName(name) for name in args.jobs) if args.jobs else _DEFAULT_JOBS

    def _cycle() -> None:
        for job_name in selected:
            result = run_job(bundle.services, job_name, paths)
            log.info(
                "job_finished",
                job=job_name.value,
                succeeded=result.succeeded,
                fingerprint=result.fingerprint,
                detail=result.detail,
            )

    if args.loop:
        log.info("scheduler_loop_start", interval=args.interval, jobs=[j.value for j in selected])
        while True:
            _cycle()
            time.sleep(args.interval)
    _cycle()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
