"""Compare a matched parameter across two tools or chambers (FR-T01)."""

from __future__ import annotations

from datetime import datetime

import numpy as np

from spc_platform.analytics.comparison.matched_tools import (
    MIN_GROUP_SIZE,
    compare_two_groups,
)
from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.measurement_repository import SeriesQuery
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.application.views.tool_comparison import ToolComparisonView, ToolSeriesSummary
from spc_platform.common.errors import InsufficientDataError, ViewDataUnavailableError
from spc_platform.domain.enums import MeasurementStatus
from spc_platform.domain.ids import ActorId, ParameterId


def compare_tools(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId,
    window_start: datetime,
    window_end: datetime,
    group_a: str,
    group_b: str,
    group_by: str = "tool",
) -> ToolComparisonView:
    """Run Welch's t-test on two tool or chamber groups for one parameter.

    ``group_by`` is ``tool`` or ``chamber``. Groups are matched by id string.
    """
    services.auth.require(actor, ProtectedAction.EVALUATE_LOT)
    if group_by not in {"tool", "chamber"}:
        raise ViewDataUnavailableError(
            "group_by must be 'tool' or 'chamber'",
            group_by=group_by,
        )
    series = services.measurements.series_for(
        SeriesQuery(
            parameter_id=parameter_id,
            window_start=window_start,
            window_end=window_end,
        )
    )
    chartable = [
        item
        for item in series.measurements
        if item.measurement_status is not MeasurementStatus.SUPERSEDED
    ]
    if group_by == "tool":
        values_a = np.asarray(
            [item.value for item in chartable if str(item.tool_id) == group_a],
            dtype=np.float64,
        )
        values_b = np.asarray(
            [item.value for item in chartable if str(item.tool_id) == group_b],
            dtype=np.float64,
        )
    else:
        values_a = np.asarray(
            [item.value for item in chartable if str(item.chamber_id) == group_a],
            dtype=np.float64,
        )
        values_b = np.asarray(
            [item.value for item in chartable if str(item.chamber_id) == group_b],
            dtype=np.float64,
        )
    if values_a.size == 0 or values_b.size == 0:
        raise InsufficientDataError(
            "one or both comparison groups have no observations in the window",
            group_a=group_a,
            group_b=group_b,
            n_a=int(values_a.size),
            n_b=int(values_b.size),
        )
    comparison = compare_two_groups(values_a, values_b)

    def _summary(key: str, values: np.ndarray) -> ToolSeriesSummary:
        stdev = None
        if values.size >= MIN_GROUP_SIZE:
            stdev = float(np.std(values, ddof=1))
        return ToolSeriesSummary(
            group_key=key,
            group_kind=group_by,
            n_observations=int(values.size),
            mean=float(np.mean(values)),
            sample_stdev=stdev,
        )

    write_audit(
        services,
        event_type=AuditEventType.REPORT_GENERATED,
        actor=actor,
        reason="tool comparison",
        after={
            "parameter_id": str(parameter_id),
            "group_by": group_by,
            "group_a": group_a,
            "group_b": group_b,
            "test_name": comparison.test_name,
            "p_value": comparison.p_value,
        },
        data_revision=series.data_revision,
    )
    return ToolComparisonView(
        parameter_id=parameter_id,
        unit=series.unit,
        window_start=window_start,
        window_end=window_end,
        groups=(_summary(group_a, values_a), _summary(group_b, values_b)),
        test_name=comparison.test_name,
        statistic=comparison.statistic,
        p_value=comparison.p_value,
        effect_size=comparison.effect_size,
        n_total=comparison.n_a + comparison.n_b,
        note="Welch's t-test; does not assert a root cause.",
    )
