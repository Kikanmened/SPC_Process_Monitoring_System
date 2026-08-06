"""Shared audit helper for use cases."""

from __future__ import annotations

from typing import Any

from spc_platform.application.audit import AuditEventType, new_audit_record
from spc_platform.application.context import ApplicationServices
from spc_platform.common.provenance import Provenance, capture_provenance
from spc_platform.domain.ids import ActorId, DataRevision


def write_audit(  # noqa: PLR0913 — shared audit helper carries full context
    services: ApplicationServices,
    *,
    event_type: AuditEventType,
    actor: ActorId,
    reason: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    data_revision: DataRevision | None = None,
    succeeded: bool = True,
) -> None:
    """Append an audit record. Propagates ``AuditWriteError`` to abort the action."""
    provenance: Provenance | None = None
    if data_revision is not None:
        provenance = capture_provenance(
            data_revision=data_revision,
            code_revision=services.code_revision,
            config_revision=services.config_revision,
            clock=services.clock,
        )
    record = new_audit_record(
        event_type=event_type,
        actor=actor,
        timestamp=services.clock.now(),
        reason=reason,
        before=before,
        after=after,
        provenance=provenance,
        succeeded=succeeded,
    )
    services.audit.append(record)
