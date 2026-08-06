"""Generate a capability report, refusing unstable processes (FR-P04)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from spc_platform.analytics.capability import (
    CapabilityContext,
    CapabilityResult,
    DispersionPair,
    StabilityStatus,
    capability,
)
from spc_platform.analytics.charts import (
    FixedIndividualsLimits,
    PanelIdentity,
    PlottedPoints,
    individuals_chart,
)
from spc_platform.analytics.estimators.sigma import sigma_overall, sigma_within_moving_range
from spc_platform.analytics.rules import evaluate_chart
from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.measurement_repository import SeriesQuery
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.errors import (
    InsufficientDataError,
    NoActiveBaselineError,
    UnstableProcessError,
)
from spc_platform.domain.charting import ControlChart
from spc_platform.domain.enums import ChartStatistic, ChartType
from spc_platform.domain.ids import ActorId, ParameterId, ProductId


@dataclass(frozen=True, slots=True)
class CapabilityReportOutcome:
    """Either a capability result or a structured refusal."""

    result: CapabilityResult | None
    refused: bool
    refusal_reason: str | None


def generate_capability_report(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId,
    product_id: ProductId,
    window_start: datetime,
    window_end: datetime,
) -> CapabilityReportOutcome:
    """Compute capability only when the process is in control (FR-P04, AC-C2).

    Stability is judged by evaluating the configured rule set against the
    active baseline over the window. Any violation → refusal, audited as
    ``report_refused``.
    """
    services.auth.require(actor, ProtectedAction.GENERATE_CAPABILITY_REPORT)
    specification = services.specifications.effective_for(
        parameter_id,
        product_id,
        at=window_end,
    )
    if specification is None:
        raise InsufficientDataError(
            "no specification in force for capability assessment",
            parameter_id=str(parameter_id),
            product_id=str(product_id),
        )
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
            product_id=product_id,
        )
    )
    values = np.asarray(series.values(), dtype=np.float64)
    timestamps = tuple(item.timestamp for item in series.measurements)
    points = PlottedPoints(
        values=values,
        timestamps=timestamps,
        subgroup_sizes=tuple(1 for _ in timestamps),
    )
    identity = PanelIdentity(
        parameter_id=parameter_id,
        baseline_id=baseline.baseline_id,
        chart_type=ChartType.I_MR,
        statistic=ChartStatistic.INDIVIDUAL,
        unit=series.unit,
    )
    panel = individuals_chart(
        points,
        identity,
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
    stability = StabilityStatus.OUT_OF_CONTROL if violations else StabilityStatus.IN_CONTROL
    context = CapabilityContext(
        window=(window_start, window_end),
        stability=stability,
        require_stable=True,
    )

    if stability is StabilityStatus.OUT_OF_CONTROL:
        reason = f"process out of control: {len(violations)} rule violation(s) in window"
        write_audit(
            services,
            event_type=AuditEventType.REPORT_REFUSED,
            actor=actor,
            reason=reason,
            after={
                "parameter_id": str(parameter_id),
                "product_id": str(product_id),
                "stability": stability.value,
                "violation_count": len(violations),
            },
            data_revision=series.data_revision,
            succeeded=False,
        )
        # Surface the typed refusal so callers cannot mistake it for success.
        raise UnstableProcessError(
            "capability report refused: process not demonstrated to be in control",
            parameter_id=str(parameter_id),
            stability=stability.value,
            violation_count=len(violations),
        )

    dispersion = DispersionPair(
        within=sigma_within_moving_range(values),
        overall=sigma_overall(values),
    )
    result = capability(values, specification, dispersion=dispersion, context=context)
    write_audit(
        services,
        event_type=AuditEventType.REPORT_GENERATED,
        actor=actor,
        reason="capability report",
        after={
            "parameter_id": str(parameter_id),
            "product_id": str(product_id),
            "n_observations": int(values.size),
            "stability": stability.value,
        },
        data_revision=series.data_revision,
    )
    return CapabilityReportOutcome(
        result=result,
        refused=False,
        refusal_reason=None,
    )
