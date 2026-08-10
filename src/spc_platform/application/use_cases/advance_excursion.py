"""Advance excursion lifecycle: containment and investigation (FR-A*)."""

from __future__ import annotations

from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.errors import ExcursionStateError, InsufficientDataError
from spc_platform.domain.enums import ExcursionState
from spc_platform.domain.excursion import Excursion
from spc_platform.domain.ids import ActorId, ExcursionId


def contain_excursion(
    services: ApplicationServices,
    *,
    actor: ActorId,
    excursion_id: ExcursionId,
    note: str,
) -> Excursion:
    """Record containment after detection."""
    services.auth.require(actor, ProtectedAction.OPEN_EXCURSION)
    current = _require(services, excursion_id)
    if current.state is not ExcursionState.DETECTED:
        raise ExcursionStateError(
            "containment only from detected state",
            state=current.state.value,
        )
    if not note.strip():
        raise InsufficientDataError("containment note is required")
    updated = current.model_copy(
        update={
            "state": ExcursionState.CONTAINED,
            "containment_note": note.strip(),
            "contained_at": services.clock.now(),
        }
    )
    write_audit(
        services,
        event_type=AuditEventType.EXCURSION_CONTAINED,
        actor=actor,
        reason=note.strip(),
        before={"state": current.state.value},
        after={"state": updated.state.value, "excursion_id": str(excursion_id)},
    )
    services.excursions.save(updated)
    return updated


def record_excursion_investigation(
    services: ApplicationServices,
    *,
    actor: ActorId,
    excursion_id: ExcursionId,
    summary: str,
) -> Excursion:
    """Record commonality / investigation notes — never a cause assertion."""
    services.auth.require(actor, ProtectedAction.OPEN_EXCURSION)
    current = _require(services, excursion_id)
    if current.state not in {ExcursionState.CONTAINED, ExcursionState.INVESTIGATING}:
        raise ExcursionStateError(
            "investigation only from contained or investigating state",
            state=current.state.value,
        )
    if not summary.strip():
        raise InsufficientDataError("investigation summary is required")
    updated = current.model_copy(
        update={
            "state": ExcursionState.INVESTIGATING,
            "investigation_summary": summary.strip(),
            "investigated_at": services.clock.now(),
        }
    )
    write_audit(
        services,
        event_type=AuditEventType.EXCURSION_INVESTIGATING,
        actor=actor,
        reason=summary.strip(),
        before={"state": current.state.value},
        after={"state": updated.state.value, "excursion_id": str(excursion_id)},
    )
    services.excursions.save(updated)
    return updated


def mark_excursion_dispositioned(
    services: ApplicationServices,
    *,
    actor: ActorId,
    excursion_id: ExcursionId,
) -> Excursion:
    """Mark dispositioned once every linked lot has a disposition record."""
    services.auth.require(actor, ProtectedAction.RECORD_DISPOSITION)
    current = _require(services, excursion_id)
    if current.state not in {
        ExcursionState.INVESTIGATING,
        ExcursionState.CONTAINED,
        ExcursionState.DISPOSITIONED,
    }:
        raise ExcursionStateError(
            "disposition marking not allowed from current state",
            state=current.state.value,
        )
    for lot_id in current.lot_ids:
        if not services.dispositions.list_for(lot_id):
            raise InsufficientDataError(
                "disposition missing for excursion lot",
                lot_id=str(lot_id),
                excursion_id=str(excursion_id),
            )
    updated = current.model_copy(update={"state": ExcursionState.DISPOSITIONED})
    write_audit(
        services,
        event_type=AuditEventType.EXCURSION_DISPOSITIONED,
        actor=actor,
        reason="all linked lots dispositioned",
        before={"state": current.state.value},
        after={"state": updated.state.value, "excursion_id": str(excursion_id)},
    )
    services.excursions.save(updated)
    return updated


def _require(services: ApplicationServices, excursion_id: ExcursionId) -> Excursion:
    current = services.excursions.get(excursion_id)
    if current is None:
        raise InsufficientDataError(
            "unknown excursion",
            excursion_id=str(excursion_id),
        )
    return current
