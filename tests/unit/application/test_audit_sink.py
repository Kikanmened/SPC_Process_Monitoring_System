"""AuditSink fake and append-only file adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from spc_platform.application.audit import AuditEventType, new_audit_record
from spc_platform.common.errors import AuditWriteError
from spc_platform.domain.ids import ActorId
from spc_platform.infrastructure.audit import FakeAuditSink, FileAuditStore


def _record(event: AuditEventType = AuditEventType.VIOLATION_RAISED) -> object:
    return new_audit_record(
        event_type=event,
        actor=ActorId("qe.smith"),
        timestamp=datetime(2025, 7, 1, 12, 0, tzinfo=UTC),
        reason="test",
        after={"k": "v"},
    )


def test_fake_audit_appends_in_order() -> None:
    sink = FakeAuditSink()
    first = _record(AuditEventType.BASELINE_CREATED)
    second = _record(AuditEventType.BASELINE_APPROVED)
    sink.append(first)  # type: ignore[arg-type]
    sink.append(second)  # type: ignore[arg-type]
    assert [item.event_type for item in sink.list_for()] == [
        AuditEventType.BASELINE_CREATED,
        AuditEventType.BASELINE_APPROVED,
    ]


def test_fake_audit_can_refuse_writes() -> None:
    sink = FakeAuditSink(fail_writes=True)
    with pytest.raises(AuditWriteError):
        sink.append(_record())  # type: ignore[arg-type]


def test_file_audit_is_append_only(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    store = FileAuditStore(path)
    store.append(_record(AuditEventType.REPORT_GENERATED))  # type: ignore[arg-type]
    store.append(_record(AuditEventType.REPORT_REFUSED))  # type: ignore[arg-type]
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 2
    # Prior line is unchanged when a second record is appended.
    first_line = lines[0]
    store.append(_record(AuditEventType.PIPELINE_RUN))  # type: ignore[arg-type]
    rewritten = path.read_text(encoding="utf-8").splitlines()
    assert rewritten[0] == first_line
    assert len([line for line in rewritten if line.strip()]) == 3
