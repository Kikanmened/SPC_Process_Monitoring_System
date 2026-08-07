"""Open violation queue ordered by severity and age (FR-A01)."""

from __future__ import annotations

from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.views.queue_view import AlarmQueueItem, AlarmQueueView
from spc_platform.domain.enums import ViolationSeverity
from spc_platform.domain.ids import ActorId, ParameterId

_SEVERITY_RANK = {
    ViolationSeverity.CRITICAL: 0,
    ViolationSeverity.WARNING: 1,
    ViolationSeverity.INFO: 2,
}


def build_alarm_queue(
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId | None = None,
) -> AlarmQueueView:
    """Return open violations newest-first within severity (AC-B2 OCAP field)."""
    services.auth.require(actor, ProtectedAction.ACKNOWLEDGE_VIOLATION)
    open_items = services.violations.list_open(parameter_id)
    items = [
        AlarmQueueItem(
            violation_id=item.violation_id,
            parameter_id=item.violation.parameter_id,
            rule_id=str(item.violation.rule_id),
            severity=item.violation.severity,
            timestamp=item.violation.timestamp,
            statistic_value=item.violation.statistic_value,
            point_index=item.violation.point_index,
            baseline_id=str(item.violation.baseline_id),
            ocap_id=None,
            acknowledged=item.acknowledged,
        )
        for item in open_items
    ]
    items.sort(
        key=lambda row: (
            _SEVERITY_RANK.get(row.severity, 99),
            -row.timestamp.timestamp(),
        )
    )
    return AlarmQueueView(
        items=tuple(items),
        n_open=len(items),
    )
