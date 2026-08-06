"""File audit store grows and never rewrites prior lines."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from spc_platform.application.audit import AuditEventType, new_audit_record
from spc_platform.domain.ids import ActorId
from spc_platform.infrastructure.audit import FileAuditStore


def test_append_only_file_never_rewrites_prior_lines(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "audit" / "trail.jsonl"
    store = FileAuditStore(path)
    first = new_audit_record(
        event_type=AuditEventType.PIPELINE_RUN,
        actor=ActorId("pipeline"),
        timestamp=datetime(2025, 7, 1, tzinfo=UTC),
        after={"step": 1},
    )
    store.append(first)
    snapshot = path.read_bytes()
    second = new_audit_record(
        event_type=AuditEventType.REPORT_GENERATED,
        actor=ActorId("qe.smith"),
        timestamp=datetime(2025, 7, 2, tzinfo=UTC),
        after={"step": 2},
    )
    store.append(second)
    content = path.read_bytes()
    assert content.startswith(snapshot)
    assert content.count(b"\n") == 2
    records = store.list_for()
    assert len(records) == 2
    assert records[0].record_id == first.record_id
