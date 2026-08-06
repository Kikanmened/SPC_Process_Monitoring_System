"""Evaluate a lot against the active baseline and configured rule set."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from spc_platform.analytics.charts import (
    FixedIndividualsLimits,
    PanelIdentity,
    PlottedPoints,
    individuals_chart,
)
from spc_platform.analytics.rules import evaluate_chart
from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.measurement_repository import SeriesQuery
from spc_platform.application.ports.violation_repository import (
    StoredViolation,
    new_stored_violation,
)
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.errors import NoActiveBaselineError
from spc_platform.domain.charting import ControlChart
from spc_platform.domain.enums import ChartStatistic, ChartType, MeasurementStatus
from spc_platform.domain.ids import ActorId, LotId, ParameterId


@dataclass(frozen=True, slots=True)
class EvaluateLotResult:
    """Outcome of lot evaluation."""

    violations: tuple[StoredViolation, ...]
    points_evaluated: int
    baseline_id: str


def evaluate_lot(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId,
    lot_id: LotId,
    window_start: datetime,
    window_end: datetime,
) -> EvaluateLotResult:
    """Chart the lot series against the active baseline and raise violations.

    Uses Phase II individuals limits from the baseline (FR-C03). Sites that are
    not superseded are plotted as individuals in time order.
    """
    services.auth.require(actor, ProtectedAction.EVALUATE_LOT)
    baseline = services.baselines.active_for(parameter_id)
    if baseline is None:
        raise NoActiveBaselineError(
            "no approved active baseline for parameter",
            parameter_id=str(parameter_id),
        )

    series = services.measurements.series_for(
        SeriesQuery(
            parameter_id=parameter_id,
            window_start=window_start,
            window_end=window_end,
            lot_id=lot_id,
        )
    )
    chartable = tuple(
        item
        for item in series.measurements
        if item.measurement_status is not MeasurementStatus.SUPERSEDED
    )
    values = np.asarray([item.value for item in chartable], dtype=np.float64)
    timestamps = tuple(item.timestamp for item in chartable)
    points = PlottedPoints(
        values=values,
        timestamps=timestamps,
        subgroup_sizes=tuple(1 for _ in chartable),
    )
    identity = PanelIdentity(
        parameter_id=parameter_id,
        baseline_id=baseline.baseline_id,
        chart_type=ChartType.I_MR,
        statistic=ChartStatistic.INDIVIDUAL,
        unit=series.unit,
    )
    limits = FixedIndividualsLimits(
        centre_line=baseline.limits.centre_line,
        sigma_within=baseline.limits.sigma_estimate,
        sigma_multiplier=baseline.limits.sigma_multiplier,
        sigma_estimator=baseline.limits.sigma_estimator,
    )
    panel = individuals_chart(points, identity, limits)
    chart = ControlChart(location=panel, dispersion=None)
    raised = evaluate_chart(services.rule_set, chart)

    stored: list[StoredViolation] = []
    for violation in raised:
        item = new_stored_violation(violation)
        write_audit(
            services,
            event_type=AuditEventType.VIOLATION_RAISED,
            actor=actor,
            reason="rule evaluation",
            after={
                "violation_id": item.violation_id,
                "rule_id": str(violation.rule_id),
                "parameter_id": str(parameter_id),
                "lot_id": str(lot_id),
                "point_index": violation.point_index,
            },
            data_revision=series.data_revision,
        )
        services.violations.save(item)
        stored.append(item)

    return EvaluateLotResult(
        violations=tuple(stored),
        points_evaluated=len(chartable),
        baseline_id=str(baseline.baseline_id),
    )
