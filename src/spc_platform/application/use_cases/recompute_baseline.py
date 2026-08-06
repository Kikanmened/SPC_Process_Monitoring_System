"""Recompute and optionally activate a baseline (FR-CF04, FR-AU04)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import numpy as np

from spc_platform.analytics.charts import individuals_study
from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.measurement_repository import SeriesQuery
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.domain.baseline import Baseline
from spc_platform.domain.control_limit import ControlLimit
from spc_platform.domain.enums import BaselineStatus
from spc_platform.domain.ids import ActorId, BaselineId, ParameterId


@dataclass(frozen=True, slots=True)
class RecomputeBaselineResult:
    """The baseline that was stored."""

    baseline: Baseline
    previous_active_id: str | None


def recompute_baseline(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId,
    window_start: datetime,
    window_end: datetime,
    activate: bool = False,
    reason: str = "",
) -> RecomputeBaselineResult:
    """Build a baseline from a Phase I individuals study over the window.

    When ``activate`` is true the actor must be authorised to approve, and the
    new baseline is saved as ACTIVE (superseding any prior active baseline).
    """
    services.auth.require(actor, ProtectedAction.RECOMPUTE_BASELINE)
    if activate:
        services.auth.require(actor, ProtectedAction.APPROVE_BASELINE)

    series = services.measurements.series_for(
        SeriesQuery(
            parameter_id=parameter_id,
            window_start=window_start,
            window_end=window_end,
        )
    )
    values = np.asarray(series.values(), dtype=np.float64)
    study = individuals_study(values)
    centre = float(np.mean(values))
    sigma = float(study.sigma_within.value)
    baseline_id = BaselineId(f"BL-{uuid4().hex[:12]}")
    now = services.clock.now()
    status = BaselineStatus.ACTIVE if activate else BaselineStatus.CANDIDATE
    previous = services.baselines.active_for(parameter_id)
    previous_id = None if previous is None else str(previous.baseline_id)
    effective = now if activate else window_end

    limits = ControlLimit(
        parameter_id=parameter_id,
        baseline_id=baseline_id,
        unit=series.unit,
        centre_line=centre,
        lcl=centre - 3.0 * sigma,
        ucl=centre + 3.0 * sigma,
        sigma_estimator=study.sigma_within.estimator,
        sigma_estimate=sigma,
        sigma_multiplier=3.0,
        effective_from=effective,
    )
    baseline = Baseline(
        baseline_id=baseline_id,
        parameter_id=parameter_id,
        status=status,
        n_observations=int(values.size),
        sigma_estimator=study.sigma_within.estimator,
        limits=limits,
        window_start=window_start,
        window_end=window_end,
        approved_by=actor if activate else None,
        approved_at=now if activate else None,
        supersedes=None if previous is None else previous.baseline_id,
        effective_from=effective,
    )
    services.baselines.save(baseline)

    write_audit(
        services,
        event_type=AuditEventType.BASELINE_CREATED,
        actor=actor,
        reason=reason,
        after={
            "baseline_id": str(baseline_id),
            "parameter_id": str(parameter_id),
            "status": status.value,
            "n_observations": baseline.n_observations,
        },
        data_revision=series.data_revision,
    )
    if activate:
        if previous is not None:
            write_audit(
                services,
                event_type=AuditEventType.BASELINE_SUPERSEDED,
                actor=actor,
                reason=reason,
                before={"baseline_id": previous_id, "status": "active"},
                after={"baseline_id": previous_id, "status": "superseded"},
                data_revision=series.data_revision,
            )
        write_audit(
            services,
            event_type=AuditEventType.BASELINE_APPROVED,
            actor=actor,
            reason=reason,
            after={"baseline_id": str(baseline_id), "status": "active"},
            data_revision=series.data_revision,
        )

    return RecomputeBaselineResult(baseline=baseline, previous_active_id=previous_id)
