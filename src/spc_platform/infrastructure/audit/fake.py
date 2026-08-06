"""In-memory audit sink for tests."""

from __future__ import annotations

from spc_platform.application.audit import AuditEventType, AuditRecord
from spc_platform.common.errors import AuditWriteError


class FakeAuditSink:
    """Dict-backed ``AuditSink``. Can be configured to fail writes."""

    def __init__(self, *, fail_writes: bool = False) -> None:
        self._records: list[AuditRecord] = []
        self.fail_writes = fail_writes

    def append(self, record: AuditRecord) -> None:
        """Append one record, or raise when configured to fail."""
        if self.fail_writes:
            raise AuditWriteError(
                "audit sink refused the write",
                record_id=record.record_id,
                event_type=record.event_type.value,
            )
        self._records.append(record)

    def list_for(
        self,
        event_type: AuditEventType | None = None,
    ) -> tuple[AuditRecord, ...]:
        """Return records in append order."""
        if event_type is None:
            return tuple(self._records)
        return tuple(item for item in self._records if item.event_type is event_type)
