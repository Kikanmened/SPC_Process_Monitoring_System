"""JSONL file audit store under ``logs/audit/`` (FR-AU01, NFR-R04)."""

from __future__ import annotations

import json
from pathlib import Path

from spc_platform.application.audit import AuditEventType, AuditRecord
from spc_platform.common.errors import AuditWriteError


class FileAuditStore:
    """Append-only JSONL sink. Never truncates or rewrites prior lines."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def append(self, record: AuditRecord) -> None:
        """Append one JSON line. Raises ``AuditWriteError`` on I/O failure."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            line = record.model_dump_json() + "\n"
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError as exc:
            raise AuditWriteError(
                "failed to append audit record",
                path=str(self._path),
                record_id=record.record_id,
                reason=str(exc),
            ) from exc

    def list_for(
        self,
        event_type: AuditEventType | None = None,
    ) -> tuple[AuditRecord, ...]:
        """Read all records in file order."""
        if not self._path.is_file():
            return ()
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise AuditWriteError(
                "failed to read audit trail",
                path=str(self._path),
                reason=str(exc),
            ) from exc
        records: list[AuditRecord] = []
        for line in lines:
            if not line.strip():
                continue
            payload = json.loads(line)
            record = AuditRecord.model_validate(payload)
            if event_type is None or record.event_type is event_type:
                records.append(record)
        return tuple(records)
