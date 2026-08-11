"""Evaluate job: re-evaluate open parameters against active baselines."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.measurement_repository import SeriesQuery
from spc_platform.application.use_cases.evaluate_lot import evaluate_lot
from spc_platform.common.errors import InsufficientDataError, NoActiveBaselineError
from spc_platform.domain.ids import ActorId, LotId, ParameterId
from spc_platform.scheduler.types import JobName, JobResult

_SCHEDULER_ACTOR = ActorId("scheduler.evaluate")


def run(services: ApplicationServices, *, state: dict[str, Any]) -> JobResult:
    """Evaluate once per data revision; re-runs are no-ops (NFR-R01)."""
    now = services.clock.now()
    window_start = now - timedelta(days=30)
    parameter_id = ParameterId("OXIDE_THK")
    lot_id = LotId("LOT-001")
    try:
        series = services.measurements.series_for(
            SeriesQuery(
                parameter_id=parameter_id,
                window_start=window_start,
                window_end=now,
            )
        )
        data_revision = str(series.data_revision)
    except InsufficientDataError:
        data_revision = "none"

    prior = state.get("evaluate", {})
    prior_detail = prior.get("detail", {}) if isinstance(prior, dict) else {}
    if (
        prior_detail.get("data_revision") == data_revision
        and isinstance(prior, dict)
        and "fingerprint" in prior
    ):
        return JobResult(
            job_name=JobName.EVALUATE,
            succeeded=True,
            fingerprint=str(prior["fingerprint"]),
            detail=dict(prior_detail),
        )

    evaluated = 0
    if data_revision != "none":
        try:
            result = evaluate_lot(
                services,
                actor=_SCHEDULER_ACTOR,
                parameter_id=parameter_id,
                lot_id=lot_id,
                window_start=window_start,
                window_end=now,
            )
            evaluated = result.points_evaluated
        except (NoActiveBaselineError, InsufficientDataError):
            evaluated = 0

    open_ids = sorted(item.violation_id for item in services.violations.list_open())
    fingerprint = hashlib.sha256(
        f"{data_revision}|{evaluated}|{','.join(open_ids)}".encode()
    ).hexdigest()
    return JobResult(
        job_name=JobName.EVALUATE,
        succeeded=True,
        fingerprint=fingerprint,
        detail={
            "points_evaluated": evaluated,
            "open_violation_ids": open_ids,
            "data_revision": data_revision,
        },
    )
