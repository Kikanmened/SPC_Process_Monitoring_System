"""Assemble a control-chart view from baseline, series, and rule evaluation."""

from __future__ import annotations

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
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.application.views.chart_view import ChartPoint, ChartView
from spc_platform.common.errors import NoActiveBaselineError
from spc_platform.domain.charting import ControlChart
from spc_platform.domain.enums import ChartStatistic, ChartType, MeasurementStatus
from spc_platform.domain.ids import ActorId, LotId, ParameterId, ProductId


def build_chart_view(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId,
    window_start: datetime,
    window_end: datetime,
    lot_id: LotId | None = None,
    product_id: ProductId | None = None,
) -> ChartView:
    """Build a Phase II individuals chart view with violation markers.

    Specification limits are attached when an effective specification exists;
    they remain a separate field so renderers cannot treat them as control
    limits (FR-C06).
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
            product_id=product_id,
        )
    )
    chartable = tuple(
        item
        for item in series.measurements
        if item.measurement_status is not MeasurementStatus.SUPERSEDED
    )
    values = np.asarray([item.value for item in chartable], dtype=np.float64)
    timestamps = tuple(item.timestamp for item in chartable)
    panel = individuals_chart(
        PlottedPoints(
            values=values,
            timestamps=timestamps,
            subgroup_sizes=tuple(1 for _ in chartable),
        ),
        PanelIdentity(
            parameter_id=parameter_id,
            baseline_id=baseline.baseline_id,
            chart_type=ChartType.I_MR,
            statistic=ChartStatistic.INDIVIDUAL,
            unit=series.unit,
        ),
        FixedIndividualsLimits(
            centre_line=baseline.limits.centre_line,
            sigma_within=baseline.limits.sigma_estimate,
            sigma_multiplier=baseline.limits.sigma_multiplier,
            sigma_estimator=baseline.limits.sigma_estimator,
        ),
    )
    violations = evaluate_chart(
        services.rule_set,
        ControlChart(location=panel, dispersion=None),
    )
    by_index: dict[int, list[str]] = {}
    severity_by_index: dict[int, list[str]] = {}
    for violation in violations:
        by_index.setdefault(violation.point_index, []).append(str(violation.rule_id))
        severity_by_index.setdefault(violation.point_index, []).append(violation.severity.value)

    points: list[ChartPoint] = []
    for index, item in enumerate(chartable):
        rules = tuple(by_index.get(index, []))
        points.append(
            ChartPoint(
                index=index,
                timestamp=item.timestamp,
                value=item.value,
                violated=bool(rules),
                rule_ids=rules,
                severities=tuple(severity_by_index.get(index, [])),
            )
        )

    product = product_id or (chartable[0].product_id if chartable else None)
    specification = None
    if product is not None:
        specification = services.specifications.effective_for(
            parameter_id,
            product,
            at=window_end,
        )

    write_audit(
        services,
        event_type=AuditEventType.MEASUREMENT_DATA_ACCESS,
        actor=actor,
        reason="control chart view",
        after={
            "parameter_id": str(parameter_id),
            "n_observations": len(points),
            "violation_count": len(violations),
        },
        data_revision=series.data_revision,
    )
    return ChartView(
        parameter_id=parameter_id,
        baseline_id=baseline.baseline_id,
        chart_type=ChartType.I_MR,
        unit=series.unit,
        points=tuple(points),
        centre_line=baseline.limits.centre_line,
        lcl=baseline.limits.lcl,
        ucl=baseline.limits.ucl,
        sigma_estimator=baseline.limits.sigma_estimator,
        sigma_estimate=baseline.limits.sigma_estimate,
        specification_lsl=None if specification is None else specification.lsl,
        specification_usl=None if specification is None else specification.usl,
        specification_target=None if specification is None else specification.target,
        n_observations=len(points),
        window_start=window_start,
        window_end=window_end,
        data_revision=series.data_revision,
        config_revision=str(services.config_revision),
    )
