"""Record a material disposition with mandatory reason (FR-A03)."""

from __future__ import annotations

from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.domain.disposition import Disposition
from spc_platform.domain.enums import DispositionAction
from spc_platform.domain.ids import ActorId, LotId, OcapId


def record_disposition(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    lot_id: LotId,
    action: DispositionAction,
    reason: str,
    ocap_id: OcapId | None = None,
) -> Disposition:
    """Append a disposition and audit it."""
    services.auth.require(actor, ProtectedAction.RECORD_DISPOSITION)
    disposition = Disposition(
        lot_id=lot_id,
        action=action,
        actor=actor,
        timestamp=services.clock.now(),
        reason=reason,
        ocap_id=ocap_id,
    )
    write_audit(
        services,
        event_type=AuditEventType.VIOLATION_DISPOSITIONED,
        actor=actor,
        reason=reason,
        after={
            "lot_id": str(lot_id),
            "action": action.value,
            "ocap_id": None if ocap_id is None else str(ocap_id),
        },
    )
    services.dispositions.append(disposition)
    return disposition
