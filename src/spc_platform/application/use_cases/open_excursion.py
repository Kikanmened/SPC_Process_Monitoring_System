"""Open an excursion from detected violations (FR-A01 lifecycle start)."""

from __future__ import annotations

from uuid import uuid4

from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.errors import InsufficientDataError
from spc_platform.domain.enums import ExcursionState
from spc_platform.domain.excursion import Excursion
from spc_platform.domain.ids import ActorId, ExcursionId, LotId, ParameterId, ProductId


def open_excursion(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId,
    lot_ids: tuple[LotId, ...],
    violation_ids: tuple[str, ...],
    product_id: ProductId | None = None,
) -> Excursion:
    """Create a detected excursion linked to violations and OCAP when known."""
    services.auth.require(actor, ProtectedAction.OPEN_EXCURSION)
    if not lot_ids or not violation_ids:
        raise InsufficientDataError(
            "excursion requires at least one lot and one violation",
            lot_count=len(lot_ids),
            violation_count=len(violation_ids),
        )
    for violation_id in violation_ids:
        if services.violations.get(violation_id) is None:
            raise InsufficientDataError(
                "unknown violation for excursion",
                violation_id=violation_id,
            )
    ocap_id = services.control_plans.ocap_for(parameter_id, product_id)
    excursion = Excursion(
        excursion_id=ExcursionId(f"exc-{uuid4().hex}"),
        parameter_id=parameter_id,
        lot_ids=lot_ids,
        violation_ids=violation_ids,
        state=ExcursionState.DETECTED,
        ocap_id=ocap_id,
        opened_at=services.clock.now(),
        opened_by=actor,
    )
    write_audit(
        services,
        event_type=AuditEventType.EXCURSION_OPENED,
        actor=actor,
        reason="excursion detected",
        after={
            "excursion_id": str(excursion.excursion_id),
            "parameter_id": str(parameter_id),
            "violation_ids": list(violation_ids),
            "ocap_id": None if ocap_id is None else str(ocap_id),
        },
    )
    services.excursions.save(excursion)
    return excursion
