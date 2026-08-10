"""Close an excursion with mandatory disposition and 8D/CAPA (FR-A07)."""

from __future__ import annotations

from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.errors import (
    DispositionRequiredError,
    ExcursionStateError,
    InsufficientDataError,
)
from spc_platform.domain.enums import ExcursionState
from spc_platform.domain.excursion import Excursion
from spc_platform.domain.ids import ActorId, CapaId, EightDId, ExcursionId


def close_excursion(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    excursion_id: ExcursionId,
    capa_id: CapaId | None = None,
    eight_d_id: EightDId | None = None,
    reason: str = "",
) -> Excursion:
    """Close only when dispositions exist and an 8D or CAPA id is supplied."""
    services.auth.require(actor, ProtectedAction.CLOSE_EXCURSION)
    current = services.excursions.get(excursion_id)
    if current is None:
        raise InsufficientDataError(
            "unknown excursion",
            excursion_id=str(excursion_id),
        )
    if current.state is ExcursionState.CLOSED:
        raise ExcursionStateError(
            "excursion is already closed",
            excursion_id=str(excursion_id),
        )
    if capa_id is None and eight_d_id is None:
        raise InsufficientDataError(
            "closure requires an 8D or CAPA identifier",
            excursion_id=str(excursion_id),
        )
    for lot_id in current.lot_ids:
        if not services.dispositions.list_for(lot_id):
            raise DispositionRequiredError(
                "cannot close excursion without disposition and reason",
                lot_id=str(lot_id),
                excursion_id=str(excursion_id),
            )
    updated = current.model_copy(
        update={
            "state": ExcursionState.CLOSED,
            "closed_at": services.clock.now(),
            "closed_by": actor,
            "capa_id": capa_id,
            "eight_d_id": eight_d_id,
        }
    )
    write_audit(
        services,
        event_type=AuditEventType.EXCURSION_CLOSED,
        actor=actor,
        reason=reason or "excursion closed",
        before={"state": current.state.value},
        after={
            "state": updated.state.value,
            "excursion_id": str(excursion_id),
            "capa_id": None if capa_id is None else str(capa_id),
            "eight_d_id": None if eight_d_id is None else str(eight_d_id),
        },
    )
    services.excursions.save(updated)
    return updated
