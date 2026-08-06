"""Audit records emitted by use cases match the QA §2.2 shape."""

from __future__ import annotations

import contextlib

from tests.factories.application import (
    ACTOR,
    WINDOW_END,
    WINDOW_START,
    seeded_bundle,
)

from spc_platform.application.audit import AuditEventType, AuditRecord
from spc_platform.application.use_cases import (
    evaluate_lot,
    generate_capability_report,
    record_disposition,
)
from spc_platform.common.errors import UnstableProcessError
from spc_platform.domain.enums import DispositionAction
from spc_platform.domain.ids import LotId, ParameterId, ProductId


def _assert_shape(record: AuditRecord) -> None:
    assert record.record_id
    assert isinstance(record.event_type, AuditEventType)
    assert record.actor
    assert record.timestamp.tzinfo is not None
    assert isinstance(record.before, dict)
    assert isinstance(record.after, dict)
    assert isinstance(record.succeeded, bool)


def test_violation_raised_audit_shape() -> None:
    bundle = seeded_bundle(outlier=11.5)
    evaluate_lot(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-001"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    for record in bundle.audit.list_for(AuditEventType.VIOLATION_RAISED):
        _assert_shape(record)
        assert record.provenance is not None


def test_report_refused_audit_shape() -> None:
    bundle = seeded_bundle(outlier=11.5)
    with contextlib.suppress(UnstableProcessError):
        generate_capability_report(
            bundle.services,
            actor=ACTOR,
            parameter_id=ParameterId("OXIDE_THK"),
            product_id=ProductId("DEV-A"),
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )
    records = bundle.audit.list_for(AuditEventType.REPORT_REFUSED)
    assert records
    _assert_shape(records[0])
    assert records[0].succeeded is False


def test_disposition_audit_shape() -> None:
    bundle = seeded_bundle()
    record_disposition(
        bundle.services,
        actor=ACTOR,
        lot_id=LotId("LOT-001"),
        action=DispositionAction.HOLD,
        reason="quarantine pending review",
    )
    records = bundle.audit.list_for(AuditEventType.VIOLATION_DISPOSITIONED)
    assert records
    _assert_shape(records[0])
