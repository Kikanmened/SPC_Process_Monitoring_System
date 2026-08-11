"""Shared scheduler job types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class JobName(StrEnum):
    """Scheduled job identifiers from DEPLOYMENT_PLAN.md §7."""

    INGEST = "ingest"
    EVALUATE = "evaluate"
    NOTIFY = "notify"
    DAILY_REPORT = "daily-report"
    ARCHIVE = "archive"
    BACKUP = "backup"


@dataclass(frozen=True, slots=True)
class JobResult:
    """Outcome of one job execution."""

    job_name: JobName
    succeeded: bool
    fingerprint: str
    detail: dict[str, Any]
