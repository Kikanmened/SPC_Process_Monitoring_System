"""Port for the append-only audit trail (FR-AU01)."""

from __future__ import annotations

from typing import Protocol

from spc_platform.application.audit import AuditEventType, AuditRecord


class AuditSink(Protocol):
    """Write audit records. Failure must abort the calling action."""

    def append(self, record: AuditRecord) -> None:
        """Append one record. Raises ``AuditWriteError`` on failure."""
        ...

    def list_for(
        self,
        event_type: AuditEventType | None = None,
    ) -> tuple[AuditRecord, ...]:
        """Return records in append order, optionally filtered by type."""
        ...
