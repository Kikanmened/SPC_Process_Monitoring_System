"""Dispatch and double-run verification for scheduled jobs."""

from __future__ import annotations

from spc_platform.application.context import ApplicationServices
from spc_platform.common.errors import SPCPlatformError
from spc_platform.infrastructure.runtime_paths import RuntimePaths
from spc_platform.observability.metrics import METRICS
from spc_platform.scheduler.jobs import archive as archive_job
from spc_platform.scheduler.jobs import backup as backup_job
from spc_platform.scheduler.jobs import evaluate as evaluate_job
from spc_platform.scheduler.jobs import ingest as ingest_job
from spc_platform.scheduler.jobs import notify as notify_job
from spc_platform.scheduler.jobs import report as report_job
from spc_platform.scheduler.state import load_job_state, save_job_state
from spc_platform.scheduler.types import JobName, JobResult


class JobIdempotencyError(SPCPlatformError):
    """A second run of an idempotent job changed observable state."""


def run_job(
    services: ApplicationServices,
    job_name: JobName,
    paths: RuntimePaths,
) -> JobResult:
    """Execute one job and persist its fingerprint."""
    state = load_job_state(paths.job_state)
    if job_name is JobName.INGEST:
        result = ingest_job.run(services, data_root=paths.data_root, state=state)
    elif job_name is JobName.EVALUATE:
        result = evaluate_job.run(services, state=state)
    elif job_name is JobName.NOTIFY:
        result = notify_job.run(services, state=state)
    elif job_name is JobName.DAILY_REPORT:
        result = report_job.run(services, state=state, data_root=paths.data_root)
    elif job_name is JobName.ARCHIVE:
        result = archive_job.run(
            services, log_root=paths.log_root, data_root=paths.data_root, state=state
        )
    elif job_name is JobName.BACKUP:
        result = backup_job.run(
            services,
            data_root=paths.data_root,
            log_root=paths.log_root,
            backup_root=paths.backup_root,
            state=state,
        )
    else:
        raise SPCPlatformError("unknown job", job_name=str(job_name))

    state[job_name.value] = {
        "fingerprint": result.fingerprint,
        "detail": result.detail,
        "succeeded": result.succeeded,
    }
    save_job_state(paths.job_state, state)
    METRICS.incr(
        "spc_jobs_total",
        help_text="Scheduled job executions",
        amount=1.0,
    )
    METRICS.set_gauge(
        "spc_job_last_success",
        1.0 if result.succeeded else 0.0,
        help_text="1 when the most recent job succeeded",
    )
    return result


def run_job_twice(
    services: ApplicationServices,
    job_name: JobName,
    paths: RuntimePaths,
) -> tuple[JobResult, JobResult]:
    """Run a job twice and require identical fingerprints (NFR-R01)."""
    first = run_job(services, job_name, paths)
    second = run_job(services, job_name, paths)
    if first.fingerprint != second.fingerprint:
        raise JobIdempotencyError(
            "job is not idempotent: fingerprint changed on second run",
            job_name=job_name.value,
            first=first.fingerprint,
            second=second.fingerprint,
        )
    return first, second
