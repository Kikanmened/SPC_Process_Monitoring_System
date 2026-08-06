"""Acknowledge an open violation (FR-A02)."""

from __future__ import annotations

from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.violation_repository import StoredViolation
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.errors import InsufficientDataError
from spc_platform.domain.ids import ActorId


def acknowledge_violation(
    services: ApplicationServices,
    *,
    actor: ActorId,
    violation_id: str,
    reason: str = "",
) -> StoredViolation:
    """Record acknowledgement with actor and timestamp."""
    services.auth.require(actor, ProtectedAction.ACKNOWLEDGE_VIOLATION)
    existing = services.violations.get(violation_id)
    if existing is None:
        raise InsufficientDataError(
            "violation does not exist",
            violation_id=violation_id,
        )
    timestamp = services.clock.now()
    write_audit(
        services,
        event_type=AuditEventType.VIOLATION_ACKNOWLEDGED,
        actor=actor,
        reason=reason,
        before={"violation_id": violation_id, "acknowledged": existing.acknowledged},
        after={
            "violation_id": violation_id,
            "acknowledged": True,
            "acknowledged_by": str(actor),
            "acknowledged_at": timestamp.isoformat(),
        },
    )
    return services.violations.acknowledge(
        violation_id,
        actor=actor,
        timestamp=timestamp,
    )
