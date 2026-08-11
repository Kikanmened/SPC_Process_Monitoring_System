"""Notify job: one digested dispatch for open violations (FR-A05)."""

from __future__ import annotations

import hashlib
from typing import Any

from spc_platform.application.context import ApplicationServices
from spc_platform.application.use_cases.dispatch_notifications import dispatch_notifications
from spc_platform.common.errors import InsufficientDataError
from spc_platform.domain.ids import ActorId
from spc_platform.scheduler.types import JobName, JobResult

_SCHEDULER_ACTOR = ActorId("scheduler.notify")


def run(services: ApplicationServices, *, state: dict[str, Any]) -> JobResult:
    """Dispatch a digest only when the open-violation set changes.

    Re-running with the same open set is a no-op so the job is idempotent
    (NFR-R01) and never floods recipients.
    """
    open_ids = sorted(item.violation_id for item in services.violations.list_open())
    fingerprint = hashlib.sha256(
        ",".join(open_ids).encode() if open_ids else b"notify-empty"
    ).hexdigest()
    prior = state.get("notify", {})
    prior_fp = prior.get("fingerprint") if isinstance(prior, dict) else None
    if not open_ids:
        return JobResult(
            job_name=JobName.NOTIFY,
            succeeded=True,
            fingerprint=fingerprint,
            detail={"dispatched": False, "item_count": 0, "skipped": True},
        )
    if prior_fp == fingerprint:
        return JobResult(
            job_name=JobName.NOTIFY,
            succeeded=True,
            fingerprint=fingerprint,
            detail={"dispatched": False, "item_count": len(open_ids), "skipped": True},
        )
    try:
        receipt = dispatch_notifications(services, actor=_SCHEDULER_ACTOR)
        item_count = receipt.item_count
        dispatched = True
    except InsufficientDataError:
        item_count = 0
        dispatched = False
    return JobResult(
        job_name=JobName.NOTIFY,
        succeeded=True,
        fingerprint=fingerprint,
        detail={"dispatched": dispatched, "item_count": item_count, "skipped": False},
    )
