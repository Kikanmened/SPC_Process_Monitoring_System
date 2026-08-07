"""Line overview ordered by attention (open violations first)."""

from __future__ import annotations

from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.views.overview import AttentionRow, LineOverview
from spc_platform.domain.enums import ViolationSeverity
from spc_platform.domain.ids import ActorId, ParameterId

_SEVERITY_RANK = {
    ViolationSeverity.CRITICAL: 0,
    ViolationSeverity.WARNING: 1,
    ViolationSeverity.INFO: 2,
}


def build_line_overview(
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_ids: tuple[ParameterId, ...] | None = None,
) -> LineOverview:
    """Summarise parameters so the worst open problems surface first."""
    services.auth.require(actor, ProtectedAction.EVALUATE_LOT)
    open_items = services.violations.list_open(None)
    by_parameter: dict[ParameterId, list[ViolationSeverity]] = {}
    counts: dict[ParameterId, int] = {}
    for item in open_items:
        pid = item.violation.parameter_id
        by_parameter.setdefault(pid, []).append(item.violation.severity)
        counts[pid] = counts.get(pid, 0) + 1

    ids = parameter_ids or tuple(sorted(by_parameter.keys(), key=str))

    rows: list[AttentionRow] = []
    for parameter_id in ids:
        severities = by_parameter.get(parameter_id, [])
        highest: ViolationSeverity | None = None
        if severities:
            highest = min(
                severities,
                key=lambda severity: _SEVERITY_RANK.get(severity, 99),
            )
        rows.append(
            AttentionRow(
                parameter_id=parameter_id,
                open_violations=counts.get(parameter_id, 0),
                highest_severity=highest,
                has_active_baseline=services.baselines.active_for(parameter_id) is not None,
                attention_rank=0,
            )
        )
    rows.sort(
        key=lambda row: (
            0 if row.open_violations else 1,
            _SEVERITY_RANK.get(row.highest_severity, 99)
            if row.highest_severity is not None
            else 99,
            -row.open_violations,
            str(row.parameter_id),
        )
    )
    ranked = tuple(
        row.model_copy(update={"attention_rank": index}) for index, row in enumerate(rows)
    )
    return LineOverview(
        rows=ranked,
        n_parameters=len(ranked),
        n_open_violations=sum(row.open_violations for row in ranked),
    )
